# -*- coding: utf-8 -*-
"""Frozen HOT-LEADER-V1 research signals (manual decision-support proxy).

This is not Tonghuashun's live hot-board. It is a no-lookahead daily proxy:
sector/industry momentum leaders, amount-top30 as a capital-flow stand-in,
CSI 300 trend gate, MACD(12,26,9) plus a rolling Fibonacci retracement filter.
Sell rules: two-day high-volume decline (flow proxy), -8% stop, 20-day time stop.

All indicators at index t use only bars[0:t+1]. Fill is the next session.
"""
from __future__ import print_function

import numpy as np


MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
FIB_WINDOW = 60
FIB_MIN_SWING = 0.15
FIB_LO = 0.382
FIB_HI = 0.618
FIB_INVALID = 0.786
MOM_WINDOW = 20
MA_WINDOW = 20
MA_SLOPE_GAP = 5
HOT_INDUSTRY_COUNT = 10
LEADERS_PER_INDUSTRY = 2
AMOUNT_TOP_N = 30
MAX_HOLDINGS = 10
MAX_NEW_PER_DAY = 3
STOP_LOSS = 0.08
TIME_STOP_DAYS = 20
OUTFLOW_AMOUNT_MULT = 1.0
MIN_AMOUNT_MA = 5.0e7
LIMIT_MAIN = 0.095
LIMIT_CHINEXT = 0.195


def ema(values, span):
    values = np.asarray(values, dtype=float)
    out = np.full(values.shape, np.nan, dtype=float)
    if values.size == 0 or span < 1:
        return out
    alpha = 2.0 / (float(span) + 1.0)
    start = None
    running = 0.0
    count = 0
    for i, price in enumerate(values):
        if not np.isfinite(price):
            continue
        if start is None:
            running += price
            count += 1
            if count == span:
                running /= float(span)
                out[i] = running
                start = i
            continue
        if not np.isfinite(out[i - 1]):
            running = price
        else:
            running = alpha * price + (1.0 - alpha) * out[i - 1]
        out[i] = running
    return out


def macd_hist(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    close = np.asarray(close, dtype=float)
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    hist = dif - dea
    return dif, dea, hist


def macd_ok(close, index):
    """True when histogram turns up and DIF is above DEA (day-close, no lookahead)."""
    if index < MACD_SLOW + MACD_SIGNAL:
        return False
    dif, dea, hist = macd_hist(close[: index + 1])
    if not (np.isfinite(hist[-1]) and np.isfinite(hist[-2])):
        return False
    if not (np.isfinite(dif[-1]) and np.isfinite(dea[-1])):
        return False
    return bool(hist[-1] > hist[-2] and dif[-1] > dea[-1])


def _last_extreme_index(values, compare):
    finite = np.isfinite(values)
    if not finite.any():
        return None
    filled = np.where(finite, values, compare)
    target = compare(filled)
    matches = np.flatnonzero(finite & (values == target))
    if matches.size == 0:
        return None
    return int(matches[-1])


def fib_ok(high, low, close, index, window=FIB_WINDOW, min_swing=FIB_MIN_SWING):
    """Rolling-window Fibonacci filter; swing points use only data through index."""
    if index < window - 1:
        return False
    start = index - window + 1
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    peak_local = _last_extreme_index(high[start: index + 1], np.nanmax)
    if peak_local is None:
        return False
    peak = start + peak_local
    swing_high = float(high[peak])
    look_start = max(0, peak - window + 1)
    trough_local = _last_extreme_index(low[look_start: peak + 1], np.nanmin)
    if trough_local is None:
        return False
    trough = look_start + trough_local
    if trough >= peak:
        return False
    swing_low = float(low[trough])
    if swing_low <= 0 or not np.isfinite(swing_high):
        return False
    if (swing_high - swing_low) / swing_low < min_swing:
        return False
    last_close = float(close[index])
    width = swing_high - swing_low
    if width <= 0 or not np.isfinite(last_close):
        return False
    retrace = (swing_high - last_close) / width
    if not (FIB_LO <= retrace <= FIB_HI):
        return False
    invalid = swing_high - FIB_INVALID * width
    after = close[peak + 1: index + 1]
    if after.size and np.any(np.isfinite(after) & (after <= invalid)):
        return False
    return True


def market_up(close, index, window=MA_WINDOW, slope_gap=MA_SLOPE_GAP):
    close = np.asarray(close, dtype=float)
    if index < window + slope_gap - 1:
        return False
    if not np.isfinite(close[index]):
        return False
    ma_now = float(np.mean(close[index - window + 1: index + 1]))
    ma_prev = float(np.mean(close[index - window + 1 - slope_gap: index + 1 - slope_gap]))
    if not (np.isfinite(ma_now) and np.isfinite(ma_prev)):
        return False
    return bool(close[index] > ma_now and ma_now > ma_prev)


def trailing_return(close, index, window=MOM_WINDOW):
    close = np.asarray(close, dtype=float)
    if index < window:
        return np.nan
    start = close[index - window]
    last = close[index]
    if not (np.isfinite(start) and np.isfinite(last)) or start <= 0:
        return np.nan
    return float(last / start - 1.0)


def mean_amount(amount, index, window=MOM_WINDOW):
    amount = np.asarray(amount, dtype=float)
    if index < window - 1:
        return np.nan
    chunk = amount[index - window + 1: index + 1]
    finite = chunk[np.isfinite(chunk)]
    if finite.size == 0:
        return np.nan
    return float(np.mean(finite))


def limit_threshold(code):
    digits = "".join(ch for ch in str(code) if ch.isdigit())[-6:]
    if digits.startswith(("300", "301", "688", "689")):
        return LIMIT_CHINEXT
    return LIMIT_MAIN


def is_limit_open(open_px, prev_close, code):
    if not (np.isfinite(open_px) and np.isfinite(prev_close)) or prev_close <= 0:
        return True
    return bool((open_px / prev_close - 1.0) >= limit_threshold(code))


def outflow_proxy(close, amount, index):
    """Two down closes with above-average amount: daily stand-in for 主力流出."""
    if index < MOM_WINDOW:
        return False
    close = np.asarray(close, dtype=float)
    amount = np.asarray(amount, dtype=float)
    if not np.all(np.isfinite(close[index - 2: index + 1])):
        return False
    if not (close[index] < close[index - 1] and close[index - 1] < close[index - 2]):
        return False
    baseline = mean_amount(amount, index)
    if not np.isfinite(baseline) or baseline <= 0:
        return False
    return bool(np.isfinite(amount[index]) and amount[index] >= OUTFLOW_AMOUNT_MULT * baseline)


def moneyflow_outflow(net_main, amount, index, days=2, frac=0.05):
    """Vendor 主力净流入: two negative days totaling >= frac of two-day amount."""
    if index < days - 1:
        return False
    net_main = np.asarray(net_main, dtype=float)
    amount = np.asarray(amount, dtype=float)
    net = net_main[index - days + 1: index + 1]
    amt = amount[index - days + 1: index + 1]
    if not np.all(np.isfinite(net)) or not np.all(np.isfinite(amt)):
        return False
    if np.any(net >= 0):
        return False
    total_amt = float(np.sum(amt))
    if total_amt <= 0:
        return False
    return bool(-float(np.sum(net)) >= frac * total_amt)


def pick_hot_industries(returns, industries, count=HOT_INDUSTRY_COUNT):
    """Return the best industries by mean 20d return among finite names."""
    grouped = {}
    for ret, industry in zip(returns, industries):
        if industry is None or industry == "" or not np.isfinite(ret):
            continue
        grouped.setdefault(industry, []).append(float(ret))
    ranked = []
    for industry, values in grouped.items():
        if len(values) < 3:
            continue
        ranked.append((float(np.mean(values)), industry))
    ranked.sort(reverse=True)
    return [item[1] for item in ranked[: int(count)]]


def pick_leaders(returns, industries, hot, per_industry=LEADERS_PER_INDUSTRY):
    chosen = []
    for industry in hot:
        pairs = [
            (float(ret), i)
            for i, (ret, label) in enumerate(zip(returns, industries))
            if label == industry and np.isfinite(ret)
        ]
        pairs.sort(reverse=True)
        for _, i in pairs[: int(per_industry)]:
            chosen.append(i)
    return chosen


def pick_amount_top(amounts, n=AMOUNT_TOP_N):
    pairs = [
        (float(value), i)
        for i, value in enumerate(amounts)
        if np.isfinite(value) and value > 0
    ]
    pairs.sort(reverse=True)
    return [i for _, i in pairs[: int(n)]]
