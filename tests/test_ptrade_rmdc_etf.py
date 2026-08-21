# -*- coding: utf-8 -*-
import re
from pathlib import Path

import numpy as np

from ptrade_rmdc_etf import (
    DIVERSIFIER,
    GROWTH,
    STATE_BAL,
    STATE_LOCK,
    STATE_OFF,
    STATE_ON,
    apply_hysteresis,
    build_targets,
    classify_state,
    crash_triggered,
    crowding_points,
    filter_correlated,
    growth_breadth,
    inverse_vol_weights,
    lot_shares,
    residual_momentum,
    trailing_stop_hit,
    trend_quality,
)


def _prices_from_returns(returns):
    return 100.0 * np.cumprod(1.0 + np.asarray(returns, dtype=float))


def test_residual_momentum_ranks_idiosyncratic_trends_around_market():
    rng = np.random.RandomState(7)
    market_returns = rng.normal(0.0004, 0.008, 181)
    market = _prices_from_returns(market_returns)
    idiosyncratic = np.concatenate(
        [np.full(100, -0.0015), np.linspace(-0.0015, 0.0045, 81)]
    )
    uptrend = _prices_from_returns(market_returns + idiosyncratic)
    downtrend = _prices_from_returns(market_returns - idiosyncratic)

    up_score = residual_momentum(uptrend, market)
    market_score = residual_momentum(market, market)
    down_score = residual_momentum(downtrend, market)

    assert up_score > market_score > down_score


def test_trend_quality_detects_crash_from_high():
    monotonic = np.linspace(100.0, 130.0, 120)
    crashed = monotonic.copy()
    crashed[-1] = 100.0

    assert np.isclose(trend_quality(monotonic), 1.0)
    assert trend_quality(crashed) < 0.90


def test_crowding_points_count_volume_spike_and_price_extension():
    close = np.concatenate([np.full(60, 100.0), np.linspace(101.0, 140.0, 20)])
    high = close * 1.01
    low = close * 0.99
    volume = np.concatenate([np.full(60, 1_000_000.0), np.full(20, 3_000_000.0)])

    assert crowding_points(close, high, low, volume) >= 2


def test_classify_state_thresholds_and_lockdown_override():
    assert classify_state(0.70, 0.20, False) == STATE_ON
    assert classify_state(0.50, 0.25, False) == STATE_BAL
    assert classify_state(0.20, 0.20, False) == STATE_OFF
    assert classify_state(0.80, 0.50, False) == STATE_OFF
    assert classify_state(0.80, 0.20, True) == STATE_LOCK


def test_growth_breadth_counts_positive_growth_names():
    returns = {"A": 0.10, "B": -0.05, "C": 0.02}
    assert np.isclose(growth_breadth(returns, ["A", "B", "C"]), 2.0 / 3.0)
    assert isinstance(GROWTH, (list, tuple))
    assert isinstance(DIVERSIFIER, (list, tuple))


def test_filter_correlated_drops_near_clone_of_first_name():
    rng = np.random.RandomState(11)
    first = rng.normal(0.0, 0.01, 80)
    returns = {
        "A": first,
        "A_CLONE": first + rng.normal(0.0, 0.00001, 80),
        "B": rng.normal(0.0, 0.01, 80),
    }

    selected = filter_correlated(["A", "A_CLONE", "B"], returns, threshold=0.65)

    assert selected[0] == "A"
    assert "A_CLONE" not in selected
    assert "B" in selected


def test_inverse_vol_weights_prefer_lower_vol_and_sum_to_one():
    weights = inverse_vol_weights(["LOW", "HIGH"], {"LOW": 0.10, "HIGH": 0.40}, cap=0.80)

    assert weights["LOW"] > weights["HIGH"]
    assert np.isclose(sum(weights.values()), 1.0, rtol=1e-9, atol=1e-12)


def test_build_targets_lockdown_excludes_growth_names():
    vols = {"G1": 0.20, "G2": 0.20, "D1": 0.20, "D2": 0.20}

    targets = build_targets(
        STATE_LOCK,
        ["G1", "G2"],
        ["D1", "D2"],
        vols,
        growth_corr_high=False,
        div_all_negative=False,
    )

    assert "G1" not in targets
    assert "G2" not in targets


def test_build_targets_offense_keeps_diversifier_floor():
    vols = {"G1": 0.20, "G2": 0.20, "D1": 0.20, "D2": 0.20}

    targets = build_targets(
        STATE_ON,
        ["G1", "G2"],
        ["D1", "D2"],
        vols,
        growth_corr_high=False,
        div_all_negative=False,
    )

    assert targets.get("D1", 0.0) + targets.get("D2", 0.0) >= 0.20


def test_hysteresis_requires_twenty_percent_score_improvement():
    scores = {"A": 1.0, "B": 1.1}
    assert apply_hysteresis(["A"], ["B"], scores, gap=1.20) == ["A"]

    scores["B"] = 1.5
    assert apply_hysteresis(["A"], ["B"], scores, gap=1.20) == ["B"]


def test_crash_trigger_and_trailing_stop_boundaries():
    crash = np.array([100.0, 101.0, 100.0, 99.0, 90.0])
    stable = np.array([100.0, 101.0, 100.0, 99.0, 98.0])

    assert crash_triggered(crash, single_day=0.08, three_day=0.08)
    assert not crash_triggered(stable, single_day=0.08, three_day=0.08)
    assert trailing_stop_hit(80.0, 100.0, 0.20)
    assert not trailing_stop_hit(80.01, 100.0, 0.20)


def test_lot_shares_rounds_down_to_hundred_share_lots():
    assert lot_shares(1_550.0, 10.0, 100) == 100
    assert lot_shares(999.0, 10.0, 100) == 0
    assert lot_shares(2_999.0, 10.0, 100) == 200


def test_live_file_avoids_forbidden_dependencies_and_f_strings():
    source = (Path(__file__).parents[1] / "ptrade_rmdc_etf.py").read_text(encoding="utf-8")

    for forbidden in ("sklearn", "import os", "import sys", "get_snapshot", "akshare", "mootdx"):
        assert forbidden not in source
    assert re.search(r"\bf['\"]", source) is None
