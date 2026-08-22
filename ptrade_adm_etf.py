# -*- coding: utf-8 -*-
"""
Antonacci Dual Momentum asset-class rotation for 国金 PTrade.

The strategy rotates among CSI 300, ChiNext, Nasdaq and gold, with a
positive one-month gate and a four-point crowding veto. Ineligible risk
assets fall back to government bonds.

Run in minute mode. SimTradeLab must use broker="auto", not
broker="guosheng". The live file requires only numpy.
"""
import numpy as np


RISK = [
    "510300.SS",
    "159915.SZ",
    "513100.SS",
    "518880.SS",
]
BOND = "511010.SS"
CASH_ETF = "511880.SS"


# ---------------------------------------------------------------------------
# Pure signal and allocation functions
# ---------------------------------------------------------------------------
def log_returns(closes):
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) < 2:
        return np.array([])
    return np.diff(np.log(np.maximum(closes, 1e-12)))


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


def ts_momentum(closes, lookback=252, skip=21):
    """Skipped 12-month return, falling back to 126/5 when needed."""
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    lookback = int(lookback)
    skip = int(skip)
    needed = lookback + skip
    if lookback > 0 and skip > 0 and len(closes) >= needed:
        start = float(closes[-needed])
        end = float(closes[-skip])
        if start > 0:
            return float(end / start - 1.0)
    fallback_lookback = 126
    fallback_skip = 5
    fallback_needed = fallback_lookback + fallback_skip
    if len(closes) >= fallback_needed:
        start = float(closes[-fallback_needed])
        end = float(closes[-fallback_skip])
        if start > 0:
            return float(end / start - 1.0)
    return 0.0


def month_gate(closes):
    """Moskowitz one-month gate: latest 21-session return is positive."""
    return bool(period_return(closes, 21) > 0)


def _corr(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    count = min(len(left), len(right))
    if count < 8:
        return 0.0
    left = left[-count:]
    right = right[-count:]
    mask = np.isfinite(left) & np.isfinite(right)
    if int(mask.sum()) < 8:
        return 0.0
    left = left[mask]
    right = right[mask]
    if np.std(left) < 1e-12 or np.std(right) < 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def crowding_points(closes, highs, lows, volumes, amounts=None):
    """Return the RMDC 0-4 crowding score."""
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    count = min(len(closes), len(highs), len(lows), len(volumes))
    if count < 61:
        return 0
    closes = closes[-count:]
    highs = highs[-count:]
    lows = lows[-count:]
    volumes = volumes[-count:]
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


def pick_risk_asset(score_map, gate_map, crowd_map):
    """Return the highest-score eligible risk asset, or None."""
    winner = None
    winner_score = -1e18
    for code in RISK:
        score = score_map.get(code)
        if score is None:
            continue
        score = float(score)
        if not np.isfinite(score) or score <= 0:
            continue
        if not bool(gate_map.get(code, False)):
            continue
        if int(crowd_map.get(code, 0)) >= 4:
            continue
        if winner is None or score > winner_score:
            winner = code
            winner_score = score
    return winner


def build_targets(winner, winner_vol, vol_target=0.16, bond=BOND):
    """Vol-scale the winner and put the remaining allocation in bonds."""
    if winner is None:
        return {bond: 0.95}
    try:
        winner_vol = float(winner_vol)
    except Exception:
        return {bond: 0.95}
    if not np.isfinite(winner_vol) or winner_vol <= 0:
        return {bond: 0.95}
    risk_weight = min(1.0, float(vol_target) / winner_vol)
    return {
        winner: risk_weight,
        bond: 1.0 - risk_weight,
    }


def lot_shares(value, price, lot=100):
    if price is None or price <= 0 or value <= 0:
        return 0
    shares = int(float(value) / float(price))
    return int(shares / int(lot)) * int(lot)


# ---------------------------------------------------------------------------
# PTrade lifecycle
# ---------------------------------------------------------------------------
def initialize(context):
    g.risk = list(RISK)
    g.bond = BOND
    g.cash_etf = CASH_ETF
    g.repo_code = "204001.SS"
    g.market = "510300.SS"
    g.universe = list(g.risk) + [g.bond]
    g.hist_count = 300
    g.vol_target = 0.16
    g.lockdown_days = 3
    g.lockdown_left = 0
    g.last_rebalance_week = None
    g.last_target = {}
    g.pending_target = {}
    g.pending_orders = {}
    g.last_winner = None

    set_universe(g.universe + [g.cash_etf])
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
    run_daily(context, rebalance_buy, time="14:54")
    if is_trade():
        run_daily(context, park_cash_in_repo, time="14:57")


def before_trading_start(context, data):
    g.pending_orders = {}


def handle_data(context, data):
    return


def after_trading_end(context, data):
    if g.lockdown_left > 0:
        g.lockdown_left -= 1
    log.info("日终 winner=%s lockdown=%d 资产=%.2f 现金=%.2f 目标=%s" % (
        str(g.last_winner),
        int(g.lockdown_left),
        float(context.portfolio.portfolio_value),
        float(context.portfolio.cash),
        str(g.last_target),
    ))


def weekly_rebalance(context, data=None):
    """14:50 weekly signal calculation and sell leg."""
    today = _current_dt(context)
    if today is not None and g.last_rebalance_week == _week_key(today):
        return
    histories = _load_histories(g.universe, g.hist_count)
    if len(histories) < len(g.universe):
        log.info("历史行情不足，本次不调仓")
        return
    target = _compute_targets(histories)
    g.last_target = dict(target)
    g.pending_target = dict(target)
    if today is not None:
        g.last_rebalance_week = _week_key(today)
    _sell_to_targets(context, target)


def rebalance_buy(context, data=None):
    """14:54 buy leg, registered in backtest and live trading."""
    if is_trade() and g.pending_orders:
        log.info("仍有未完成委托，推迟买入")
        return
    target = dict(g.pending_target or g.last_target or {})
    if target:
        _buy_to_targets(context, target)


def crash_overlay(context, data=None):
    """Lock down on a CSI 300 or currently held risk-asset crash."""
    held_risk = _held_risk_assets(context)
    codes = list(dict.fromkeys([g.market] + held_risk))
    histories = _load_histories(codes, 30)
    triggered_code = None
    for code in codes:
        bars = histories.get(code)
        if bars is None:
            continue
        if crash_triggered(
                bars["close"], single_day=0.06, three_day=0.08):
            triggered_code = code
            break
    if triggered_code is None:
        return
    g.lockdown_left = g.lockdown_days
    g.last_winner = None
    target = build_targets(None, None, bond=g.bond)
    g.last_target = dict(target)
    g.pending_target = dict(target)
    log.info("崩盘 overlay 触发 code=%s 3 日 lockdown" % triggered_code)
    _sell_to_targets(context, target)


def park_cash_in_repo(context, data=None):
    """14:57 live-only reverse repo."""
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
    """Load one symbol with fq="pre" and include=False."""
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


def _positions():
    try:
        positions = get_positions()
    except Exception:
        positions = None
    if not positions:
        return []
    if hasattr(positions, "items"):
        return list(positions.items())
    if isinstance(positions, (list, tuple)):
        return [
            (_field(position, "sid") or _field(position, "security"), position)
            for position in positions
        ]
    return []


def _held_etfs(context):
    tradable = set(g.universe + [g.cash_etf])
    held = []
    for code, position in _positions():
        code = _normalize_security_code(code or _field(position, "sid"))
        amount = int(_field(position, "amount", 0) or 0)
        if code in tradable and amount > 0:
            held.append(code)
    return held


def _held_risk_assets(context):
    risk = set(g.risk)
    return [code for code in _held_etfs(context) if code in risk]


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
    price = float(bars["close"][-1])
    if not np.isfinite(price):
        return None
    return price


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


def _score_risk(histories):
    scores = {}
    gates = {}
    crowds = {}
    vols = {}
    for code in g.risk:
        bars = histories.get(code)
        if bars is None:
            continue
        closes = bars["close"]
        scores[code] = ts_momentum(closes)
        gates[code] = month_gate(closes)
        crowds[code] = crowding_points(
            closes,
            bars["high"],
            bars["low"],
            bars["volume"],
            bars.get("money"),
        )
        vols[code] = realized_vol(closes, 20)
    return scores, gates, crowds, vols


def _compute_targets(histories):
    market = histories.get(g.market)
    market_crash = bool(
        market is not None
        and crash_triggered(
            market["close"], single_day=0.06, three_day=0.08)
    )
    if market_crash:
        g.lockdown_left = max(g.lockdown_left, g.lockdown_days)
    scores, gates, crowds, vols = _score_risk(histories)
    winner = pick_risk_asset(scores, gates, crowds)
    if g.lockdown_left > 0:
        winner = None
    g.last_winner = winner
    winner_vol = None if winner is None else vols.get(winner)
    target = build_targets(
        winner,
        winner_vol,
        vol_target=g.vol_target,
        bond=g.bond,
    )
    log.info("winner=%s lockdown=%d scores=%s gate=%s crowd=%s target=%s" % (
        str(winner),
        int(g.lockdown_left),
        str(scores),
        str(gates),
        str(crowds),
        str(target),
    ))
    return target


def _sell_to_targets(context, target_weights):
    """Sell removals and overweight lots without opening positions."""
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
    """Buy target deficits with finite last closes and available cash."""
    targets = {
        code: float(weight)
        for code, weight in (target_weights or {}).items()
        if weight > 0.0
    }
    portfolio_value = float(context.portfolio.portfolio_value)
    cash_left = float(context.portfolio.cash)
    for code in sorted(targets, key=lambda item: -targets[item]):
        if _has_pending_order(code):
            continue
        price = _current_price(code)
        if price is None or not np.isfinite(price) or price <= 0:
            continue
        lot = _lot_for(code)
        current = _position_amount(code)
        deficit = portfolio_value * targets[code] - current * price
        if deficit < price * lot:
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
            log.info("买入 %s 数量=%d 权重=%.2f" % (
                code, shares, targets[code]))
