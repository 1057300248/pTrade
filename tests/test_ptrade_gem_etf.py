# -*- coding: utf-8 -*-
import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import ptrade_gem_etf as gem
from ptrade_gem_etf import (
    STATE_BAL,
    STATE_LOCK,
    STATE_OFF,
    STATE_ON,
    build_targets,
    classify_state,
    crash_triggered,
    crowding_points,
    dual_eligible,
    filter_correlated,
    gold_trend_on,
    lot_shares,
    ts_momentum,
)


def test_ts_momentum_uses_252_day_lookback_and_21_day_skip():
    closes = np.arange(1.0, 301.0)

    expected = closes[-21] / closes[-273] - 1.0

    assert np.isclose(ts_momentum(closes), expected)


def test_ts_momentum_falls_back_to_126_days_and_five_day_skip():
    closes = np.arange(1.0, 201.0)

    expected = closes[-5] / closes[-131] - 1.0

    assert np.isclose(ts_momentum(closes), expected)
    assert ts_momentum(np.arange(1.0, 131.0)) == 0.0


def test_dual_eligible_requires_positive_ts_momentum_and_ma120():
    rising = np.linspace(80.0, 160.0, 300)
    falling = np.linspace(160.0, 80.0, 300)
    below_ma = rising.copy()
    below_ma[-1] = 90.0

    assert dual_eligible(rising)
    assert not dual_eligible(falling)
    assert not dual_eligible(below_ma)


def test_gold_trend_requires_ma100_and_positive_twenty_day_return():
    rising = np.linspace(90.0, 130.0, 140)
    weak = rising.copy()
    weak[-21:] = np.linspace(125.0, 110.0, 21)

    assert gold_trend_on(rising)
    assert not gold_trend_on(weak)
    assert not gold_trend_on(rising[:99])


def test_classify_state_uses_frozen_breadth_vol_and_crash_boundaries():
    assert classify_state(0.50, 0.219, False) == STATE_ON
    assert classify_state(0.50, 0.22, False) == STATE_BAL
    assert classify_state(0.35, 0.40, False) == STATE_BAL
    assert classify_state(0.349, 0.10, False) == STATE_OFF
    assert classify_state(0.90, 0.10, True) == STATE_LOCK


def test_build_targets_uses_top_two_and_full_single_name_sleeves():
    vols = {
        "G1": 0.10,
        "G2": 0.10,
        "G3": 0.10,
        "D1": 0.10,
        "D2": 0.10,
        "D3": 0.10,
    }

    offense = build_targets(
        STATE_ON,
        ["G1", "G2", "G3"],
        ["D1", "D2", "D3"],
        vols,
    )
    single = build_targets(
        STATE_ON,
        ["G1"],
        ["D1"],
        vols,
    )

    assert set(offense) == {"G1", "G2", "D1", "D2"}
    assert np.isclose(offense["G1"] + offense["G2"], 0.80)
    assert np.isclose(offense["D1"] + offense["D2"], 0.15)
    assert np.isclose(single["G1"], 0.80)
    assert np.isclose(single["D1"], 0.15)


def test_build_targets_lockdown_excludes_growth():
    targets = build_targets(
        STATE_LOCK,
        ["G1", "G2"],
        ["D1", "D2"],
        {"G1": 0.10, "G2": 0.10, "D1": 0.10, "D2": 0.10},
    )

    assert "G1" not in targets
    assert "G2" not in targets
    assert np.isclose(targets["D1"] + targets["D2"], 0.30)


def test_four_crowding_points_block_new_growth_but_three_do_not():
    original_g = getattr(gem, "g", None)
    gem.g = SimpleNamespace(growth=["FOUR", "THREE"], corr_limit=0.70)
    snapshot = {
        "dual": {"FOUR": True, "THREE": True},
        "crowd": {"FOUR": 4, "THREE": 3},
        "scores": {"FOUR": 2.0, "THREE": 1.0},
        "ret60": {
            "FOUR": np.arange(60.0),
            "THREE": np.arange(60.0)[::-1],
        },
    }
    try:
        assert gem._select_growth(snapshot, held=[]) == ["THREE"]
        assert gem._select_growth(snapshot, held=["FOUR"])[0] == "FOUR"
    finally:
        if original_g is None:
            del gem.g
        else:
            gem.g = original_g


def test_crowding_points_can_reach_four():
    close = np.concatenate(
        [np.full(60, 100.0), np.linspace(101.0, 145.0, 20)]
    )
    high = close * 1.04
    low = close * 0.96
    volume = np.concatenate(
        [np.full(60, 1_000_000.0), np.full(20, 5_000_000.0)]
    )

    assert crowding_points(close, high, low, volume) == 4


def test_filter_correlated_drops_a_near_clone():
    rng = np.random.RandomState(23)
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


def test_crash_and_lot_helpers_copy_live_boundaries():
    assert crash_triggered(np.array([100.0, 94.0]))
    assert crash_triggered(np.array([100.0, 102.0, 101.0, 93.0]))
    assert not crash_triggered(np.array([100.0, 101.0, 100.0, 96.0]))
    assert lot_shares(1_550.0, 10.0, 100) == 100
    assert lot_shares(999.0, 10.0, 100) == 0


def test_live_file_ast_has_only_compatible_imports_and_calls():
    source = (
        Path(__file__).parents[1] / "ptrade_gem_etf.py"
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
    assert "sklearn" not in imports
    assert "get_snapshot" not in calls
    assert "order_target_value" not in calls


def test_initialize_registers_frozen_daily_times():
    source = (
        Path(__file__).parents[1] / "ptrade_gem_etf.py"
    ).read_text(encoding="utf-8")

    assert 'run_daily(context, crash_overlay, time="14:45")' in source
    assert 'run_daily(context, weekly_rebalance, time="14:50")' in source
    assert 'run_daily(context, rebalance_buy, time="14:54")' in source
    assert 'run_daily(context, park_cash_in_repo, time="14:57")' in source
