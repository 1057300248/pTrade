# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ptrade_rmdc_etf import (
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


def _trend(start, drift, n=160, noise=0.0, seed=1):
    rng = np.random.RandomState(seed)
    rets = np.full(n, drift) + rng.normal(0.0, noise, n)
    return start * np.cumprod(1.0 + rets)


def test_residual_momentum_is_idiosyncratic():
    market = _trend(1.0, 0.001, n=180, noise=0.002, seed=1)
    etf = market * _trend(1.0, 0.003, n=180, noise=0.001, seed=2)
    lag = market * _trend(1.0, -0.002, n=180, noise=0.001, seed=3)
    up = residual_momentum(etf, market)
    down = residual_momentum(lag, market)
    assert up > down
    assert up > 0


def test_trend_quality_near_high():
    prices = np.linspace(1.0, 1.2, 120)
    assert trend_quality(prices) > 0.99
    dropped = np.concatenate([prices, np.array([1.0])])
    assert trend_quality(dropped) < 0.90


def test_crowding_flags_volume_spike_and_extension():
    n = 80
    close = np.linspace(1.0, 1.4, n)
    high = close * 1.03
    low = close * 0.97
    volume = np.full(n, 1e6)
    volume[-20:] = 3.5e6
    points = crowding_points(close, high, low, volume)
    assert points >= 2


def test_classify_state_thresholds():
    assert classify_state(0.70, 0.20, False) == STATE_ON
    assert classify_state(0.50, 0.25, False) == STATE_BAL
    assert classify_state(0.20, 0.20, False) == STATE_OFF
    assert classify_state(0.80, 0.50, False) == STATE_OFF
    assert classify_state(0.80, 0.20, True) == STATE_LOCK


def test_growth_breadth():
    assert growth_breadth({"A": 0.1, "B": -0.1, "C": 0.02}, ["A", "B", "C"]) == pytest.approx(2.0 / 3.0)


def test_corr_filter_drops_clone():
    rng = np.random.RandomState(0)
    base = rng.normal(0, 0.01, 60)
    ret_map = {
        "A": base,
        "B": base + rng.normal(0, 0.0001, 60),
        "C": rng.normal(0, 0.01, 60),
    }
    picked = filter_correlated(["A", "B", "C"], ret_map, threshold=0.65)
    assert picked[0] == "A"
    assert "B" not in picked
    assert "C" in picked


def test_inverse_vol_prefers_quiet_name():
    weights = inverse_vol_weights(["A", "B"], {"A": 0.10, "B": 0.40}, cap=0.80)
    assert weights["A"] > weights["B"]
    assert pytest.approx(sum(weights.values()), rel=1e-6) == 1.0


def test_build_targets_lockdown_has_no_growth():
    vols = {c: 0.20 for c in ["G1", "G2", "D1", "D2"]}
    weights = build_targets(
        STATE_LOCK, ["G1", "G2"], ["D1", "D2"], vols,
        growth_corr_high=False, div_all_negative=False,
    )
    assert "G1" not in weights
    assert "G2" not in weights
    assert weights.get("D1", 0) > 0 or weights.get("D2", 0) > 0


def test_build_targets_offense_keeps_diversifier_floor():
    vols = {c: 0.20 for c in ["G1", "G2", "D1", "D2"]}
    weights = build_targets(
        STATE_ON, ["G1", "G2"], ["D1", "D2"], vols,
        growth_corr_high=False, div_all_negative=False,
    )
    div_w = weights.get("D1", 0) + weights.get("D2", 0)
    assert div_w >= 0.20


def test_hysteresis_blocks_small_upgrade():
    kept = apply_hysteresis(["A"], ["B"], {"A": 1.0, "B": 1.1}, gap=1.20)
    assert kept == ["A"]
    kept2 = apply_hysteresis(["A"], ["B"], {"A": 1.0, "B": 1.5}, gap=1.20)
    assert kept2 == ["B"]


def test_crash_and_trailing_stop():
    prices = np.array([10.0, 10.1, 10.0, 9.0, 8.1])
    assert crash_triggered(prices, 0.08, 0.08) is True
    assert trailing_stop_hit(8.0, 10.0, 0.20) is True
    assert trailing_stop_hit(8.5, 10.0, 0.20) is False


def test_lot_shares_rounds_to_100():
    assert lot_shares(1550, 10.0, 100) == 100
    assert lot_shares(50, 10.0, 100) == 0


def test_live_file_has_no_research_deps():
    import re
    path = os.path.join(ROOT, "ptrade_rmdc_etf.py")
    text = open(path, "r", encoding="utf-8").read()
    assert "sklearn" not in text
    assert "import os" not in text
    assert "import sys" not in text
    assert "get_snapshot" not in text
    assert "akshare" not in text
    assert "mootdx" not in text
    assert re.search(r"\bf['\"]", text) is None
