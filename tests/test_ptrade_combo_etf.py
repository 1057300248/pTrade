# -*- coding: utf-8 -*-
import ast
from pathlib import Path

import numpy as np

from ptrade_combo_etf import (
    STATE_BAL,
    STATE_LOCK,
    STATE_OFF,
    STATE_ON,
    _eligible,
    build_targets,
    classify_state,
    combined_score,
    crash_triggered,
    crowding_points,
    filter_correlated,
    lot_shares,
    residual_momentum,
)


def _prices_from_returns(returns):
    return 100.0 * np.cumprod(1.0 + np.asarray(returns, dtype=float))


def test_combined_score_uses_frozen_sixty_forty_blend():
    result = combined_score(2.0, mom63=0.12, vol20=0.24)

    assert np.isclose(result, 0.6 * 2.0 + 0.4 * (0.12 / 0.24))


def test_residual_momentum_rewards_idiosyncratic_acceleration():
    rng = np.random.RandomState(17)
    market_returns = rng.normal(0.0003, 0.008, 301)
    market = _prices_from_returns(market_returns)
    size = _prices_from_returns(
        market_returns + rng.normal(0.0, 0.002, len(market_returns))
    )
    alpha = np.concatenate(
        [np.full(180, -0.001), np.linspace(-0.001, 0.004, 121)]
    )
    rising = _prices_from_returns(market_returns + alpha)
    falling = _prices_from_returns(market_returns - alpha)

    assert residual_momentum(rising, market, size) > residual_momentum(
        falling, market, size
    )


def test_state_thresholds_match_combo_specification():
    assert classify_state(0.50, 0.35, False) == STATE_ON
    assert classify_state(0.49, 0.35, False) == STATE_BAL
    assert classify_state(0.35, 0.45, False) == STATE_BAL
    assert classify_state(0.34, 0.20, False) == STATE_OFF
    assert classify_state(0.80, 0.451, False) == STATE_OFF
    assert classify_state(0.80, 0.20, True) == STATE_LOCK


def test_offense_targets_are_more_aggressive_than_balanced_targets():
    growth = ["G1", "G2", "G3", "G4"]
    diversifiers = ["D1", "D2", "D3"]
    vols = {code: 0.10 for code in growth + diversifiers}

    offense = build_targets(
        STATE_ON, growth, diversifiers, vols, vol_target=0.18)
    balanced = build_targets(
        STATE_BAL, growth, diversifiers, vols, vol_target=0.18)

    offense_growth = sum(offense.get(code, 0.0) for code in growth)
    balanced_growth = sum(balanced.get(code, 0.0) for code in growth)
    offense_div = sum(offense.get(code, 0.0) for code in diversifiers)
    assert np.isclose(offense_growth, 0.85)
    assert np.isclose(offense_div, 0.12)
    assert offense_growth > balanced_growth
    assert len([code for code in growth if code in offense]) == 3
    assert len([code for code in diversifiers if code in offense]) == 2


def test_growth_cluster_halves_growth_sleeve():
    growth = ["G1", "G2", "G3"]
    diversifiers = ["D1", "D2"]
    vols = {code: 0.10 for code in growth + diversifiers}

    normal = build_targets(
        STATE_ON, growth, diversifiers, vols, growth_corr_high=False)
    clustered = build_targets(
        STATE_ON, growth, diversifiers, vols, growth_corr_high=True)

    normal_growth = sum(normal.get(code, 0.0) for code in growth)
    clustered_growth = sum(clustered.get(code, 0.0) for code in growth)
    assert np.isclose(clustered_growth, normal_growth * 0.5)


def test_four_crowding_points_block_but_three_do_not():
    snapshot = {
        "scores": {"THREE": 2.0, "FOUR": 3.0},
        "ret63": {"THREE": 0.10, "FOUR": 0.10},
        "tq": {"THREE": 0.90, "FOUR": 0.90},
        "crowd": {"THREE": 3, "FOUR": 4},
    }

    assert _eligible(["FOUR", "THREE"], snapshot, held=[]) == ["THREE"]
    assert _eligible(["FOUR"], snapshot, held=["FOUR"]) == ["FOUR"]


def test_crowding_points_can_reach_four():
    close = np.concatenate(
        [np.full(60, 100.0), np.linspace(101.0, 145.0, 20)]
    )
    high = close * 1.04
    low = close * 0.96
    volume = np.concatenate(
        [np.full(60, 1_000_000.0), np.full(20, 4_000_000.0)]
    )

    assert crowding_points(close, high, low, volume) == 4


def test_default_correlation_filter_is_point_seven():
    rng = np.random.RandomState(19)
    first = rng.normal(0.0, 0.01, 80)
    returns = {
        "A": first,
        "CLONE": first + rng.normal(0.0, 0.00001, 80),
        "B": rng.normal(0.0, 0.01, 80),
    }

    selected = filter_correlated(["A", "CLONE", "B"], returns)

    assert selected[0] == "A"
    assert "CLONE" not in selected
    assert "B" in selected


def test_crash_defaults_are_six_percent_one_day_or_eight_percent_three_day():
    one_day = np.array([100.0, 101.0, 102.0, 100.0, 94.0])
    three_day = np.array([100.0, 102.0, 101.0, 95.0, 93.0])
    stable = np.array([100.0, 101.0, 102.0, 100.0, 96.0])

    assert crash_triggered(one_day)
    assert crash_triggered(three_day)
    assert not crash_triggered(stable)


def test_lot_shares_rounds_down_to_exchange_lots():
    assert lot_shares(1_550.0, 10.0, 100) == 100
    assert lot_shares(999.0, 10.0, 100) == 0
    assert lot_shares(1_550.0, 10.0, 1) == 155


def test_live_file_uses_numpy_without_f_strings_or_snapshot_calls():
    source = (
        Path(__file__).parents[1] / "ptrade_combo_etf.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert imports == {"numpy"}
    assert not any(isinstance(node, ast.JoinedStr) for node in ast.walk(tree))
    assert "get_snapshot" not in calls
