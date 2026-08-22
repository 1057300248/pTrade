# -*- coding: utf-8 -*-
"""
RMDC: Residual-Momentum De-Crowding ETF rotation for 国金 PTrade.

Design (2026 rewrite, not regime_etf_rotation.py):
- Residual momentum: ETF log returns regressed on 1 + r(510300)
  + (r(510500) - r(510300)); fit 120d, score = sum of the last 60
  residuals (last 5 days skipped) divided by their std.
- Huatai-style 0-4 crowding score on OHLCV; >=3 blocks new opens.
- State machine from the GROWTH sleeve: breadth (pct of 20d ret > 0)
  and median 20d annualised vol. offense B>=0.60 & vol<=0.30,
  defense B<0.40 or vol>0.40, lockdown 5 sessions after a crash
  (510300 down >=6% in 1d or >=8% in 3d).
- Greedy correlation filter at 0.65; if mean pairwise corr of the
  top-5 growth names >0.75, growth sleeve is halved and capped at 1.
- Absolute momentum gate: 63d return > 0 and > 511010 63d return.
- Inverse-vol weights, 12% portfolio vol target, ~25% diversifier
  floor unless every diversifier has a negative 63d return.
- Weekly rebalance 14:50 (sell leg), buy leg ALWAYS at 14:54,
  crash / 20% trailing-stop overlay at 14:45 plus 09:35/13:05
  checks in handle_data, reverse repo at 14:57 in live only.

PTrade notes:
- Paste this whole file into 国金 PTrade; run in minute mode so the
  14:45/14:50/14:54/14:57 schedule fires.
- 国金 broker adapter is 'auto', NOT 'guosheng' (e.g. SimTradeLab
  backtest config: broker='auto').
- Python 3.11 with numpy. No pandas required, no f-strings, no
  os/sys/network, no get_snapshot in the core path.
- get_history one symbol at a time with fq='pre', include=False.
- order/order_target only (never order_target_value); sell before
  buy; buys capped by available cash; 100-share lots except 51188*.
"""
import math

import numpy as np


# QDII (513*) live only in DIVERSIFIER, never in GROWTH.
GROWTH = [
    "510300.SS",
    "510500.SS",
    "512100.SS",
    "159915.SZ",
    "588000.SS",
    "512480.SS",
    "515880.SS",
    "515980.SS",
    "512660.SS",
    "512010.SS",
    "512800.SS",
    "512880.SS",
    "512690.SS",
    "512400.SS",
    "515030.SS",
    "516160.SS",
    "515220.SS",
]

DIVERSIFIER = [
    "518880.SS",
    "510880.SS",
    "512890.SS",
    "511010.SS",
    "511090.SS",
    "511260.SS",
    "513500.SS",
    "513030.SS",
    "513520.SS",
    "513100.SS",
]

STATE_ON = "offense"
STATE_BAL = "balanced"
STATE_OFF = "defense"
STATE_LOCK = "lockdown"

# (growth, diversifier, cash) sleeve weights per state.
SLEEVE_WEIGHTS = {
    STATE_ON: (0.70, 0.25, 0.05),
    STATE_BAL: (0.40, 0.45, 0.15),
    STATE_OFF: (0.00, 0.65, 0.35),
    STATE_LOCK: (0.00, 0.30, 0.70),
}


# ---------------------------------------------------------------------------
# Pure quant functions (frozen public API; no PTrade calls in here)
# ---------------------------------------------------------------------------
def log_returns(closes):
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) < 2:
        return np.array([])
    return np.diff(np.log(np.maximum(closes, 1e-12)))


def _corr(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n < 8:
        return 0.0
    a = a[-n:]
    b = b[-n:]
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 8:
        return 0.0
    a = a[mask]
    b = b[mask]
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def residual_momentum(etf_closes, market_closes, size_closes=None,
                      fit_window=120, score_window=60, skip=5):
    """Sum of recent regression residuals over their std.

    y ~ 1 + r_mkt + (r_size - r_mkt), fit on `fit_window` daily log
    returns ending `skip` days ago; score over the last
    `score_window` residuals of the fit.
    """
    y = log_returns(etf_closes)
    mkt = log_returns(market_closes)
    n = min(len(y), len(mkt))
    if n < 40:
        return 0.0
    y = y[-n:]
    mkt = mkt[-n:]
    cols = [np.ones(n), mkt]
    if size_closes is not None and len(size_closes) > 2:
        size = log_returns(size_closes)
        if len(size) >= n:
            cols.append(size[-n:] - mkt)
    X = np.column_stack(cols)
    end = n - int(skip)
    start = max(0, end - int(fit_window))
    if end - start < 40:
        return 0.0
    yy = y[start:end]
    xx = X[start:end]
    beta, _, _, _ = np.linalg.lstsq(xx, yy, rcond=None)
    resid = yy - xx.dot(beta)
    tail = resid[-int(score_window):]
    if len(tail) < 3:
        return 0.0
    sd = float(np.std(tail, ddof=1))
    if sd < 1e-12:
        return 0.0
    return float(np.sum(tail) / sd)


def trend_quality(closes, lookback=120):
    """Close relative to the rolling peak; 1.0 = at the high."""
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 5:
        return 0.0
    window = closes[-int(lookback):]
    peak = float(np.max(window))
    if peak <= 0:
        return 0.0
    return float(closes[-1] / peak)


def period_return(closes, days):
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) <= days:
        return 0.0
    prev = closes[-(days + 1)]
    if prev <= 0:
        return 0.0
    return float(closes[-1] / prev - 1.0)


def realized_vol(closes, days=20):
    rets = log_returns(closes)
    if len(rets) < 5:
        return 0.0
    tail = rets[-int(days):]
    return float(np.std(tail, ddof=1) * math.sqrt(252.0))


def crowding_points(closes, highs, lows, volumes, amounts=None):
    """0-4 crowding score. >=3 means the name cannot be opened.

    +1 vol20/vol60 > 2, +1 close/MA60 - 1 > 0.15,
    +1 20d corr(close, volume) < 0.10,
    +1 mean 20d (high-low)/prev_close > 0.04.
    """
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    n = min(len(closes), len(highs), len(lows), len(volumes))
    if n < 61:
        return 0
    closes = closes[-n:]
    highs = highs[-n:]
    lows = lows[-n:]
    volumes = volumes[-n:]
    points = 0
    v20 = float(np.mean(volumes[-20:]))
    v60 = float(np.mean(volumes[-60:]))
    if v60 > 0 and v20 / v60 > 2.0:
        points += 1
    ma60 = float(np.mean(closes[-60:]))
    if ma60 > 0 and closes[-1] / ma60 - 1.0 > 0.15:
        points += 1
    if _corr(closes[-20:], volumes[-20:]) < 0.10:
        points += 1
    prev_close = closes[-21:-1]
    amp = (highs[-20:] - lows[-20:]) / np.maximum(prev_close, 1e-8)
    if float(np.mean(amp)) > 0.04:
        points += 1
    return int(min(4, points))


def classify_state(breadth, med_vol, lockdown):
    if lockdown:
        return STATE_LOCK
    if breadth < 0.40 or med_vol > 0.40:
        return STATE_OFF
    if breadth >= 0.60 and med_vol <= 0.30:
        return STATE_ON
    return STATE_BAL


def growth_breadth(ret20_map, growth_codes):
    vals = [ret20_map[c] for c in growth_codes if c in ret20_map]
    if not vals:
        return 0.0
    return float(sum(1 for x in vals if x > 0)) / float(len(vals))


def median_vol(vol_map, codes):
    vals = [vol_map[c] for c in codes if c in vol_map and vol_map[c] > 0]
    if not vals:
        return 0.0
    return float(np.median(vals))


def mean_pairwise_corr(ret_map, codes):
    arrays = [ret_map[c] for c in codes if c in ret_map]
    if len(arrays) < 2:
        return 0.0
    n = min(len(a) for a in arrays)
    arrays = [np.asarray(a, dtype=float)[-n:] for a in arrays]
    corrs = []
    for i in range(len(arrays)):
        for j in range(i + 1, len(arrays)):
            value = _corr(arrays[i], arrays[j])
            if np.isfinite(value):
                corrs.append(value)
    if not corrs:
        return 0.0
    return float(np.mean(corrs))


def filter_correlated(ranked, ret60_map, threshold=0.65):
    """Greedy: keep a name only if corr with every kept name <= threshold."""
    selected = []
    for code in ranked:
        ok = True
        for held in selected:
            if _corr(ret60_map.get(code, []), ret60_map.get(held, [])) > threshold:
                ok = False
                break
        if ok:
            selected.append(code)
    return selected


def inverse_vol_weights(codes, vol_map, cap=0.40):
    if not codes:
        return {}
    inv = []
    for code in codes:
        vol = max(float(vol_map.get(code, 0.20)), 1e-4)
        inv.append(1.0 / vol)
    total = sum(inv)
    weights = {codes[i]: inv[i] / total for i in range(len(codes))}
    overflow = 0.0
    uncapped = []
    for code in codes:
        if weights[code] > cap:
            overflow += weights[code] - cap
            weights[code] = cap
        else:
            uncapped.append(code)
    if overflow > 0 and uncapped:
        room = sum(weights[c] for c in uncapped)
        if room > 0:
            for code in uncapped:
                weights[code] += overflow * (weights[code] / room)
    return weights


def scale_to_vol_target(weights, vol_map, target=0.12):
    """Scale weights down (never up) toward the vol target."""
    var = 0.0
    for code, weight in weights.items():
        vol = float(vol_map.get(code, 0.20))
        var += (weight * vol) ** 2
    port_vol = math.sqrt(max(var, 0.0))
    if port_vol <= 1e-8:
        return weights, 1.0
    scale = min(1.0, float(target) / port_vol)
    scaled = {code: weight * scale for code, weight in weights.items()}
    return scaled, scale


def crash_triggered(closes, single_day=0.08, three_day=0.08):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 4:
        return False
    if closes[-2] > 0 and (closes[-2] - closes[-1]) / closes[-2] >= single_day:
        return True
    if closes[-4] > 0 and (closes[-4] - closes[-1]) / closes[-4] >= three_day:
        return True
    return False


def trailing_stop_hit(close_px, high_water, pct=0.20):
    if high_water is None or high_water <= 0 or close_px is None:
        return False
    return float(close_px) <= float(high_water) * (1.0 - pct)


def build_targets(state, growth_ranked, div_ranked, vol_map,
                  growth_corr_high, div_all_negative, vol_target=0.12):
    """Sleeve weights -> per-ETF weights (cash is the remainder)."""
    g_w, d_w, c_w = SLEEVE_WEIGHTS[state]
    growth_ranked = list(growth_ranked or [])
    div_ranked = list(div_ranked or [])
    if state in (STATE_OFF, STATE_LOCK):
        growth_ranked = []
        g_w = 0.0
    if growth_corr_high and g_w > 0:
        freed = g_w * 0.5
        g_w -= freed
        d_w = min(0.80, d_w + freed)
        c_w = max(0.0, 1.0 - g_w - d_w)
        growth_ranked = growth_ranked[:1]
    if not growth_ranked and g_w > 0:
        d_w = min(0.80, d_w + g_w * 0.5)
        g_w = 0.0
        c_w = max(0.0, 1.0 - d_w)
    if div_all_negative:
        d_w = 0.0
        c_w = max(0.0, 1.0 - g_w)
    elif d_w < 0.25 and g_w > 0:
        take = min(0.25 - d_w, g_w)
        g_w -= take
        d_w += take

    g_n = 2 if g_w >= 0.50 else (1 if g_w > 0 else 0)
    d_n = 3 if d_w >= 0.60 else (2 if d_w > 0 else 0)
    g_pick = growth_ranked[:g_n]
    d_pick = div_ranked[:d_n]

    weights = {}
    if g_pick and g_w > 0:
        for code, weight in inverse_vol_weights(g_pick, vol_map).items():
            weights[code] = weight * g_w
    if d_pick and d_w > 0:
        for code, weight in inverse_vol_weights(d_pick, vol_map).items():
            weights[code] = weights.get(code, 0.0) + weight * d_w
    weights, _scale = scale_to_vol_target(weights, vol_map, target=vol_target)
    return weights


def apply_hysteresis(current, proposed, score_map, gap=1.20):
    """Keep incumbents unless a challenger beats them by `gap`."""
    current = list(current or [])
    proposed = list(proposed or [])
    if not current:
        return proposed
    limit = max(len(proposed), 1)
    kept = []
    for code in current:
        if code in proposed:
            if code not in kept:
                kept.append(code)
            continue
        best = None
        best_score = -1e18
        for cand in proposed:
            if cand in current or cand in kept:
                continue
            sc = float(score_map.get(cand, 0.0))
            if sc > best_score:
                best_score = sc
                best = cand
        old_score = float(score_map.get(code, 0.0))
        if best is not None and best_score > old_score * gap:
            kept.append(best)
        else:
            kept.append(code)
    for code in proposed:
        if code not in kept and len(kept) < limit:
            kept.append(code)
    ordered = [c for c in proposed if c in kept]
    for code in kept:
        if code not in ordered:
            ordered.append(code)
    return ordered[:limit]


def lot_shares(value, price, lot=100):
    if price is None or price <= 0 or value <= 0:
        return 0
    shares = int(value / price)
    return int(shares / lot) * lot


# ---------------------------------------------------------------------------
# PTrade lifecycle
# ---------------------------------------------------------------------------
def initialize(context):
    g.growth = list(GROWTH)
    g.diversifier = list(DIVERSIFIER)
    g.etf_pool = list(dict.fromkeys(g.growth + g.diversifier))
    g.market = "510300.SS"
    g.size = "510500.SS"
    g.bond = "511010.SS"
    g.cash_etf = "511880.SS"
    g.repo_code = "204001.SS"
    g.hist_count = 260
    g.corr_limit = 0.65
    g.corr_cluster = 0.75
    g.vol_target = 0.12
    g.hysteresis = 1.20
    g.trail_pct = 0.20
    g.lockdown_days = 5
    g.cash_reserve = 0.02
    g.premium_limit = 0.03
    g.min_weight = 0.04
    g.last_rebalance_week = None
    g.lockdown_left = 0
    g.last_target = {}
    g.pending_target = {}
    g.pending_orders = {}
    g.high_water = {}
    g.last_scores = {}
    g.last_state = STATE_BAL

    set_universe(g.etf_pool + [g.cash_etf])
    set_benchmark("000300.SS")
    if not is_trade():
        try:
            set_commission(commission_ratio=0.0003, min_commission=5)
            set_slippage(slippage=0.001)
            set_limit_mode(limit_mode="UNLIMITED")
        except Exception:
            pass

    run_daily(context, crash_overlay, time="14:45")
    run_daily(context, weekly_rebalance, time="14:50")
    # ALWAYS register the buy leg, in backtest and live alike.
    run_daily(context, rebalance_buy, time="14:54")
    if is_trade():
        run_daily(context, park_cash_in_repo, time="14:57")


def before_trading_start(context, data):
    # Drop stale order bookkeeping from the previous session.
    g.pending_orders = {}


def handle_data(context, data):
    current_dt = _current_dt(context)
    if current_dt is None:
        return
    hhmm = current_dt.strftime("%H:%M")
    if hhmm in ("09:35", "13:05"):
        crash_overlay(context, data)


def after_trading_end(context, data):
    if g.lockdown_left > 0:
        g.lockdown_left -= 1
    log.info("日终 状态=%s 锁仓剩余=%d 资产=%.2f 现金=%.2f 持仓=%s 目标=%s" % (
        str(g.last_state),
        int(g.lockdown_left),
        context.portfolio.portfolio_value,
        context.portfolio.cash,
        str(_held_etfs(context)),
        str(sorted(g.last_target.keys())),
    ))


def weekly_rebalance(context, data=None):
    today = _current_dt(context)
    if today is not None and g.last_rebalance_week == _week_key(today):
        return
    hist_map = _load_histories(g.etf_pool, g.hist_count)
    if len(hist_map) < 6:
        log.info("历史行情不足，本次不调仓")
        return
    target = _compute_targets(hist_map, _held_etfs(context))
    g.last_target = dict(target)
    g.pending_target = dict(target)
    if today is not None:
        g.last_rebalance_week = _week_key(today)
    _align_positions(context, target)


def crash_overlay(context, data=None):
    """Daily overlay: market crash + 20% trailing stop on growth holds."""
    held = _held_etfs(context)
    if not held:
        return
    growth_held = [c for c in held if c in g.growth]
    hist_map = _load_histories(list(dict.fromkeys(growth_held + [g.market])), 30)
    flatten = False
    mkt = hist_map.get(g.market)
    if mkt is not None and crash_triggered(mkt["close"], 0.06, 0.08):
        flatten = True
    for code in growth_held:
        bars = hist_map.get(code)
        if bars is None or len(bars["close"]) == 0:
            continue
        px = float(bars["close"][-1])
        water = g.high_water.get(code)
        if water is None or px > water:
            g.high_water[code] = px
        elif trailing_stop_hit(px, water, g.trail_pct):
            flatten = True
        if crash_triggered(bars["close"], 0.08, 0.08):
            flatten = True
    if not flatten:
        return
    g.lockdown_left = g.lockdown_days
    g.last_state = STATE_LOCK
    target = {}
    div_hist = _load_histories(
        list(dict.fromkeys(g.diversifier + [g.market, g.size, g.bond])),
        g.hist_count,
    )
    if div_hist:
        snap = _score_universe(div_hist)
        ranked = _eligible(g.diversifier, snap, held, require_trend=False)
        if ranked:
            target[ranked[0]] = 0.60
    g.last_target = dict(target)
    g.pending_target = dict(target)
    log.info("崩盘/回撤 overlay 触发 lockdown 目标=%s" % str(target))
    _align_positions(context, target)


def rebalance_buy(context, data=None):
    """14:54 buy leg; runs every day so 14:50 sells settle into buys."""
    if is_trade() and g.pending_orders:
        log.info("仍有未完成委托，推迟买入")
        return
    target = dict(g.pending_target or g.last_target or {})
    if not target:
        return
    _align_positions(context, target)


def park_cash_in_repo(context, data=None):
    """Live only: lend idle cash via 1-day reverse repo (sell direction)."""
    if not is_trade():
        return
    if g.pending_orders:
        return
    cash = float(context.portfolio.cash)
    if cash < 1000:
        return
    amount = int(math.floor(cash / 1000.0) * 10)
    if amount < 10:
        return
    order_id = order(g.repo_code, -amount)
    _remember_order(g.repo_code, order_id)


def on_order_response(context, order_list):
    if not order_list:
        return
    for order_info in order_list:
        status = str(_field(order_info, "status", ""))
        sid = _normalize_security_code(
            _field(order_info, "stock_code")
            or _field(order_info, "sid")
            or _field(order_info, "symbol")
        )
        if status in ("5", "6", "8", "9"):
            _clear_pending_order(sid)
        if status == "9":
            log.info("废单 %s 原因=%s" % (
                str(sid), str(_field(order_info, "error_info"))))


def on_trade_response(context, trade_list):
    if not trade_list:
        return
    for trade_info in trade_list:
        if str(_field(trade_info, "status", "")) == "8":
            _clear_pending_order(_field(trade_info, "stock_code"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _field(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _normalize_security_code(code):
    if code is None:
        return None
    code = str(code)
    if code.endswith(".XSHG"):
        return code[:-5] + ".SS"
    if code.endswith(".XSHE"):
        return code[:-5] + ".SZ"
    return code


def _remember_order(code, order_id):
    if order_id is None:
        return
    code = _normalize_security_code(code)
    if code is not None:
        g.pending_orders[code] = str(order_id)


def _clear_pending_order(code):
    code = _normalize_security_code(code)
    if code in g.pending_orders:
        del g.pending_orders[code]


def _has_pending_order(code):
    # Backtest fills are synchronous; only gate on pendings in live.
    if not is_trade():
        return False
    return _normalize_security_code(code) in g.pending_orders


def _series(df, field):
    if df is None:
        return np.array([])
    if hasattr(df, "get"):
        col = df.get(field)
        if col is None and field == "money":
            col = df.get("amount")
        if col is None:
            return np.array([])
        return np.asarray(col, dtype=float)
    return np.array([])


def _load_one(code, count):
    """get_history for a single symbol, fq='pre', include=False."""
    try:
        df = get_history(
            count,
            "1d",
            ["open", "high", "low", "close", "volume", "money"],
            security_list=code,
            fq="pre",
            include=False,
        )
    except TypeError:
        try:
            df = get_history(count, "1d",
                             ["open", "high", "low", "close", "volume"], code)
        except Exception:
            return None
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    bars = {
        "open": _series(df, "open"),
        "high": _series(df, "high"),
        "low": _series(df, "low"),
        "close": _series(df, "close"),
        "volume": _series(df, "volume"),
        "money": _series(df, "money"),
    }
    if len(bars["close"]) == 0:
        return None
    if len(bars["money"]) == 0:
        bars["money"] = bars["close"] * bars["volume"]
    return bars


def _load_histories(codes, count):
    out = {}
    for code in codes:
        bars = _load_one(code, count)
        if bars is not None:
            out[code] = bars
    return out


def _current_dt(context):
    dt = getattr(context, "current_dt", None)
    if dt is not None:
        return dt
    blotter = getattr(context, "blotter", None)
    return getattr(blotter, "current_dt", None)


def _week_key(dt):
    try:
        iso = dt.isocalendar()
        return (int(iso[0]), int(iso[1]))
    except Exception:
        return (dt.year, dt.timetuple().tm_yday // 7)


def _held_etfs(context):
    held = []
    try:
        positions = get_positions()
    except Exception:
        positions = None
    if not positions:
        return held
    if hasattr(positions, "items"):
        items = list(positions.items())
    elif isinstance(positions, (list, tuple)):
        items = [(_field(p, "sid") or _field(p, "security"), p)
                 for p in positions]
    else:
        items = []
    tradable = set(g.etf_pool + [g.cash_etf])
    for code, pos in items:
        sid = _normalize_security_code(code or _field(pos, "sid"))
        amount = int(_field(pos, "amount", 0) or 0)
        if sid and amount > 0 and sid in tradable:
            held.append(sid)
    return held


def _position_amount(code):
    try:
        pos = get_position(code)
    except Exception:
        pos = None
    return int(_field(pos, "amount", 0) or 0)


def _current_price(code):
    bars = _load_one(code, 5)
    if bars is None or len(bars["close"]) == 0:
        return None
    return float(bars["close"][-1])


def _etf_premium_too_high(code, price):
    """QDII (513*) premium veto via get_etf_info; fail-open."""
    if not is_trade():
        return False
    if not str(code).startswith("513"):
        return False
    try:
        info = get_etf_info(code)
    except Exception:
        return False
    if not info:
        return False
    iopv = (_field(info, "iopv") or _field(info, "IOPV")
            or _field(info, "nav") or _field(info, "unit_nav"))
    try:
        iopv = float(iopv)
    except Exception:
        return False
    if iopv <= 0 or price is None:
        return False
    return (price / iopv - 1.0) >= g.premium_limit


def _limit_blocked(code):
    """check_limit veto, always fail-open."""
    try:
        res = check_limit(code)
    except Exception:
        return False
    try:
        if isinstance(res, dict):
            return int(res.get(code, 0) or 0) != 0
    except Exception:
        return False
    return False


def _lot_for(code):
    return 1 if str(code).startswith("51188") else 100


def _score_universe(hist_map):
    market = hist_map.get(g.market)
    size = hist_map.get(g.size)
    bond = hist_map.get(g.bond)
    mkt_c = None if market is None else market["close"]
    size_c = None if size is None else size["close"]
    bond_ret = 0.0 if bond is None else period_return(bond["close"], 63)
    scores = {}
    tq_map = {}
    ret20 = {}
    ret63 = {}
    vols = {}
    ret60_map = {}
    crowd = {}
    for code, bars in hist_map.items():
        close = bars["close"]
        if mkt_c is None or len(close) < 70:
            continue
        scores[code] = residual_momentum(close, mkt_c, size_c)
        tq_map[code] = trend_quality(close)
        ret20[code] = period_return(close, 20)
        ret63[code] = period_return(close, 63)
        vols[code] = realized_vol(close, 20)
        ret60_map[code] = log_returns(close)[-60:]
        crowd[code] = crowding_points(
            close, bars["high"], bars["low"], bars["volume"], bars.get("money"))
    return {
        "scores": scores,
        "tq": tq_map,
        "ret20": ret20,
        "ret63": ret63,
        "vols": vols,
        "ret60": ret60_map,
        "crowd": crowd,
        "bond_ret": bond_ret,
        "mkt_close": mkt_c,
    }


def _eligible(codes, snap, held, require_trend):
    """Rank by residual momentum after veto gates.

    Crowding >=3 blocks new opens only; incumbents may stay.
    Growth additionally needs trend quality and absolute momentum
    above the bond return; diversifiers just need a positive 63d.
    """
    held = set(held or [])
    ranked = []
    for code in codes:
        score = snap["scores"].get(code)
        if score is None:
            continue
        if snap["crowd"].get(code, 0) >= 3 and code not in held:
            continue
        ret63 = snap["ret63"].get(code, 0.0)
        if ret63 <= 0:
            continue
        if require_trend:
            if snap["tq"].get(code, 0.0) < 0.90:
                continue
            if ret63 <= snap["bond_ret"]:
                continue
        ranked.append((code, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked]


def _compute_targets(hist_map, current_held):
    snap = _score_universe(hist_map)
    g.last_scores = dict(snap["scores"])
    breadth = growth_breadth(snap["ret20"], g.growth)
    med_vol = median_vol(snap["vols"], g.growth)
    if snap["mkt_close"] is not None and crash_triggered(
            snap["mkt_close"], 0.06, 0.08):
        g.lockdown_left = max(g.lockdown_left, g.lockdown_days)
    state = classify_state(breadth, med_vol, g.lockdown_left > 0)
    g.last_state = state

    growth_all = _eligible(g.growth, snap, current_held, require_trend=True)
    div_all = _eligible(g.diversifier, snap, current_held, require_trend=False)
    # Cluster check on the raw top-5 before the pairwise filter thins it.
    cluster = mean_pairwise_corr(snap["ret60"], growth_all[:5]) > g.corr_cluster
    growth_ranked = filter_correlated(growth_all, snap["ret60"], g.corr_limit)
    div_ranked = filter_correlated(div_all, snap["ret60"], g.corr_limit)

    div_all_neg = True
    for code in g.diversifier:
        if snap["ret63"].get(code, -1.0) > 0:
            div_all_neg = False
            break

    raw_weights = build_targets(
        state, growth_ranked, div_ranked, snap["vols"],
        cluster, div_all_neg, g.vol_target)
    proposed = [c for c, w in sorted(raw_weights.items(), key=lambda kv: -kv[1])
                if w >= g.min_weight]
    held_keep = [c for c in current_held if c in raw_weights]
    stable = apply_hysteresis(held_keep, proposed, snap["scores"], g.hysteresis)
    weights = {c: raw_weights[c] for c in stable if c in raw_weights}
    log.info("state=%s breadth=%.2f medvol=%.2f cluster=%s growth=%s div=%s target=%s" % (
        state, breadth, med_vol, str(cluster), str(growth_ranked[:4]),
        str(div_ranked[:4]), str(weights)))
    return weights


def _align_positions(context, target_weights):
    """Sell leg first; buy leg only when no fresh sells are in flight."""
    targets = {c: w for c, w in (target_weights or {}).items() if w > 0.01}
    held = _held_etfs(context)
    sold = False
    for code in held:
        if code in targets or _has_pending_order(code):
            continue
        order_id = order_target(code, 0)
        if order_id is not None:
            sold = True
            _remember_order(code, order_id)
            g.high_water.pop(code, None)
            log.info("卖出非目标 %s" % code)
    if not targets:
        return
    if sold and is_trade():
        log.info("本轮已提交卖单，等待资金同步后由 14:54 买入")
        return

    total_value = float(context.portfolio.portfolio_value) * (1.0 - g.cash_reserve)
    cash_left = float(context.portfolio.cash) * (1.0 - g.cash_reserve)
    for code in sorted(targets, key=lambda c: -targets[c]):
        if _has_pending_order(code):
            continue
        price = _current_price(code)
        if price is None or price <= 0:
            continue
        lot = _lot_for(code)
        current_amount = _position_amount(code)
        diff = total_value * targets[code] - current_amount * price
        if diff < 0:
            shares = min(lot_shares(-diff, price, lot), current_amount)
            shares = int(shares / lot) * lot
            if shares >= lot:
                order_id = order(code, -shares)
                if order_id is not None:
                    _remember_order(code, order_id)
                    log.info("减仓 %s 数量=%d" % (code, shares))
            continue
        if diff < price * lot:
            continue
        if _etf_premium_too_high(code, price):
            log.info("溢价过高，跳过 %s" % code)
            continue
        if _limit_blocked(code):
            log.info("涨跌停限制，跳过 %s" % code)
            continue
        shares = min(lot_shares(diff, price, lot),
                     lot_shares(cash_left, price, lot))
        if shares < lot:
            continue
        order_id = order(code, shares)
        if order_id is not None:
            _remember_order(code, order_id)
            cash_left -= shares * price
            water = g.high_water.get(code)
            if water is None or price > water:
                g.high_water[code] = price
            log.info("买入 %s 数量=%d 权重=%.2f" % (code, shares, targets[code]))
