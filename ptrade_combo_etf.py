# -*- coding: utf-8 -*-
"""
Combo ETF: residual momentum plus volatility-adjusted absolute momentum.

This is a live 国金 PTrade strategy. Run it in minute mode so the 09:35,
13:05, 14:45, 14:50, 14:54 and 14:57 callbacks can fire.

The ranking score is:
    0.6 * residual_momentum + 0.4 * (63-day return / 20-day annualised vol)

PTrade compatibility:
- Python 3.11 and numpy only; no pandas, sklearn, network, os or sys.
- get_history is called once per symbol with fq="pre", include=False.
- Execution uses order/order_target and 100-share ETF lots.
- The SimTradeLab broker setting is "auto", not "guosheng".
"""
import numpy as np


# QDII funds (513*) are diversifiers only.
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

# (growth, diversifier, cash)
SLEEVE_WEIGHTS = {
    STATE_ON: (0.85, 0.12, 0.03),
    STATE_BAL: (0.55, 0.35, 0.10),
    STATE_OFF: (0.15, 0.55, 0.30),
    STATE_LOCK: (0.00, 0.40, 0.60),
}


# ---------------------------------------------------------------------------
# Pure quant functions
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
    if int(mask.sum()) < 8:
        return 0.0
    a = a[mask]
    b = b[mask]
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def residual_momentum(etf_closes, market_closes, size_closes=None,
                      fit_window=120, score_window=60, skip=5):
    """Return residual sum/std from a market and size-spread OLS."""
    y = log_returns(etf_closes)
    market = log_returns(market_closes)
    n = min(len(y), len(market))
    if n < 40:
        return 0.0
    y = y[-n:]
    market = market[-n:]
    columns = [np.ones(n), market]
    if size_closes is not None and len(size_closes) > 2:
        size = log_returns(size_closes)
        if len(size) >= n:
            columns.append(size[-n:] - market)
    x = np.column_stack(columns)
    end = n - int(skip)
    start = max(0, end - int(fit_window))
    if end - start < 40:
        return 0.0
    yy = y[start:end]
    xx = x[start:end]
    beta, _, _, _ = np.linalg.lstsq(xx, yy, rcond=None)
    residuals = yy - xx.dot(beta)
    tail = residuals[-int(score_window):]
    if len(tail) < 3:
        return 0.0
    std = float(np.std(tail, ddof=1))
    if std < 1e-12:
        return 0.0
    return float(np.sum(tail) / std)


def combined_score(residual_score, mom63, vol20):
    """Blend residual momentum with 63-day momentum per unit of vol."""
    residual_score = float(residual_score)
    mom63 = float(mom63)
    vol20 = float(vol20)
    risk_adjusted = 0.0
    if np.isfinite(vol20) and vol20 > 1e-12:
        risk_adjusted = mom63 / vol20
    return float(0.6 * residual_score + 0.4 * risk_adjusted)


def trend_quality(closes, lookback=120):
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
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
    if len(closes) <= int(days):
        return 0.0
    previous = float(closes[-(int(days) + 1)])
    if previous <= 0:
        return 0.0
    return float(closes[-1] / previous - 1.0)


def realized_vol(closes, days=20):
    returns = log_returns(closes)
    if len(returns) < 5:
        return 0.0
    tail = returns[-int(days):]
    return float(np.std(tail, ddof=1) * np.sqrt(252.0))


def crowding_points(closes, highs, lows, volumes, amounts=None):
    """Return a 0-4 crowding score; all four points block a new open."""
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
    volume20 = float(np.mean(volumes[-20:]))
    volume60 = float(np.mean(volumes[-60:]))
    if volume60 > 0 and volume20 / volume60 > 2.0:
        points += 1
    ma60 = float(np.mean(closes[-60:]))
    if ma60 > 0 and closes[-1] / ma60 - 1.0 > 0.15:
        points += 1
    if _corr(closes[-20:], volumes[-20:]) < 0.10:
        points += 1
    previous = closes[-21:-1]
    amplitude = (highs[-20:] - lows[-20:]) / np.maximum(previous, 1e-8)
    if float(np.mean(amplitude)) > 0.04:
        points += 1
    return int(min(4, points))


def classify_state(breadth, med_vol, lockdown):
    if lockdown:
        return STATE_LOCK
    if breadth >= 0.50 and med_vol <= 0.35:
        return STATE_ON
    if breadth < 0.35 or med_vol > 0.45:
        return STATE_OFF
    return STATE_BAL


def growth_breadth(ret20_map, growth_codes):
    values = [ret20_map[code] for code in growth_codes if code in ret20_map]
    if not values:
        return 0.0
    positive = sum(1 for value in values if value > 0)
    return float(positive) / float(len(values))


def median_vol(vol_map, codes):
    values = [
        vol_map[code] for code in codes
        if code in vol_map and vol_map[code] > 0
    ]
    if not values:
        return 0.0
    return float(np.median(values))


def mean_pairwise_corr(ret_map, codes):
    arrays = [ret_map[code] for code in codes if code in ret_map]
    if len(arrays) < 2:
        return 0.0
    n = min(len(values) for values in arrays)
    arrays = [np.asarray(values, dtype=float)[-n:] for values in arrays]
    correlations = []
    for left in range(len(arrays)):
        for right in range(left + 1, len(arrays)):
            value = _corr(arrays[left], arrays[right])
            if np.isfinite(value):
                correlations.append(value)
    if not correlations:
        return 0.0
    return float(np.mean(correlations))


def filter_correlated(ranked, ret60_map, threshold=0.70):
    """Greedily keep names no more correlated than the threshold."""
    selected = []
    for code in ranked:
        allowed = True
        for held in selected:
            if _corr(ret60_map.get(code, []),
                     ret60_map.get(held, [])) > threshold:
                allowed = False
                break
        if allowed:
            selected.append(code)
    return selected


def inverse_vol_weights(codes, vol_map, cap=1.0):
    if not codes:
        return {}
    inverse = []
    for code in codes:
        vol = max(float(vol_map.get(code, 0.20)), 1e-4)
        inverse.append(1.0 / vol)
    total = float(sum(inverse))
    weights = {
        codes[index]: inverse[index] / total
        for index in range(len(codes))
    }
    capped = set()
    while True:
        over = [code for code in codes
                if code not in capped and weights[code] > cap]
        if not over:
            break
        for code in over:
            weights[code] = cap
            capped.add(code)
        remaining = [code for code in codes if code not in capped]
        room = 1.0 - sum(weights[code] for code in capped)
        if not remaining or room <= 0:
            break
        raw_total = sum(inverse[codes.index(code)] for code in remaining)
        for code in remaining:
            raw = inverse[codes.index(code)]
            weights[code] = room * raw / raw_total
    return weights


def scale_to_vol_target(weights, vol_map, target=0.18):
    variance = 0.0
    for code, weight in weights.items():
        variance += (float(weight) * float(vol_map.get(code, 0.20))) ** 2
    portfolio_vol = float(np.sqrt(max(variance, 0.0)))
    if portfolio_vol <= 1e-12:
        return dict(weights), 1.0
    scale = min(1.0, float(target) / portfolio_vol)
    return {
        code: float(weight) * scale for code, weight in weights.items()
    }, scale


def build_targets(state, growth_ranked, div_ranked, vol_map,
                  growth_corr_high=False, div_all_negative=False,
                  vol_target=0.18):
    """Convert sleeve allocations to inverse-vol ETF target weights."""
    growth_weight, div_weight, _cash_weight = SLEEVE_WEIGHTS[state]
    growth_ranked = list(growth_ranked or [])
    div_ranked = list(div_ranked or [])
    if state == STATE_LOCK:
        growth_ranked = []
        growth_weight = 0.0
    if growth_corr_high:
        growth_weight *= 0.5
    if div_all_negative:
        div_ranked = []
        div_weight = 0.0
    growth_pick = growth_ranked[:3]
    div_pick = div_ranked[:2]
    weights = {}
    if growth_pick and growth_weight > 0:
        sleeve = inverse_vol_weights(growth_pick, vol_map)
        for code, weight in sleeve.items():
            weights[code] = weight * growth_weight
    if div_pick and div_weight > 0:
        sleeve = inverse_vol_weights(div_pick, vol_map)
        for code, weight in sleeve.items():
            weights[code] = weights.get(code, 0.0) + weight * div_weight
    scaled, _scale = scale_to_vol_target(weights, vol_map, vol_target)
    return scaled


def apply_hysteresis(current, proposed, score_map, gap=1.15):
    """Keep eligible incumbents unless challengers beat them by `gap`."""
    current = list(current or [])
    proposed = list(proposed or [])
    if not current:
        return proposed
    limit = max(len(proposed), 1)
    result = []
    challengers = [code for code in proposed if code not in current]
    for incumbent in current:
        if incumbent in proposed:
            result.append(incumbent)
            continue
        challenger = None
        if challengers:
            challenger = challengers.pop(0)
        if challenger is None:
            result.append(incumbent)
            continue
        old_score = float(score_map.get(incumbent, 0.0))
        new_score = float(score_map.get(challenger, 0.0))
        if new_score > old_score * float(gap):
            result.append(challenger)
        else:
            result.append(incumbent)
    for code in proposed:
        if code not in result and len(result) < limit:
            result.append(code)
    result.sort(key=lambda code: float(score_map.get(code, -1e18)),
                reverse=True)
    return result[:limit]


def lot_shares(value, price, lot=100):
    if price is None or price <= 0 or value <= 0:
        return 0
    shares = int(float(value) / float(price))
    return int(shares / int(lot)) * int(lot)


def crash_triggered(closes, single_day=0.06, three_day=0.08):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 2:
        return False
    if closes[-2] > 0:
        one_day = (closes[-2] - closes[-1]) / closes[-2]
        if one_day >= single_day:
            return True
    if len(closes) >= 4 and closes[-4] > 0:
        three_days = (closes[-4] - closes[-1]) / closes[-4]
        if three_days >= three_day:
            return True
    return False


def trailing_stop_hit(close_price, high_water, pct=0.22):
    if close_price is None or high_water is None or high_water <= 0:
        return False
    return float(close_price) <= float(high_water) * (1.0 - float(pct))


# ---------------------------------------------------------------------------
# PTrade lifecycle
# ---------------------------------------------------------------------------
def initialize(context):
    g.growth = list(GROWTH)
    g.diversifier = list(DIVERSIFIER)
    g.etf_pool = list(dict.fromkeys(g.growth + g.diversifier))
    g.market = "510300.SS"
    g.size = "510500.SS"
    g.cash_etf = "511880.SS"
    g.repo_code = "204001.SS"
    g.hist_count = 300
    g.corr_limit = 0.70
    g.corr_cluster = 0.80
    g.vol_target = 0.18
    g.hysteresis = 1.15
    g.trail_pct = 0.22
    g.lockdown_days = 3
    g.cash_reserve = 0.02
    g.premium_limit = 0.03
    g.min_weight = 0.03
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
    # The buy callback is always present in backtest and live execution.
    run_daily(context, rebalance_buy, time="14:54")
    if is_trade():
        run_daily(context, park_cash_in_repo, time="14:57")


def before_trading_start(context, data):
    g.pending_orders = {}


def handle_data(context, data):
    current = _current_dt(context)
    if current is None:
        return
    if current.strftime("%H:%M") in ("09:35", "13:05"):
        crash_overlay(context, data)


def after_trading_end(context, data):
    if g.lockdown_left > 0:
        g.lockdown_left -= 1
    log.info("日终 状态=%s 锁仓剩余=%d 资产=%.2f 现金=%.2f 目标=%s" % (
        str(g.last_state),
        int(g.lockdown_left),
        float(context.portfolio.portfolio_value),
        float(context.portfolio.cash),
        str(sorted(g.last_target.keys())),
    ))


def weekly_rebalance(context, data=None):
    """14:50 weekly scoring and sell leg."""
    today = _current_dt(context)
    if today is not None and g.last_rebalance_week == _week_key(today):
        return
    histories = _load_histories(g.etf_pool, g.hist_count)
    if len(histories) < 6:
        log.info("历史行情不足，本次不调仓")
        return
    target = _compute_targets(histories, _held_etfs(context))
    g.last_target = dict(target)
    g.pending_target = dict(target)
    if today is not None:
        g.last_rebalance_week = _week_key(today)
    _sell_to_targets(context, target)


def rebalance_buy(context, data=None):
    """14:54 buy leg, registered every day."""
    if is_trade() and g.pending_orders:
        log.info("仍有未完成委托，推迟买入")
        return
    target = dict(g.pending_target or g.last_target or {})
    if target:
        _buy_to_targets(context, target)


def crash_overlay(context, data=None):
    """Lock down after a CSI 300 crash or a growth-sleeve 22% drawdown."""
    held = _held_etfs(context)
    growth_held = [code for code in held if code in g.growth]
    codes = list(dict.fromkeys([g.market] + growth_held))
    histories = _load_histories(codes, 30)
    triggered = False
    market = histories.get(g.market)
    if market is not None and crash_triggered(
            market["close"], single_day=0.06, three_day=0.08):
        triggered = True
    for code in growth_held:
        bars = histories.get(code)
        if bars is None or len(bars["close"]) == 0:
            continue
        price = float(bars["close"][-1])
        water = g.high_water.get(code)
        if water is None or price > water:
            g.high_water[code] = price
        elif trailing_stop_hit(price, water, g.trail_pct):
            triggered = True
    if not triggered:
        return

    g.lockdown_left = g.lockdown_days
    g.last_state = STATE_LOCK
    div_histories = _load_histories(
        list(dict.fromkeys(g.diversifier + [g.market, g.size])),
        g.hist_count,
    )
    target = {}
    if div_histories:
        snapshot = _score_universe(div_histories)
        ranked = _eligible(g.diversifier, snapshot, held)
        target = build_targets(
            STATE_LOCK,
            [],
            ranked,
            snapshot["vols"],
            growth_corr_high=False,
            div_all_negative=not bool(ranked),
            vol_target=g.vol_target,
        )
    g.last_target = dict(target)
    g.pending_target = dict(target)
    log.info("崩盘/回撤 overlay 触发 3 日 lockdown 目标=%s" % str(target))
    _sell_to_targets(context, target)


def park_cash_in_repo(context, data=None):
    """14:57 live-only reverse repo for idle cash."""
    if not is_trade() or g.pending_orders:
        return
    cash = float(context.portfolio.cash)
    if cash < 1000:
        return
    amount = int(np.floor(cash / 1000.0) * 10)
    if amount < 10:
        return
    order_id = order(g.repo_code, -amount)
    _remember_order(g.repo_code, order_id)


def on_order_response(context, order_list):
    if not order_list:
        return
    for order_info in order_list:
        status = str(_field(order_info, "status", ""))
        code = _normalize_security_code(
            _field(order_info, "stock_code")
            or _field(order_info, "sid")
            or _field(order_info, "symbol")
        )
        if status in ("5", "6", "8", "9"):
            _clear_pending_order(code)
        if status == "9":
            log.info("废单 %s 原因=%s" % (
                str(code), str(_field(order_info, "error_info"))))


def on_trade_response(context, trade_list):
    if not trade_list:
        return
    for trade_info in trade_list:
        if str(_field(trade_info, "status", "")) == "8":
            _clear_pending_order(_field(trade_info, "stock_code"))


# ---------------------------------------------------------------------------
# PTrade helpers
# ---------------------------------------------------------------------------
def _field(value, name, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    try:
        return getattr(value, name, default)
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
    if not is_trade():
        return False
    return _normalize_security_code(code) in g.pending_orders


def _series(frame, field):
    if frame is None or not hasattr(frame, "get"):
        return np.array([])
    column = frame.get(field)
    if column is None and field == "money":
        column = frame.get("amount")
    if column is None:
        return np.array([])
    return np.asarray(column, dtype=float)


def _load_one(code, count):
    """Load one symbol with the PTrade-compatible history call."""
    try:
        frame = get_history(
            count,
            "1d",
            ["open", "high", "low", "close", "volume", "money"],
            security_list=code,
            fq="pre",
            include=False,
        )
    except TypeError:
        try:
            frame = get_history(
                count,
                "1d",
                ["open", "high", "low", "close", "volume"],
                code,
                fq="pre",
                include=False,
            )
        except Exception:
            return None
    except Exception:
        return None
    if frame is None or len(frame) == 0:
        return None
    bars = {
        "open": _series(frame, "open"),
        "high": _series(frame, "high"),
        "low": _series(frame, "low"),
        "close": _series(frame, "close"),
        "volume": _series(frame, "volume"),
        "money": _series(frame, "money"),
    }
    if len(bars["close"]) == 0:
        return None
    if len(bars["money"]) == 0:
        bars["money"] = bars["close"] * bars["volume"]
    return bars


def _load_histories(codes, count):
    histories = {}
    for code in codes:
        bars = _load_one(code, count)
        if bars is not None:
            histories[code] = bars
    return histories


def _current_dt(context):
    value = getattr(context, "current_dt", None)
    if value is not None:
        return value
    blotter = getattr(context, "blotter", None)
    return getattr(blotter, "current_dt", None)


def _week_key(value):
    try:
        iso = value.isocalendar()
        return int(iso[0]), int(iso[1])
    except Exception:
        return value.year, value.timetuple().tm_yday // 7


def _held_etfs(context):
    try:
        positions = get_positions()
    except Exception:
        positions = None
    if not positions:
        return []
    if hasattr(positions, "items"):
        items = list(positions.items())
    elif isinstance(positions, (list, tuple)):
        items = [
            (_field(position, "sid") or _field(position, "security"), position)
            for position in positions
        ]
    else:
        items = []
    tradable = set(g.etf_pool + [g.cash_etf])
    held = []
    for code, position in items:
        code = _normalize_security_code(code or _field(position, "sid"))
        amount = int(_field(position, "amount", 0) or 0)
        if code in tradable and amount > 0:
            held.append(code)
    return held


def _position_amount(code):
    try:
        position = get_position(code)
    except Exception:
        position = None
    return int(_field(position, "amount", 0) or 0)


def _current_price(code):
    bars = _load_one(code, 5)
    if bars is None or len(bars["close"]) == 0:
        return None
    return float(bars["close"][-1])


def _premium_too_high(code, price):
    """Veto high-premium 513 QDII funds in live trading only."""
    if not is_trade() or not str(code).startswith("513"):
        return False
    try:
        info = get_etf_info(code)
    except Exception:
        return False
    if not info:
        return False
    iopv = (
        _field(info, "iopv")
        or _field(info, "IOPV")
        or _field(info, "nav")
        or _field(info, "unit_nav")
    )
    try:
        iopv = float(iopv)
    except Exception:
        return False
    if iopv <= 0 or price is None:
        return False
    return float(price) / iopv - 1.0 >= g.premium_limit


def _limit_blocked(code):
    try:
        result = check_limit(code)
    except Exception:
        return False
    if isinstance(result, dict):
        try:
            return int(result.get(code, 0) or 0) != 0
        except Exception:
            return False
    return False


def _lot_for(code):
    return 1 if str(code).startswith("51188") else 100


def _score_universe(histories):
    market = histories.get(g.market)
    size = histories.get(g.size)
    market_close = None if market is None else market["close"]
    size_close = None if size is None else size["close"]
    scores = {}
    residual_scores = {}
    trend = {}
    ret20 = {}
    ret63 = {}
    vols = {}
    ret60 = {}
    crowding = {}
    for code, bars in histories.items():
        close = bars["close"]
        if market_close is None or len(close) < 70:
            continue
        residual = residual_momentum(close, market_close, size_close)
        momentum = period_return(close, 63)
        vol = realized_vol(close, 20)
        residual_scores[code] = residual
        ret63[code] = momentum
        vols[code] = vol
        scores[code] = combined_score(residual, momentum, vol)
        trend[code] = trend_quality(close)
        ret20[code] = period_return(close, 20)
        ret60[code] = log_returns(close)[-60:]
        crowding[code] = crowding_points(
            close,
            bars["high"],
            bars["low"],
            bars["volume"],
            bars.get("money"),
        )
    return {
        "scores": scores,
        "residual": residual_scores,
        "tq": trend,
        "ret20": ret20,
        "ret63": ret63,
        "vols": vols,
        "ret60": ret60,
        "crowd": crowding,
        "mkt_close": market_close,
    }


def _eligible(codes, snapshot, held):
    """Apply positive momentum, TQ 0.80 and four-point crowding gates."""
    held = set(held or [])
    ranked = []
    for code in codes:
        score = snapshot["scores"].get(code)
        if score is None:
            continue
        if snapshot["ret63"].get(code, 0.0) <= 0:
            continue
        if snapshot["tq"].get(code, 0.0) < 0.80:
            continue
        if snapshot["crowd"].get(code, 0) >= 4 and code not in held:
            continue
        ranked.append((code, float(score)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [code for code, _score in ranked]


def _compute_targets(histories, current_held):
    snapshot = _score_universe(histories)
    g.last_scores = dict(snapshot["scores"])
    breadth = growth_breadth(snapshot["ret20"], g.growth)
    med_vol = median_vol(snapshot["vols"], g.growth)
    market_close = snapshot["mkt_close"]
    if market_close is not None and crash_triggered(
            market_close, single_day=0.06, three_day=0.08):
        g.lockdown_left = max(g.lockdown_left, g.lockdown_days)
    state = classify_state(breadth, med_vol, g.lockdown_left > 0)
    g.last_state = state

    growth_all = _eligible(g.growth, snapshot, current_held)
    div_all = _eligible(g.diversifier, snapshot, current_held)
    cluster = (
        mean_pairwise_corr(snapshot["ret60"], growth_all[:5])
        > g.corr_cluster
    )
    growth_ranked = filter_correlated(
        growth_all, snapshot["ret60"], g.corr_limit)
    div_ranked = filter_correlated(
        div_all, snapshot["ret60"], g.corr_limit)

    current_growth = [
        code for code in current_held if code in growth_ranked
    ]
    current_div = [code for code in current_held if code in div_ranked]
    stable_growth = apply_hysteresis(
        current_growth,
        growth_ranked[:3],
        snapshot["scores"],
        g.hysteresis,
    )
    stable_div = apply_hysteresis(
        current_div,
        div_ranked[:2],
        snapshot["scores"],
        g.hysteresis,
    )
    weights = build_targets(
        state,
        stable_growth,
        stable_div,
        snapshot["vols"],
        growth_corr_high=cluster,
        div_all_negative=not bool(div_ranked),
        vol_target=g.vol_target,
    )
    weights = {
        code: weight for code, weight in weights.items()
        if weight >= g.min_weight
    }
    log.info(
        "state=%s breadth=%.2f medvol=%.2f cluster=%s growth=%s div=%s target=%s"
        % (
            state,
            breadth,
            med_vol,
            str(cluster),
            str(stable_growth),
            str(stable_div),
            str(weights),
        )
    )
    return weights


def _sell_to_targets(context, target_weights):
    """Sell removals and overweight lots; never open positions."""
    targets = {
        code: float(weight)
        for code, weight in (target_weights or {}).items()
        if weight > 0.0
    }
    portfolio_value = float(context.portfolio.portfolio_value)
    for code in _held_etfs(context):
        if _has_pending_order(code):
            continue
        if code not in targets:
            order_id = order_target(code, 0)
            _remember_order(code, order_id)
            g.high_water.pop(code, None)
            continue
        price = _current_price(code)
        if price is None or price <= 0:
            continue
        lot = _lot_for(code)
        amount = _position_amount(code)
        excess = amount * price - portfolio_value * targets[code]
        shares = min(lot_shares(excess, price, lot), amount)
        shares = int(shares / lot) * lot
        if shares >= lot:
            order_id = order(code, -shares)
            _remember_order(code, order_id)


def _buy_to_targets(context, target_weights):
    """Buy target deficits with available cash; never sell positions."""
    targets = {
        code: float(weight)
        for code, weight in (target_weights or {}).items()
        if weight > 0.0
    }
    portfolio_value = (
        float(context.portfolio.portfolio_value) * (1.0 - g.cash_reserve)
    )
    cash_left = float(context.portfolio.cash) * (1.0 - g.cash_reserve)
    for code in sorted(targets, key=lambda item: -targets[item]):
        if _has_pending_order(code):
            continue
        price = _current_price(code)
        if price is None or price <= 0:
            continue
        lot = _lot_for(code)
        current = _position_amount(code)
        deficit = portfolio_value * targets[code] - current * price
        if deficit < price * lot:
            continue
        if _premium_too_high(code, price):
            log.info("溢价过高，跳过 %s" % code)
            continue
        if _limit_blocked(code):
            log.info("涨跌停限制，跳过 %s" % code)
            continue
        shares = min(
            lot_shares(deficit, price, lot),
            lot_shares(cash_left, price, lot),
        )
        if shares < lot:
            continue
        order_id = order(code, shares)
        if order_id is not None:
            _remember_order(code, order_id)
            cash_left -= shares * price
            water = g.high_water.get(code)
            if water is None or price > water:
                g.high_water[code] = price
            log.info("买入 %s 数量=%d 权重=%.2f" % (
                code, shares, targets[code]))
