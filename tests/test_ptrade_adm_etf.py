# -*- coding: utf-8 -*-
import ast
from pathlib import Path

import numpy as np

from ptrade_adm_etf import (
    BOND,
    RISK,
    build_targets,
    crash_triggered,
    crowding_points,
    lot_shares,
    month_gate,
    pick_risk_asset,
    ts_momentum,
)


def test_frozen_asset_class_universe():
    assert RISK == [
        "510300.SS",
        "159915.SZ",
        "513100.SS",
        "518880.SS",
    ]
    assert BOND == "511010.SS"


def test_ts_momentum_uses_252_day_lookback_and_21_day_skip():
    closes = np.arange(1.0, 301.0)

    expected = closes[-21] / closes[-273] - 1.0

    assert np.isclose(ts_momentum(closes), expected)


def test_ts_momentum_uses_126_day_fallback_then_zero():
    closes = np.arange(1.0, 201.0)

    expected = closes[-5] / closes[-131] - 1.0

    assert np.isclose(ts_momentum(closes), expected)
    assert ts_momentum(np.arange(1.0, 131.0)) == 0.0


def test_month_gate_requires_positive_21_session_return():
    rising = np.linspace(100.0, 110.0, 22)
    flat = np.full(22, 100.0)
    falling = np.linspace(110.0, 100.0, 22)

    assert month_gate(rising)
    assert not month_gate(flat)
    assert not month_gate(falling)
    assert not month_gate(rising[:21])


def test_pick_risk_asset_selects_highest_fully_eligible_score():
    scores = {
        "510300.SS": 0.20,
        "159915.SZ": 0.40,
        "513100.SS": 0.30,
        "518880.SS": 0.10,
    }
    gates = {code: True for code in RISK}
    crowds = {code: 0 for code in RISK}

    assert pick_risk_asset(scores, gates, crowds) == "159915.SZ"


def test_pick_risk_asset_applies_ts_month_and_crowding_gates():
    scores = {
        "510300.SS": -0.10,
        "159915.SZ": 0.40,
        "513100.SS": 0.30,
        "518880.SS": 0.10,
    }
    gates = {
        "510300.SS": True,
        "159915.SZ": False,
        "513100.SS": True,
        "518880.SS": True,
    }
    crowds = {
        "510300.SS": 0,
        "159915.SZ": 0,
        "513100.SS": 4,
        "518880.SS": 3,
    }

    assert pick_risk_asset(scores, gates, crowds) == "518880.SS"
    crowds["518880.SS"] = 4
    assert pick_risk_asset(scores, gates, crowds) is None


def test_build_targets_falls_back_to_95_percent_bonds():
    assert build_targets(None, None) == {BOND: 0.95}
    assert build_targets("510300.SS", 0.0) == {BOND: 0.95}
    assert build_targets("510300.SS", np.nan) == {BOND: 0.95}


def test_build_targets_scales_winner_and_places_remainder_in_bonds():
    targets = build_targets("513100.SS", 0.24)

    assert np.isclose(targets["513100.SS"], 2.0 / 3.0)
    assert np.isclose(targets[BOND], 1.0 / 3.0)


def test_build_targets_caps_winner_at_one():
    targets = build_targets("518880.SS", 0.06)

    assert np.isclose(targets["518880.SS"], 1.0)
    assert np.isclose(targets[BOND], 0.0)


def test_crowding_points_can_reach_the_blocking_value_four():
    close = np.concatenate(
        [np.full(60, 100.0), np.linspace(101.0, 145.0, 20)]
    )
    high = close * 1.04
    low = close * 0.96
    volume = np.concatenate(
        [np.full(60, 1_000_000.0), np.full(20, 5_000_000.0)]
    )

    assert crowding_points(close, high, low, volume) == 4


def test_crash_trigger_uses_six_percent_day_or_eight_percent_three_day():
    assert crash_triggered(np.array([100.0, 94.0]))
    assert crash_triggered(np.array([100.0, 102.0, 101.0, 91.0]))
    assert not crash_triggered(np.array([100.0, 101.0, 100.0, 96.0]))


def test_lot_shares_rounds_down_to_exchange_lots():
    assert lot_shares(1_550.0, 10.0, 100) == 100
    assert lot_shares(999.0, 10.0, 100) == 0
    assert lot_shares(1_550.0, 10.0, 1) == 155


def test_live_file_ast_bans_incompatible_syntax_imports_and_calls():
    source = (
        Path(__file__).parents[1] / "ptrade_adm_etf.py"
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
    assert imports.isdisjoint({"pandas", "sklearn", "os", "sys"})
    assert "get_snapshot" not in calls
    assert "order_target_value" not in calls


def test_execution_callbacks_match_the_frozen_constitution():
    source = (
        Path(__file__).parents[1] / "ptrade_adm_etf.py"
    ).read_text(encoding="utf-8")

    assert 'run_daily(context, crash_overlay, time="14:45")' in source
    assert 'run_daily(context, weekly_rebalance, time="14:50")' in source
    assert 'run_daily(context, rebalance_buy, time="14:54")' in source
    assert 'run_daily(context, park_cash_in_repo, time="14:57")' in source
    assert "def handle_data(context, data):\n    return" in source
