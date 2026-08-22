# -*- coding: utf-8 -*-
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import regime_etf_rotation as strategy
from regime_etf_rotation import (
    REGIME_RISK_OFF,
    REGIME_RISK_ON,
    combined_score,
    crash_triggered,
    detect_regime,
    efficiency_coefficient,
    eligible_pool,
    lot_size,
    plan_rebalance,
    select_holdings,
    weighted_log_trend_score,
)


def _trend(start, drift, n=80, noise=0.0, seed=1):
    rng = np.random.RandomState(seed)
    rets = np.full(n, drift) + rng.normal(0.0, noise, n)
    prices = start * np.cumprod(1.0 + rets)
    return prices


def test_uptrend_scores_higher_than_downtrend():
    up = _trend(1.0, 0.004, n=80, noise=0.001)
    down = _trend(1.0, -0.004, n=80, noise=0.001)
    up_score = weighted_log_trend_score(up)[2]
    down_score = weighted_log_trend_score(down)[2]
    assert up_score > 0
    assert down_score < 0
    assert up_score > down_score


def test_choppy_series_has_low_r2():
    prices = np.array([1.0, 1.05, 0.98, 1.06, 0.97, 1.04, 0.96, 1.05, 0.95, 1.03,
                       0.97, 1.06, 0.94, 1.05, 0.96, 1.04, 0.95, 1.06, 0.94, 1.05,
                       0.97, 1.04, 0.96, 1.05, 0.95])
    _ann, r2, score = weighted_log_trend_score(prices)
    assert r2 < 0.3
    assert abs(score) < abs(_ann)


def test_crash_filter_on_three_down_days():
    prices = np.array([10.0, 10.1, 10.2, 10.0, 9.4, 8.8, 8.2])
    assert crash_triggered(prices, single_day=0.05, three_day=0.05) is True


def test_crash_filter_false_on_slow_drift():
    prices = _trend(10.0, -0.002, n=30, noise=0.0)
    assert crash_triggered(prices, single_day=0.05, three_day=0.05) is False


def test_efficiency_high_on_straight_move():
    prices = np.linspace(1.0, 1.2, 25)
    _mom, coef, _eff = efficiency_coefficient(prices, prices, prices, prices, window=20)
    assert coef > 0.9


def test_efficiency_low_on_round_trip():
    up = np.linspace(1.0, 1.2, 12)
    down = np.linspace(1.2, 1.0, 13)
    prices = np.concatenate([up, down])
    _mom, coef, _eff = efficiency_coefficient(prices, prices, prices, prices, window=20)
    assert coef < 0.3


def test_combined_score_zero_after_crash():
    prices = np.concatenate([_trend(1.0, 0.005, n=40, noise=0.0), np.array([1.15, 1.05, 0.95])])
    result = combined_score(prices, prices, prices, prices, min_days=20, max_days=40)
    assert result["crashed"] is True
    assert result["score"] == 0.0


def test_regime_switches_with_ma():
    below = np.concatenate([np.full(50, 2.0), np.full(20, 1.5)])
    above = np.concatenate([np.full(50, 2.0), np.full(20, 2.4)])
    assert detect_regime(below, ma_window=60) == REGIME_RISK_OFF
    assert detect_regime(above, ma_window=60) == REGIME_RISK_ON


def test_eligible_pool_filters_in_risk_off():
    all_codes = ["510300.SS", "512480.SS", "518880.SS", "510880.SS"]
    defensive = ["518880.SS", "510880.SS"]
    assert eligible_pool(REGIME_RISK_ON, all_codes, defensive) == all_codes
    assert eligible_pool(REGIME_RISK_OFF, all_codes, defensive) == ["518880.SS", "510880.SS"]


def test_hysteresis_keeps_holding_when_gap_small():
    scores = {"A": 0.40, "B": 0.39, "C": 0.30}
    held = select_holdings(scores, ["A", "C"], hold_num=2, score_floor=0.0, gap=0.15)
    assert "A" in held
    assert "C" in held
    assert "B" not in held


def test_hysteresis_switches_when_gap_large():
    scores = {"A": 0.20, "B": 0.50, "C": 0.10}
    held = select_holdings(scores, ["A", "C"], hold_num=2, score_floor=0.0, gap=0.15)
    assert "B" in held
    assert "C" not in held or scores["C"] >= 0.50 - 0.15


def test_empty_when_all_scores_below_floor():
    scores = {"A": 0.01, "B": -0.2}
    assert select_holdings(scores, ["A"], hold_num=2, score_floor=0.02, gap=0.15) == []


def test_lot_size_rounds_to_board_lot():
    assert lot_size(9500, 10.0) == 900
    assert lot_size(50, 10.0) == 0
    assert lot_size(10000, 0) == 0


def test_strategy_file_has_no_fstrings():
    import ast
    src_path = os.path.join(ROOT, "regime_etf_rotation.py")
    src = open(src_path, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    fstrings = []
    variable_annotations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            fstrings.append(getattr(node, "lineno", "?"))
        if isinstance(node, ast.AnnAssign):
            variable_annotations.append(getattr(node, "lineno", "?"))
    assert fstrings == []
    assert variable_annotations == []
    assert "sklearn" not in src


class _State(object):
    pass


class _Portfolio(object):
    pass


class _Context(object):
    pass


class _Position(object):
    def __init__(self, sid, amount):
        self.sid = sid
        self.amount = amount


class _Log(object):
    def info(self, message):
        return message

    def warning(self, message):
        return message


def _install_runtime_state(monkeypatch, etf_pool):
    state = _State()
    state.etf_pool = list(etf_pool)
    state.pending_orders = {}
    state.cash_reserve = 0.02
    monkeypatch.setattr(strategy, "g", state, raising=False)
    monkeypatch.setattr(strategy, "log", _Log(), raising=False)
    monkeypatch.setattr(strategy, "is_trade", lambda: False, raising=False)
    return state


def test_held_etfs_uses_position_sid_instead_of_four_letter_dict_key(monkeypatch):
    _install_runtime_state(monkeypatch, ["510300.SS"])
    positions = {"510300.XSHG": _Position("510300.SS", 100)}
    monkeypatch.setattr(strategy, "get_positions", lambda: positions, raising=False)

    assert strategy._held_etfs(_Context()) == ["510300.SS"]


def test_load_histories_calls_old_ptrade_one_security_at_a_time(monkeypatch):
    _install_runtime_state(monkeypatch, ["A.SS", "B.SS"])
    calls = []

    def fake_get_history(count, frequency, fields, security, fq=None, include=False):
        calls.append(security)
        return object()

    def fake_parse_history(_hist, codes):
        values = np.array([1.0, 1.1])
        return {
            codes[0]: {
                "open": values,
                "high": values,
                "low": values,
                "close": values,
            }
        }

    monkeypatch.setattr(strategy, "get_history", fake_get_history, raising=False)
    monkeypatch.setattr(strategy, "_parse_history", fake_parse_history)

    result = strategy._load_histories(["A.SS", "B.SS"], 20)

    assert calls == ["A.SS", "B.SS"]
    assert sorted(result.keys()) == ["A.SS", "B.SS"]


def test_align_positions_defers_buys_when_sell_was_submitted(monkeypatch):
    _install_runtime_state(monkeypatch, ["A.SS", "B.SS"])
    context = _Context()
    context.portfolio = _Portfolio()
    context.portfolio.portfolio_value = 100000.0
    context.portfolio.cash = 1000.0
    buys = []
    sells = []

    monkeypatch.setattr(strategy, "_held_etfs", lambda _context: ["A.SS"])
    monkeypatch.setattr(strategy, "_current_price", lambda _code: 10.0)
    monkeypatch.setattr(strategy, "get_position", lambda _code: None, raising=False)
    monkeypatch.setattr(
        strategy,
        "order_target",
        lambda code, amount: sells.append((code, amount)) or "sell-1",
        raising=False,
    )
    monkeypatch.setattr(
        strategy,
        "order",
        lambda code, amount: buys.append((code, amount)) or "buy-1",
        raising=False,
    )

    strategy._align_positions(context, ["B.SS"])

    assert sells == [("A.SS", 0)]
    assert buys == []


def test_align_positions_caps_buy_by_available_cash(monkeypatch):
    _install_runtime_state(monkeypatch, ["A.SS"])
    context = _Context()
    context.portfolio = _Portfolio()
    context.portfolio.portfolio_value = 100000.0
    context.portfolio.cash = 2000.0
    buys = []

    monkeypatch.setattr(strategy, "_held_etfs", lambda _context: [])
    monkeypatch.setattr(strategy, "_current_price", lambda _code: 10.0)
    monkeypatch.setattr(strategy, "get_position", lambda _code: None, raising=False)
    monkeypatch.setattr(
        strategy,
        "order",
        lambda code, amount: buys.append((code, amount)) or "buy-1",
        raising=False,
    )

    strategy._align_positions(context, ["A.SS"])

    assert buys == [("A.SS", 100)]


def test_plan_rebalance_splits_sells_and_buys():
    sells, buys, keeps = plan_rebalance(["A", "B"], ["B", "C"])
    assert sells == ["A"]
    assert buys == ["C"]
    assert keeps == ["B"]


def test_plan_rebalance_empty_target_sells_all():
    sells, buys, keeps = plan_rebalance(["A", "B"], [])
    assert sells == ["A", "B"]
    assert buys == []
    assert keeps == []
