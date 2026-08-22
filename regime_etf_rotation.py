# -*- coding: utf-8 -*-
"""
2026 状态机 ETF 轮动（PTrade 单文件策略）

设计对齐 2026 年 A 股量化约束：
- 中低频、ETF 表达、低换手
- A 股走弱时只允许黄金 / 跨境 / 红利 / 债券
- 动量 * R2 * 效率系数，避免无趋势震荡市乱切
- 分数差距滞后，避免每天因微小分差换仓
- 持有 2 只而不是 1 只，降低单主题拥挤
- Python 3.5 兼容（不用 f-string）
- 下单用 order / order_target，避开 order_target_value 的实盘坑

把本文件整体粘贴进券商 PTrade。本地单元测试会 import 下面的纯函数。
"""
import math
import numpy as np


# ---------------------------------------------------------------------------
# 纯函数：本地回测和 PTrade 共用
# ---------------------------------------------------------------------------
REGIME_RISK_ON = "risk_on"
REGIME_RISK_OFF = "risk_off"

DEFAULT_DEFENSIVE = [
    "518880.SS",  # 黄金
    "513100.SS",  # 纳指
    "513520.SS",  # 日经
    "513030.SS",  # 德国
    "510880.SS",  # 上证红利
    "512890.SS",  # 红利低波
    "511010.SS",  # 国债
    "511090.SS",  # 30 年国债
]

DEFAULT_GROWTH = [
    "510300.SS",  # 沪深300
    "510500.SS",  # 中证500
    "512100.SS",  # 中证1000
    "159915.SZ",  # 创业板
    "588000.SS",  # 科创50
    "512480.SS",  # 半导体
    "515880.SS",  # 通信
    "515980.SS",  # 人工智能
    "159857.SZ",  # 光伏
    "513180.SS",  # 恒生科技
    "516650.SS",  # 有色
]


def calc_true_range(highs, lows, closes):
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 2:
        return np.array([])
    prev_close = closes[:-1]
    tr = np.maximum(highs[1:] - lows[1:], np.abs(highs[1:] - prev_close))
    tr = np.maximum(tr, np.abs(lows[1:] - prev_close))
    return tr


def calc_atr(highs, lows, closes, period):
    tr = calc_true_range(highs, lows, closes)
    if len(tr) == 0:
        return 0.0
    if len(tr) >= period:
        return float(np.mean(tr[-period:]))
    return float(np.mean(tr))


def choose_lookback(highs, lows, closes, min_days, max_days):
    if highs is None or lows is None or len(closes) < min_days:
        return int(min_days)
    long_atr = calc_atr(highs, lows, closes, max_days)
    short_atr = calc_atr(highs[-min_days:], lows[-min_days:], closes[-min_days:], min_days)
    if long_atr <= 0:
        atr_ratio = 0.9
    else:
        atr_ratio = min(0.9, short_atr / long_atr)
    lookback = int(min_days + (max_days - min_days) * (1.0 - atr_ratio))
    if lookback < min_days:
        lookback = min_days
    if lookback > max_days:
        lookback = max_days
    return lookback


def weighted_log_trend_score(prices):
    prices = np.asarray(prices, dtype=float)
    prices = prices[np.isfinite(prices)]
    prices = prices[prices > 0]
    if len(prices) < 5:
        return 0.0, 0.0, 0.0
    y = np.log(prices)
    x = np.arange(len(y))
    weights = np.linspace(1.0, 2.0, len(y))
    x_mean = np.average(x, weights=weights)
    y_mean = np.average(y, weights=weights)
    cov = np.average((x - x_mean) * (y - y_mean), weights=weights)
    var = np.average((x - x_mean) ** 2, weights=weights)
    if var <= 0:
        return 0.0, 0.0, 0.0
    slope = cov / var
    annualized = math.exp(slope * 250.0) - 1.0
    y_pred = slope * x + (y_mean - slope * x_mean)
    ss_res = np.average((y - y_pred) ** 2, weights=weights)
    ss_tot = np.average((y - y_mean) ** 2, weights=weights)
    r2 = 0.0 if ss_tot <= 0 else (1.0 - ss_res / ss_tot)
    if r2 < 0:
        r2 = 0.0
    return float(annualized), float(r2), float(annualized * r2)


def efficiency_coefficient(opens, highs, lows, closes, window=20):
    closes = np.asarray(closes, dtype=float)
    if opens is None:
        opens = closes
    if highs is None:
        highs = closes
    if lows is None:
        lows = closes
    opens = np.asarray(opens, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    n = min(len(opens), len(highs), len(lows), len(closes))
    if n < window + 1:
        return 0.0, 0.0, 0.0
    center = (opens + highs + lows + closes) / 4.0
    center = center[-window - 1:]
    displacement = center[-1] - center[0]
    path = np.sum(np.abs(np.diff(center)))
    if path <= 1e-12:
        coef = 0.0
    else:
        coef = abs(displacement) / path
    if coef > 1.0:
        coef = 1.0
    mom = displacement / (abs(center[0]) + 1e-8)
    return float(mom), float(coef), float(mom * coef)


def crash_triggered(prices, single_day=0.05, three_day=0.05):
    prices = np.asarray(prices, dtype=float)
    prices = prices[np.isfinite(prices)]
    if len(prices) < 4:
        return False
    last3 = prices[-4:]
    for i in range(1, len(last3)):
        if last3[i - 1] > 0 and last3[i] / last3[i - 1] < (1.0 - single_day):
            return True
    if last3[0] > 0 and last3[-1] / last3[0] < (1.0 - three_day):
        consecutive = all(last3[i] < last3[i - 1] for i in range(1, len(last3)))
        if consecutive:
            return True
    return False


def detect_regime(benchmark_prices, ma_window=60, risk_off_buffer=0.0):
    prices = np.asarray(benchmark_prices, dtype=float)
    prices = prices[np.isfinite(prices)]
    if len(prices) < ma_window:
        return REGIME_RISK_OFF
    ma = float(np.mean(prices[-ma_window:]))
    last = float(prices[-1])
    if last >= ma * (1.0 - risk_off_buffer):
        return REGIME_RISK_ON
    return REGIME_RISK_OFF


def eligible_pool(regime, all_codes, defensive_codes):
    if regime == REGIME_RISK_ON:
        return list(all_codes)
    defensive = [c for c in all_codes if c in set(defensive_codes)]
    if defensive:
        return defensive
    return list(all_codes)


def combined_score(prices, opens=None, highs=None, lows=None,
                   min_days=20, max_days=60, auto_day=True,
                   single_day_drop=0.05, three_day_drop=0.05):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < min_days:
        return {
            "annualized": 0.0,
            "r2": 0.0,
            "efficiency": 0.0,
            "score": 0.0,
            "lookback": min_days,
            "crashed": False,
        }
    if auto_day:
        lookback = choose_lookback(highs, lows, prices, min_days, max_days)
    else:
        lookback = max_days
    window = prices[-lookback:]
    annualized, r2, base = weighted_log_trend_score(window)
    _mom, coef, _eff = efficiency_coefficient(opens, highs, lows, prices, window=min(20, len(prices) - 1))
    crashed = crash_triggered(prices, single_day_drop, three_day_drop)
    if crashed:
        score = 0.0
    else:
        score = base * (0.5 + 0.5 * coef)
    return {
        "annualized": annualized,
        "r2": r2,
        "efficiency": coef,
        "score": float(score),
        "lookback": lookback,
        "crashed": crashed,
    }


def select_holdings(score_map, current_holdings, hold_num, score_floor=0.0, gap=0.15):
    ranked = sorted(
        [(code, float(score_map.get(code, 0.0))) for code in score_map],
        key=lambda item: item[1],
        reverse=True,
    )
    ranked = [item for item in ranked if item[1] > score_floor]
    if not ranked:
        return []
    top_codes = [code for code, _s in ranked[:hold_num]]
    top_score = ranked[0][1]
    chosen = []
    for code in current_holdings or []:
        sc = float(score_map.get(code, 0.0))
        if sc <= score_floor:
            continue
        if code in top_codes or sc >= top_score - gap:
            chosen.append(code)
        if len(chosen) >= hold_num:
            break
    for code, _sc in ranked:
        if len(chosen) >= hold_num:
            break
        if code not in chosen:
            chosen.append(code)
    return chosen[:hold_num]


def lot_size(cash, price):
    if price is None or price <= 0 or cash <= 0:
        return 0
    shares = int(cash / price / 100.0) * 100
    if shares < 100:
        return 0
    return shares


def plan_rebalance(held, target):
    held_list = list(held or [])
    target_list = list(target or [])
    sells = [code for code in held_list if code not in target_list]
    buys = [code for code in target_list if code not in held_list]
    keeps = [code for code in target_list if code in held_list]
    return sells, buys, keeps


# ---------------------------------------------------------------------------
# PTrade 生命周期
# ---------------------------------------------------------------------------
def initialize(context):
    g.benchmark = "510300.SS"
    g.min_days = 20
    g.max_days = 60
    g.auto_day = True
    g.hold_num = 2
    g.score_floor = 0.02
    g.score_cap = 8.0
    g.gap = 0.15
    g.ma_window = 60
    g.drop_1d = 0.05
    g.drop_3d = 0.05
    g.trade_time = "14:50"
    g.rebalance_days = 1
    g.last_rebalance_date = None
    g.cash_reserve = 0.02
    g.reverse_repo = ["131810.SZ", "204001.SS"]
    g.defensive = list(DEFAULT_DEFENSIVE)
    g.etf_pool = list(dict.fromkeys(DEFAULT_DEFENSIVE + DEFAULT_GROWTH))
    g.last_target = []
    g.pending_target = []
    g.pending_orders = {}

    set_universe(g.etf_pool)
    set_benchmark("000300.SS")
    if not is_trade():
        set_commission(commission_ratio=0.0003, min_commission=5)
        set_slippage(slippage=0.001)
        set_limit_mode(limit_mode="UNLIMITED")

    run_daily(context, rebalance, time=g.trade_time)
    if is_trade():
        run_daily(context, rebalance_buy, time="14:54")
        run_daily(context, park_cash_in_repo, time="14:57")


def before_trading_start(context, data):
    g.pending_orders = {}


def handle_data(context, data):
    # 日线回测时 run_daily 负责调仓；分钟级实盘额外做一次盘中止损检查
    current_dt = getattr(context.blotter, "current_dt", None)
    if current_dt is None:
        return
    hhmm = current_dt.strftime("%H:%M")
    if hhmm in ("09:35", "13:05"):
        _crash_flatten(context, data)


def after_trading_end(context, data):
    positions = _held_etfs(context)
    log.info("日终 总资产=%.2f 现金=%.2f 持仓=%s 目标=%s" % (
        context.portfolio.portfolio_value,
        context.portfolio.cash,
        str(positions),
        str(g.last_target),
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
        log.info("成交 %s 数量=%s 价格=%s" % (
            str(sid),
            str(trade_info.get("business_amount")),
            str(trade_info.get("business_price")),
        ))


def rebalance(context, data=None):
    today = getattr(context, "current_dt", None) or getattr(context.blotter, "current_dt", None)
    if today is not None and g.last_rebalance_date is not None:
        try:
            delta = (today.date() - g.last_rebalance_date).days
        except Exception:
            delta = g.rebalance_days
        if delta < g.rebalance_days:
            return
    hist_map = _load_histories(g.etf_pool, g.max_days + 10)
    if not hist_map:
        log.info("未取得任何ETF历史行情，本次不调仓")
        return
    bench = hist_map.get(g.benchmark)
    bench_close = None if bench is None else bench.get("close")
    if bench_close is None:
        # 基准行情缺失时采取防御状态，不能放大为全池风险偏好。
        regime = REGIME_RISK_OFF
    else:
        regime = detect_regime(bench_close, g.ma_window)
    pool = eligible_pool(regime, g.etf_pool, g.defensive)
    score_map = {}
    for code in pool:
        bars = hist_map.get(code)
        if not bars:
            continue
        result = combined_score(
            bars["close"],
            opens=bars.get("open"),
            highs=bars.get("high"),
            lows=bars.get("low"),
            min_days=g.min_days,
            max_days=g.max_days,
            auto_day=g.auto_day,
            single_day_drop=g.drop_1d,
            three_day_drop=g.drop_3d,
        )
        if result["score"] >= g.score_cap:
            continue
        score_map[code] = result["score"]

    if not score_map:
        log.info("ETF行情存在但没有可用评分，本次保留原持仓")
        return
    current = _held_etfs(context)
    target = select_holdings(score_map, current, g.hold_num, g.score_floor, g.gap)
    g.last_target = list(target)
    g.pending_target = list(target)
    if today is not None:
        try:
            g.last_rebalance_date = today.date()
        except Exception:
            g.last_rebalance_date = today
    log.info("regime=%s pool=%d target=%s scores=%s" % (
        regime,
        len(pool),
        str(target),
        _top_scores(score_map, 5),
    ))

    _align_positions(context, target)


def rebalance_buy(context, data=None):
    if g.pending_orders:
        log.info("仍有未完成委托，推迟买入")
        return
    target = list(getattr(g, "pending_target", None) or g.last_target or [])
    _align_positions(context, target)


def park_cash_in_repo(context, data=None):
    if not is_trade():
        return
    if g.pending_orders:
        log.info("仍有未完成ETF委托，跳过逆回购")
        return
    cash = float(context.portfolio.cash)
    if cash < 10000:
        return
    shen = _last_px("131810.SZ")
    hu = _last_px("204001.SS")
    if shen is None and hu is None:
        return
    if hu is None or (shen is not None and shen >= hu):
        code = "131810.SZ"
    else:
        code = "204001.SS"
    amount = int(math.floor(cash / 1000.0) * 10)
    if amount >= 10:
        order_id = order(code, -amount)
        _remember_order(code, order_id)
        log.info("逆回购 %s 数量=%d" % (code, amount))


def _crash_flatten(context, data):
    hist_map = _load_histories(_held_etfs(context), g.max_days)
    for code in list(_held_etfs(context)):
        if _has_pending_order(code):
            continue
        bars = hist_map.get(code)
        if not bars:
            continue
        if crash_triggered(bars["close"], g.drop_1d, g.drop_3d):
            order_id = order_target(code, 0)
            _remember_order(code, order_id)
            log.info("盘中跌幅风控清仓 %s" % code)


def _align_positions(context, target):
    held = _held_etfs(context)
    sell_submitted = False

    # 第一阶段只处理清仓。真实柜台不会立即把卖出资金同步回可用现金，
    # 因此有卖单时必须把买入推迟到下一次调仓。
    for code in held:
        if code not in target and not _has_pending_order(code):
            order_id = order_target(code, 0)
            if order_id is not None:
                sell_submitted = True
                _remember_order(code, order_id)
                log.info("卖出非目标 %s" % code)
    if not target:
        return

    value = float(context.portfolio.portfolio_value) * (1.0 - g.cash_reserve)
    per = value / float(len(target))
    position_map = {}
    price_map = {}

    # 第二阶段先减持目标中的超配仓位，仍然不与买单混在同一轮提交。
    for code in target:
        if _has_pending_order(code):
            continue
        price = _current_price(code)
        if price is None or price <= 0:
            continue
        price_map[code] = price
        pos = get_position(code)
        position_map[code] = pos
        current_amount = 0 if pos is None else int(getattr(pos, "amount", 0) or 0)
        current_value = current_amount * price
        diff_value = per - current_value
        if abs(diff_value) < price * 100:
            continue
        if diff_value < 0:
            shares = lot_size(abs(diff_value), price)
            sell_amount = min(shares, current_amount)
            sell_amount = int(sell_amount / 100) * 100
            if sell_amount >= 100:
                order_id = order(code, -sell_amount)
                if order_id is not None:
                    sell_submitted = True
                    _remember_order(code, order_id)
                    log.info("减仓 %s 数量=%d 价格=%.3f" % (code, sell_amount, price))

    if sell_submitted:
        log.info("本轮已提交卖单，等待资金和持仓同步后再买入")
        return

    # 第三阶段买入时只使用柜台当前可用现金，避免按总资产重复占用卖出款。
    available_cash = float(context.portfolio.cash) * (1.0 - g.cash_reserve)
    for code in target:
        if _has_pending_order(code):
            continue
        price = price_map.get(code)
        if price is None:
            price = _current_price(code)
        if price is None or price <= 0:
            continue
        if _etf_premium_too_high(code, price):
            log.info("溢价过高，跳过 %s" % code)
            continue
        pos = position_map.get(code)
        if pos is None:
            pos = get_position(code)
        current_amount = 0 if pos is None else int(getattr(pos, "amount", 0) or 0)
        diff_value = per - current_amount * price
        if diff_value < price * 100:
            continue
        desired_shares = lot_size(diff_value, price)
        cash_shares = lot_size(available_cash, price)
        shares = min(desired_shares, cash_shares)
        if shares < 100:
            continue
        order_id = order(code, shares)
        if order_id is not None:
            _remember_order(code, order_id)
            available_cash -= shares * price
            log.info("买入 %s 数量=%d 价格=%.3f" % (code, shares, price))


def _held_etfs(context):
    positions = get_positions()
    held = []
    if isinstance(positions, dict):
        items = positions.items()
    else:
        items = []
        try:
            items = [(p.sid, p) for p in positions.values()]
        except Exception:
            items = []
    for sid, pos in items:
        amount = getattr(pos, "amount", None)
        if amount is None and isinstance(pos, dict):
            amount = pos.get("amount", 0)
        position_sid = getattr(pos, "sid", None)
        if position_sid is None and isinstance(pos, dict):
            position_sid = pos.get("sid")
        code = _normalize_security_code(position_sid or sid)
        if amount and amount > 0 and code in g.etf_pool and code not in held:
            held.append(code)
    return held


def _load_histories(codes, count):
    result = {}
    if not codes:
        return result
    # 旧版 PTrade 对“多标的+多字段”返回 pandas.Panel，新版和本地框架
    # 返回形态又不同。逐标的获取虽然调用次数更多，但可避免三维 Panel
    # 被误当成价格序列，且与仓库中已运行的 V3 策略用法一致。
    for code in codes:
        try:
            hist = get_history(
                count,
                "1d",
                ["open", "high", "low", "close"],
                code,
                fq="pre",
                include=False,
            )
            parsed = _parse_history(hist, [code])
            if parsed:
                result.update(parsed)
        except Exception as exc:
            log.info("获取历史行情失败 %s: %s" % (code, str(exc)))
            continue
    return result


def _parse_history(hist, codes):
    result = {}
    if hist is None:
        return result
    if isinstance(hist, dict):
        # 可能是 {field: DataFrame} 或 {code: DataFrame}
        sample_key = None
        keys = list(hist.keys())
        if not keys:
            return result
        sample_key = keys[0]
        if sample_key in ("open", "high", "low", "close", "volume"):
            for code in codes:
                bars = {}
                ok = True
                for field in ("open", "high", "low", "close"):
                    frame = hist.get(field)
                    if frame is None:
                        ok = False
                        break
                    series = _extract_series(frame, code)
                    if series is None:
                        ok = False
                        break
                    bars[field] = series
                if ok:
                    result[code] = bars
            return result
        for code in codes:
            frame = hist.get(code)
            if frame is None:
                continue
            bars = {}
            for field in ("open", "high", "low", "close"):
                series = _extract_series(frame, field)
                if series is None:
                    bars = None
                    break
                bars[field] = series
            if bars:
                result[code] = bars
        return result
    # DataFrame
    try:
        if hasattr(hist, "columns") and "code" in list(hist.columns):
            for code in codes:
                part = hist[hist["code"] == code]
                if part is None or len(part) == 0:
                    continue
                bars = {}
                ok = True
                for field in ("open", "high", "low", "close"):
                    if field not in part.columns:
                        ok = False
                        break
                    bars[field] = np.asarray(part[field].values, dtype=float)
                if ok:
                    result[code] = bars
            return result
        for code in codes:
            bars = {}
            ok = True
            for field in ("open", "high", "low", "close"):
                series = _extract_series(hist, (code, field))
                if series is None:
                    series = _extract_series(hist, field if len(codes) == 1 else code)
                if series is None:
                    ok = False
                    break
                bars[field] = series
            if ok:
                result[code] = bars
    except Exception:
        return result
    return result


def _extract_series(frame, key):
    try:
        if hasattr(frame, "columns"):
            if key in frame.columns:
                return np.asarray(frame[key].values, dtype=float)
            if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
                if key in frame.columns:
                    return np.asarray(frame[key].values, dtype=float)
        if hasattr(frame, "values") and not hasattr(frame, "columns"):
            values = np.asarray(frame.values, dtype=float)
            if values.ndim == 1:
                return values
    except Exception:
        return None
    return None


def _current_price(code):
    if is_trade():
        try:
            # 使用字符串参数，与仓库中已有实盘策略保持一致。
            snap = get_snapshot(code)
            if snap and code in snap:
                px = snap[code].get("last_px") or snap[code].get("last")
                if px:
                    return float(px)
        except Exception as exc:
            log.info("获取行情快照失败 %s: %s" % (code, str(exc)))
        # 实盘快照失败时不能用昨收继续计算下单数量。
        return None
    bars = _load_histories([code], 3).get(code)
    if bars and len(bars.get("close", [])) > 0:
        return float(bars["close"][-1])
    return None


def _last_px(code):
    try:
        snap = get_snapshot(code)
        if isinstance(snap, dict) and code in snap:
            return float(snap[code]["last_px"])
        if isinstance(snap, dict) and "last_px" in snap:
            return float(snap["last_px"])
    except Exception:
        return None
    return None


def _etf_premium_too_high(code, price, cap=0.03):
    if not str(code).startswith("513"):
        return False
    try:
        if not is_trade():
            return False
        info = get_etf_info(code)
        if not info:
            return False
        if isinstance(info, dict) and code in info:
            info = info[code]
        iopv = None
        if isinstance(info, dict):
            iopv = info.get("IOPV") or info.get("iopv") or info.get("unit_net_value")
        if not iopv:
            return False
        iopv = float(iopv)
        if iopv <= 0 or price is None:
            return False
        return (float(price) - iopv) / iopv >= cap
    except Exception:
        return False


def _top_scores(score_map, n):
    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)[:n]
    parts = []
    for code, sc in ranked:
        parts.append("%s:%.3f" % (code, sc))
    return ",".join(parts)
