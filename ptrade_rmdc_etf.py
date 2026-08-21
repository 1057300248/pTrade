# -*- coding: utf-8 -*-
"""
RMDC: Residual-Momentum De-Crowding ETF rotation for 国金 PTrade.

From-scratch 2026 design. Not a clone of regime_etf_rotation.py.

- Residual momentum vs 沪深300 + 中证500 size spread (beta/size stripped)
- Huatai-style 0-4 crowding veto on OHLCV
- Breadth + median-vol state machine (not 510300 vs MA60)
- Correlation filter so 半导体/创业板/科创50 cannot be one trade
- Growth vs diversifier sleeves, inverse-vol weights, 12% vol target
- Weekly rebalance, daily crash/trailing-stop overlay
- Python 3.11 on 国金; still avoid f-strings for SimTradeLab/paste safety

Paste this whole file into 国金 PTrade. Use minute mode to keep 14:45/14:50/14:54.
"""
import math
import numpy as np


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

SLEEVE_WEIGHTS = {
    STATE_ON: (0.70, 0.25, 0.05),
    STATE_BAL: (0.40, 0.45, 0.15),
    STATE_OFF: (0.00, 0.65, 0.35),
    STATE_LOCK: (0.00, 0.30, 0.70),
}


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
        size = size[-n:]
        if len(size) == n:
            cols.append(size - mkt)
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
    sd = float(np.std(tail, ddof=1)) if len(tail) > 2 else 0.0
    if sd < 1e-12:
        return 0.0
    return float(np.sum(tail) / sd)


def trend_quality(closes, lookback=120):
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
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    n = min(len(closes), len(highs), len(lows), len(volumes))
    if n < 60:
        return 0
    closes = closes[-n:]
    highs = highs[-n:]
    lows = lows[-n:]
    volumes = volumes[-n:]
    if amounts is None:
        amounts = closes * volumes
    else:
        amounts = np.asarray(amounts, dtype=float)[-n:]
    points = 0
    v20 = float(np.mean(volumes[-20:]))
    v60 = float(np.median(volumes[-60:]))
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
    vals = []
    for code in growth_codes:
        if code in ret20_map:
            vals.append(ret20_map[code])
    if not vals:
        return 0.0
    return float(sum(1 for x in vals if x > 0) / float(len(vals)))


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
    arrays = [a[-n:] for a in arrays]
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


def pick_sleeve(ranked, count):
    return list(ranked[:count])


def build_targets(state, growth_ranked, div_ranked, vol_map,
                  growth_corr_high, div_all_negative, vol_target=0.12):
    g_w, d_w, c_w = SLEEVE_WEIGHTS[state]
    if growth_corr_high:
        g_w = g_w * 0.5
        d_w = min(0.80, d_w + 0.15)
        c_w = max(0.0, 1.0 - g_w - d_w)
        growth_ranked = growth_ranked[:1]
    if state in (STATE_OFF, STATE_LOCK):
        growth_ranked = []
        g_w = 0.0
        d_w, c_w = SLEEVE_WEIGHTS[state][1], SLEEVE_WEIGHTS[state][2]
    if not growth_ranked:
        g_w = 0.0
        d_w = d_w + SLEEVE_WEIGHTS[state][0] * 0.5
        c_w = max(0.0, 1.0 - d_w)
    if div_all_negative:
        d_w = 0.0
        c_w = 1.0 - g_w
    elif d_w < 0.25 and g_w > 0:
        extra = 0.25 - d_w
        take = min(extra, g_w)
        g_w -= take
        d_w += take

    g_pick = pick_sleeve(growth_ranked, 2 if g_w >= 0.50 else (1 if g_w > 0 else 0))
    d_n = 3 if d_w >= 0.60 else (2 if d_w > 0 else 0)
    d_pick = pick_sleeve(div_ranked, d_n)

    weights = {}
    if g_pick and g_w > 0:
        inner = inverse_vol_weights(g_pick, vol_map)
        for code, weight in inner.items():
            weights[code] = weight * g_w
    if d_pick and d_w > 0:
        inner = inverse_vol_weights(d_pick, vol_map)
        for code, weight in inner.items():
            weights[code] = weights.get(code, 0.0) + weight * d_w
    weights, _scale = scale_to_vol_target(weights, vol_map, target=vol_target)
    return weights


def apply_hysteresis(current, proposed, score_map, gap=1.20):
    current = list(current or [])
    proposed = list(proposed or [])
    if not current:
        return proposed
    kept = []
    for code in current:
        if code in proposed:
            kept.append(code)
            continue
        best_new = None
        best_score = -1e9
        for cand in proposed:
            if cand in current or cand in kept:
                continue
            sc = float(score_map.get(cand, 0.0))
            if sc > best_score:
                best_score = sc
                best_new = cand
        old_score = float(score_map.get(code, 0.0))
        if best_new is not None and best_score > old_score * gap:
            kept.append(best_new)
        else:
            kept.append(code)
    for code in proposed:
        if code not in kept and len(kept) < max(len(proposed), len(current)):
            kept.append(code)
    ordered = [c for c in proposed if c in kept]
    for c in kept:
        if c not in ordered:
            ordered.append(c)
    return ordered[: max(len(proposed), 1)]


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
    g.hist_count = 260
    g.corr_limit = 0.65
    g.corr_cluster = 0.75
    g.vol_target = 0.12
    g.hysteresis = 1.20
    g.trail_pct = 0.20
    g.lockdown_days = 5
    g.cash_reserve = 0.02
    g.reverse_repo = ["131810.SZ", "204001.SS"]
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
        set_commission(commission_ratio=0.0003, min_commission=5)
        set_slippage(slippage=0.001)
        set_limit_mode(limit_mode="UNLIMITED")

    run_daily(context, crash_overlay, time="14:45")
    run_daily(context, weekly_rebalance, time="14:50")
    if is_trade():
        run_daily(context, rebalance_buy, time="14:54")
        run_daily(context, park_cash_in_repo, time="14:57")


def before_trading_start(context, data):
    g.pending_orders = {}


def handle_data(context, data):
    current_dt = getattr(context.blotter, "current_dt", None)
    if current_dt is None:
        return
    hhmm = current_dt.strftime("%H:%M")
    if hhmm in ("09:35", "13:05"):
        crash_overlay(context, data)


def after_trading_end(context, data):
    log.info("日终 状态=%s 资产=%.2f 现金=%.2f 持仓=%s 目标=%s" % (
        str(g.last_state),
        context.portfolio.portfolio_value,
        context.portfolio.cash,
        str(_held_etfs(context)),
        str(sorted(g.last_target.keys())),
    ))


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
    return _normalize_security_code(code) in g.pending_orders


def on_order_response(context, order_list):
    if not order_list:
        return
    for order_info in order_list:
        status = str(order_info.get("status", ""))
        sid = _normalize_security_code(
            order_info.get("stock_code") or order_info.get("sid") or order_info.get("symbol")
        )
        if status in ("5", "6", "8", "9"):
            _clear_pending_order(sid)
        if status == "9":
            log.info("废单 %s 原因=%s" % (str(sid), str(order_info.get("error_info"))))


def on_trade_response(context, trade_list):
    if not trade_list:
        return
    for trade_info in trade_list:
        sid = _normalize_security_code(trade_info.get("stock_code"))
        if str(trade_info.get("status", "")) == "8":
            _clear_pending_order(sid)


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
        df = get_history(count, "1d", ["open", "high", "low", "close", "volume"], code)
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    bars = {
        "close": _series(df, "close"),
        "open": _series(df, "open"),
        "high": _series(df, "high"),
        "low": _series(df, "low"),
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
    return getattr(context, "current_dt", None) or getattr(context.blotter, "current_dt", None)


def _week_key(dt):
    try:
        iso = dt.isocalendar()
        return (int(iso[0]), int(iso[1]))
    except Exception:
        return (dt.year, dt.timetuple().tm_yday // 7)


def _held_etfs(context):
    held = []
    positions = get_positions()
    if not positions:
        return held
    items = positions.items() if hasattr(positions, "items") else []
    if not items and isinstance(positions, (list, tuple)):
        items = [(getattr(p, "sid", None) or getattr(p, "security", None), p) for p in positions]
    for code, pos in items:
        amount = int(getattr(pos, "amount", 0) or 0)
        sid = _normalize_security_code(code or getattr(pos, "sid", None))
        if sid and amount > 0 and sid in g.etf_pool + [g.cash_etf]:
            held.append(sid)
    return held


def _current_price(code):
    bars = _load_one(code, 5)
    if bars is None or len(bars["close"]) == 0:
        return None
    return float(bars["close"][-1])


def _etf_premium_too_high(code, price):
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
    iopv = info.get("iopv") or info.get("IOPV") or info.get("nav")
    try:
        iopv = float(iopv)
    except Exception:
        return False
    if iopv <= 0 or price is None:
        return False
    return (price / iopv - 1.0) >= 0.03


def _score_universe(hist_map):
    market = hist_map.get(g.market)
    size = hist_map.get(g.size)
    bond = hist_map.get(g.bond)
    mkt_c = None if market is None else market["close"]
    size_c = None if size is None else size["close"]
    bond_ret = 0.0
    if bond is not None:
        bond_ret = period_return(bond["close"], 63)
    scores = {}
    ret20 = {}
    ret63 = {}
    vols = {}
    ret60_map = {}
    crowd = {}
    tq_map = {}
    for code, bars in hist_map.items():
        close = bars["close"]
        if len(close) < 70 or mkt_c is None:
            continue
        scores[code] = residual_momentum(close, mkt_c, size_c)
        tq_map[code] = trend_quality(close)
        ret20[code] = period_return(close, 20)
        ret63[code] = period_return(close, 63)
        vols[code] = realized_vol(close, 20)
        ret60_map[code] = log_returns(close)[-60:]
        crowd[code] = crowding_points(
            close, bars["high"], bars["low"], bars["volume"], bars.get("money")
        )
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


def _eligible(codes, snap, require_trend=True):
    ranked = []
    for code in codes:
        score = snap["scores"].get(code)
        if score is None:
            continue
        if snap["crowd"].get(code, 0) >= 3:
            continue
        if require_trend and snap["tq"].get(code, 0) < 0.90:
            continue
        if snap["ret63"].get(code, 0) <= 0:
            continue
        if snap["ret63"].get(code, 0) < snap["bond_ret"]:
            continue
        ranked.append((code, score * max(snap["tq"].get(code, 0), 0.01)))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked]


def _compute_targets(hist_map, current_held):
    snap = _score_universe(hist_map)
    g.last_scores = dict(snap["scores"])
    breadth = growth_breadth(snap["ret20"], g.growth)
    med_vol = median_vol(snap["vols"], g.growth)
    lockdown = g.lockdown_left > 0
    if snap["mkt_close"] is not None and crash_triggered(snap["mkt_close"], 0.06, 0.08):
        lockdown = True
        g.lockdown_left = max(g.lockdown_left, g.lockdown_days)
    state = classify_state(breadth, med_vol, lockdown)
    g.last_state = state

    growth_ranked = _eligible(g.growth, snap, require_trend=True)
    div_ranked = _eligible(g.diversifier, snap, require_trend=False)
    growth_ranked = filter_correlated(growth_ranked, snap["ret60"], g.corr_limit)
    div_ranked = filter_correlated(div_ranked, snap["ret60"], g.corr_limit)

    top5 = growth_ranked[:5]
    cluster = mean_pairwise_corr(snap["ret60"], top5) > g.corr_cluster
    div_all_neg = True
    for code in g.diversifier:
        if snap["ret63"].get(code, -1) > 0:
            div_all_neg = False
            break

    raw_weights = build_targets(
        state, growth_ranked, div_ranked, snap["vols"],
        cluster, div_all_neg, g.vol_target,
    )
    proposed = [c for c, w in sorted(raw_weights.items(), key=lambda x: -x[1]) if w >= 0.04]
    held_keep = [c for c in current_held if c in raw_weights]
    stable = apply_hysteresis(held_keep, proposed, snap["scores"], g.hysteresis)
    weights = {c: raw_weights[c] for c in stable if c in raw_weights}
    if weights:
        total = sum(weights.values())
        if total > 0:
            weights = {c: w / total * sum(raw_weights.get(x, 0) for x in weights) for c, w in weights.items()}
    log.info("state=%s breadth=%.2f medvol=%.2f cluster=%s growth=%s div=%s target=%s" % (
        state, breadth, med_vol, str(cluster), str(growth_ranked[:4]),
        str(div_ranked[:4]), str(weights),
    ))
    return weights


def weekly_rebalance(context, data=None):
    today = _current_dt(context)
    if today is not None:
        week = _week_key(today)
        if g.last_rebalance_week == week:
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
    if g.lockdown_left > 0:
        g.lockdown_left -= 1
    _align_positions(context, target)


def crash_overlay(context, data=None):
    held = _held_etfs(context)
    if not held:
        return
    hist_map = _load_histories(held + [g.market], 30)
    flatten = False
    for code in held:
        if code in g.diversifier or code == g.cash_etf:
            continue
        bars = hist_map.get(code)
        px = None if bars is None or len(bars["close"]) == 0 else float(bars["close"][-1])
        if bars is not None and crash_triggered(bars["close"], 0.08, 0.08):
            flatten = True
        water = g.high_water.get(code)
        if px is not None:
            if water is None or px > water:
                g.high_water[code] = px
            elif trailing_stop_hit(px, water, g.trail_pct):
                flatten = True
    mkt = hist_map.get(g.market)
    if mkt is not None and crash_triggered(mkt["close"], 0.06, 0.08):
        flatten = True
    if not flatten:
        return
    g.lockdown_left = g.lockdown_days
    g.last_state = STATE_LOCK
    target = {}
    hist_div = _load_histories(g.diversifier, g.hist_count)
    snap = _score_universe(hist_div) if hist_div else None
    if snap:
        ranked = _eligible(g.diversifier, snap, require_trend=False)
        if ranked:
            target[ranked[0]] = 0.60
    g.last_target = dict(target)
    g.pending_target = dict(target)
    log.info("crash/trailing overlay lockdown target=%s" % str(target))
    _align_positions(context, target)


def rebalance_buy(context, data=None):
    if g.pending_orders:
        log.info("仍有未完成委托，推迟买入")
        return
    _align_positions(context, dict(g.pending_target or g.last_target or {}))


def park_cash_in_repo(context, data=None):
    if not is_trade():
        return
    if g.pending_orders:
        return
    cash = float(context.portfolio.cash)
    if cash < 10000:
        return
    code = "204001.SS"
    amount = int(math.floor(cash / 1000.0) * 10)
    if amount >= 10:
        order_id = order(code, amount)
        _remember_order(code, order_id)


def _align_positions(context, target_weights):
    if target_weights is None:
        target_weights = {}
    target_codes = [c for c, w in target_weights.items() if w > 0.01]
    held = _held_etfs(context)
    sell_submitted = False
    for code in held:
        if code not in target_codes and not _has_pending_order(code):
            order_id = order_target(code, 0)
            if order_id is not None:
                sell_submitted = True
                _remember_order(code, order_id)
                g.high_water.pop(code, None)
                log.info("卖出非目标 %s" % code)

    if not target_codes:
        return
    if sell_submitted:
        log.info("本轮已提交卖单，等待资金同步后再买入")
        return

    value = float(context.portfolio.portfolio_value) * (1.0 - g.cash_reserve)
    available_cash = float(context.portfolio.cash) * (1.0 - g.cash_reserve)
    for code in target_codes:
        if _has_pending_order(code):
            continue
        price = _current_price(code)
        if price is None or price <= 0:
            continue
        if _etf_premium_too_high(code, price):
            log.info("溢价过高，跳过 %s" % code)
            continue
        try:
            check_limit(code)
        except Exception:
            pass
        weight = float(target_weights.get(code, 0.0))
        target_value = value * weight
        pos = get_position(code)
        current_amount = 0 if pos is None else int(getattr(pos, "amount", 0) or 0)
        current_value = current_amount * price
        diff = target_value - current_value
        lot = 1 if str(code).startswith("51188") else 100
        if diff < 0:
            shares = lot_shares(-diff, price, lot)
            sell_amount = min(shares, current_amount)
            if lot > 1:
                sell_amount = int(sell_amount / lot) * lot
            if sell_amount >= lot:
                order_id = order(code, -sell_amount)
                if order_id is not None:
                    _remember_order(code, order_id)
                    log.info("减仓 %s 数量=%d" % (code, sell_amount))
            continue
        if diff < price * lot:
            continue
        desired = lot_shares(diff, price, lot)
        cash_shares = lot_shares(available_cash, price, lot)
        shares = min(desired, cash_shares)
        if shares < lot:
            continue
        order_id = order(code, shares)
        if order_id is not None:
            _remember_order(code, order_id)
            available_cash -= shares * price
            water = g.high_water.get(code)
            if water is None or price > water:
                g.high_water[code] = price
            log.info("买入 %s 数量=%d 权重=%.2f" % (code, shares, weight))
