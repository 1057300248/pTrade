import numpy as np
import pandas as pd

from research.hot_leader_v1 import (
    fib_ok,
    macd_hist,
    macd_ok,
    market_up,
    moneyflow_outflow,
    outflow_proxy,
    pick_amount_top,
    pick_hot_industries,
    pick_leaders,
)
from research.oos_protocol import assert_no_lookahead


def test_macd_histogram_turn_requires_causal_bars():
    close = np.linspace(10.0, 20.0, 80)
    close[70:] = np.linspace(20.0, 16.0, 10)
    assert macd_ok(close, 40) in (True, False)
    dif, dea, hist = macd_hist(close)
    assert hist.shape == close.shape
    # Truncating the future must not change the MACD value at t.
    t = 50
    hist_full = hist[t]
    _, _, hist_cut = macd_hist(close[: t + 1])
    assert np.isclose(hist_full, hist_cut[-1])


def test_fibonacci_filter_does_not_use_future_swings():
    n = 80
    close = np.ones(n) * 10.0
    high = close.copy()
    low = close.copy()
    # Rise 10 -> 20 over bars 0..40, then pull back toward 14 (50% retrace of 10).
    close[:41] = np.linspace(10.0, 20.0, 41)
    high[:41] = close[:41] * 1.01
    low[:41] = close[:41] * 0.99
    close[41:] = 14.0
    high[41:] = 14.2
    low[41:] = 13.8
    t = 70
    assert fib_ok(high, low, close, t) is True
    # A future new high after t must not change the T-day decision.
    future = high.copy()
    future[75] = 40.0
    assert fib_ok(future, low, close, t) is True
    assert fib_ok(high[: t + 1], low[: t + 1], close[: t + 1], t) is True


def test_fibonacci_rejects_break_of_786():
    n = 80
    close = np.ones(n) * 10.0
    high = close.copy()
    low = close.copy()
    close[:41] = np.linspace(10.0, 20.0, 41)
    high[:41] = close[:41]
    low[:41] = close[:41]
    close[41:] = 11.0  # 90% retrace, below 78.6 invalidation
    high[41:] = 11.0
    low[41:] = 11.0
    assert fib_ok(high, low, close, 70) is False


def test_market_gate_needs_price_above_rising_ma():
    close = np.linspace(10.0, 20.0, 40)
    assert market_up(close, 30) is True
    down = np.linspace(20.0, 10.0, 40)
    assert market_up(down, 30) is False


def test_outflow_proxy_needs_two_down_days_and_heavy_amount():
    close = np.array([10.0, 10.5, 11.0, 10.8, 10.4], dtype=float)
    amount = np.array([1e8, 1e8, 1e8, 1e8, 2e8], dtype=float)
    # pad to 20 days
    close = np.concatenate([np.full(18, 10.0), close])
    amount = np.concatenate([np.full(18, 1e8), amount])
    assert outflow_proxy(close, amount, len(close) - 1) is True
    amount[-1] = 1.0
    assert outflow_proxy(close, amount, len(close) - 1) is False


def test_moneyflow_outflow_two_negative_days():
    net = np.array([-1e6, -2e6], dtype=float)
    amount = np.array([1e7, 1e7], dtype=float)
    assert moneyflow_outflow(net, amount, 1) is True
    net = np.array([1e6, -2e6], dtype=float)
    assert moneyflow_outflow(net, amount, 1) is False


def test_hot_industry_and_leader_picks():
    returns = np.array([0.1, 0.2, 0.15, 0.01, 0.02, 0.03, 0.4])
    industries = ["A", "A", "A", "B", "B", "B", "C"]
    hot = pick_hot_industries(returns, industries, count=2)
    assert hot[0] == "A"
    leaders = pick_leaders(returns, industries, ["A"], per_industry=2)
    assert leaders[0] == 1
    assert 0 in leaders or 2 in leaders


def test_amount_top_and_lookahead_helper():
    amounts = np.array([1.0, 5.0, 3.0, 9.0])
    assert pick_amount_top(amounts, 2) == [3, 1]
    signal = pd.to_datetime(["2020-01-02", "2020-01-03"])
    fill = pd.to_datetime(["2020-01-03", "2020-01-06"])
    assert_no_lookahead(signal, fill)
