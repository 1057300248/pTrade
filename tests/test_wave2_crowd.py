# -*- coding: utf-8 -*-
"""Tests for the Wave 2 W2-CROWD causal percentile crowding module."""
import ast
from pathlib import Path

import numpy as np
import pytest

import ptrade_adm_etf as strategy
from research.wave2_crowd import (
    crowd_map_for_index,
    crowding_component_values,
    crowding_points_percentile,
)


CODE = "TEST.SS"
COMPONENT_KEYS = {
    "volume_heat",
    "price_extension",
    "price_volume_correlation",
    "amplitude",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _baseline_series(days=100):
    """Gently rising close and volume: no live crowding component trips."""
    t = np.arange(days, dtype=float)
    closes = 1.0 + 0.0002 * t
    volumes = 1000.0 + t
    highs = closes * 1.001
    lows = closes * 0.999
    return closes, highs, lows, volumes


def _fixed_threshold_points(components):
    """Re-score raw component values with the live fixed thresholds."""
    points = 0
    if components["volume_heat"] is not None and components["volume_heat"] > 2.0:
        points += 1
    if (
        components["price_extension"] is not None
        and components["price_extension"] > 0.15
    ):
        points += 1
    if (
        components["price_volume_correlation"] is not None
        and components["price_volume_correlation"] < 0.10
    ):
        points += 1
    if components["amplitude"] is not None and components["amplitude"] > 0.04:
        points += 1
    return min(4, points)


def _observation(volume_heat=0.5, price_extension=0.0,
                 price_volume_correlation=0.5, amplitude=0.01):
    return {
        "volume_heat": volume_heat,
        "price_extension": price_extension,
        "price_volume_correlation": price_volume_correlation,
        "amplitude": amplitude,
    }


def _make_panel(closes, highs, lows, volumes, code=CODE):
    closes = np.asarray(closes, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    days = len(closes)
    dates = (np.datetime64("2020-01-01") + np.arange(days)).astype(
        "datetime64[ns]"
    )
    bars = {
        "dates": dates,
        "high": np.asarray(highs, dtype=float),
        "low": np.asarray(lows, dtype=float),
        "close": closes,
        "volume": volumes,
        "amount": closes * volumes,
    }
    counts = {code: np.searchsorted(bars["dates"], dates, side="right")}
    return {code: bars}, counts


def _components_at(arrays, count):
    closes, highs, lows, volumes = arrays
    return crowding_component_values(
        closes[:count], highs[:count], lows[:count], volumes[:count]
    )


def _random_arrays(days, seed):
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, size=days)))
    spread = np.abs(rng.normal(0.01, 0.01, size=days)) * closes
    highs = closes + spread
    lows = closes - spread
    volumes = np.exp(rng.normal(7.0, 0.6, size=days))
    return closes, highs, lows, volumes


# ---------------------------------------------------------------------------
# Component values match the live fixed-threshold triggers
# ---------------------------------------------------------------------------
def test_baseline_series_trips_no_component():
    closes, highs, lows, volumes = _baseline_series()

    components = crowding_component_values(closes, highs, lows, volumes)

    assert set(components) == COMPONENT_KEYS
    assert components["volume_heat"] < 2.0
    assert components["price_extension"] < 0.15
    assert components["price_volume_correlation"] >= 0.10
    assert components["amplitude"] < 0.04
    assert _fixed_threshold_points(components) == 0
    assert strategy.crowding_points(closes, highs, lows, volumes) == 0


def test_volume_heat_value_matches_live_trigger():
    closes, highs, lows, volumes = _baseline_series()
    volumes = volumes.copy()
    volumes[-20:] *= 5.0

    components = crowding_component_values(closes, highs, lows, volumes)

    assert components["volume_heat"] > 2.0
    assert np.isclose(
        components["volume_heat"],
        np.mean(volumes[-20:]) / np.mean(volumes[-60:]),
    )
    assert _fixed_threshold_points(components) == 1
    assert strategy.crowding_points(closes, highs, lows, volumes) == 1


def test_price_extension_value_matches_live_trigger():
    closes, highs, lows, volumes = _baseline_series()
    closes = closes.copy()
    closes[-10:] = np.linspace(closes[-11], 1.25, 10)
    highs = closes * 1.001
    lows = closes * 0.999

    components = crowding_component_values(closes, highs, lows, volumes)

    assert components["price_extension"] > 0.15
    assert np.isclose(
        components["price_extension"],
        closes[-1] / np.mean(closes[-60:]) - 1.0,
    )
    assert _fixed_threshold_points(components) == 1
    assert strategy.crowding_points(closes, highs, lows, volumes) == 1


def test_price_volume_correlation_value_matches_live_trigger():
    closes, highs, lows, volumes = _baseline_series()
    volumes = volumes.copy()
    volumes[-20:] = np.linspace(1200.0, 800.0, 20)

    components = crowding_component_values(closes, highs, lows, volumes)

    assert components["price_volume_correlation"] < 0.10
    assert np.isclose(
        components["price_volume_correlation"],
        np.corrcoef(closes[-20:], volumes[-20:])[0, 1],
    )
    assert _fixed_threshold_points(components) == 1
    assert strategy.crowding_points(closes, highs, lows, volumes) == 1


def test_amplitude_value_matches_live_trigger():
    closes, highs, lows, volumes = _baseline_series()
    highs = highs.copy()
    lows = lows.copy()
    highs[-20:] = closes[-20:] * 1.03
    lows[-20:] = closes[-20:] * 0.97

    components = crowding_component_values(closes, highs, lows, volumes)

    assert components["amplitude"] > 0.04
    assert np.isclose(
        components["amplitude"],
        np.mean(
            (highs[-20:] - lows[-20:]) / np.maximum(closes[-21:-1], 1e-8)
        ),
    )
    assert _fixed_threshold_points(components) == 1
    assert strategy.crowding_points(closes, highs, lows, volumes) == 1


def test_all_four_components_trip_together_like_live():
    closes, highs, lows, volumes = _baseline_series()
    closes = closes.copy()
    closes[-10:] = np.linspace(closes[-11], 1.25, 10)
    volumes = volumes.copy()
    volumes[-20:] = np.linspace(6000.0, 5000.0, 20)
    highs = closes * 1.001
    lows = closes * 0.999
    highs[-20:] = closes[-20:] * 1.03
    lows[-20:] = closes[-20:] * 0.97

    components = crowding_component_values(closes, highs, lows, volumes)

    assert _fixed_threshold_points(components) == 4
    assert strategy.crowding_points(closes, highs, lows, volumes) == 4


def test_short_series_yields_none_components_like_live_zero():
    closes, highs, lows, volumes = _baseline_series(60)

    components = crowding_component_values(closes, highs, lows, volumes)

    assert all(value is None for value in components.values())
    assert _fixed_threshold_points(components) == 0
    assert strategy.crowding_points(closes, highs, lows, volumes) == 0

    at_61 = crowding_component_values(*_baseline_series(61))
    assert all(value is not None for value in at_61.values())


# ---------------------------------------------------------------------------
# Percentile scoring
# ---------------------------------------------------------------------------
def test_warmup_below_min_obs_returns_none():
    prior = [_observation() for _ in range(251)]
    current = _observation()

    assert crowding_points_percentile(prior, current, 0.95) is None
    assert crowding_points_percentile([], current, 0.95) is None
    # Exactly 252 constant observations score: >= / <= make equality trigger.
    assert crowding_points_percentile(prior + [_observation()], current,
                                      0.95) == 4
    # Custom min_obs is honored.
    assert crowding_points_percentile(prior[:10], current, 0.95,
                                      min_obs=10) == 4
    assert crowding_points_percentile(prior[:9], current, 0.95,
                                      min_obs=10) is None


def test_component_with_too_few_valid_observations_returns_none():
    prior = [_observation() for _ in range(252)]
    prior[0] = _observation(volume_heat=None)

    assert crowding_points_percentile(prior, _observation(), 0.95) is None


def test_none_current_component_never_triggers():
    prior = [_observation() for _ in range(252)]
    current = _observation(volume_heat=None, price_extension=9.9,
                           price_volume_correlation=-9.9, amplitude=9.9)

    assert crowding_points_percentile(prior, current, 0.95) == 3


def test_upper_and_lower_tail_directions():
    heat_history = np.linspace(1.0, 3.0, 252)
    corr_history = np.linspace(-1.0, 1.0, 252)
    prior = [
        _observation(
            volume_heat=float(heat),
            price_extension=0.10,
            price_volume_correlation=float(corr),
            amplitude=0.05,
        )
        for heat, corr in zip(heat_history, corr_history)
    ]
    hot = _observation(volume_heat=3.5, price_extension=0.0,
                       price_volume_correlation=-0.95, amplitude=0.0)
    calm = _observation(volume_heat=1.5, price_extension=0.0,
                        price_volume_correlation=0.5, amplitude=0.0)
    boundary = _observation(
        volume_heat=float(np.quantile(heat_history, 0.90)),
        price_extension=0.0,
        price_volume_correlation=0.5,
        amplitude=0.0,
    )

    assert hot["volume_heat"] >= np.quantile(heat_history, 0.90)
    assert hot["price_volume_correlation"] <= np.quantile(corr_history, 0.10)
    assert crowding_points_percentile(prior, hot, 0.90) == 2
    assert crowding_points_percentile(prior, calm, 0.90) == 0
    # Upper-tail comparison is inclusive at the threshold.
    assert crowding_points_percentile(prior, boundary, 0.90) == 1


def test_percentile_090_and_095_differ_on_constructed_tail():
    heat_history = np.arange(1.0, 253.0)
    prior = [
        _observation(volume_heat=float(heat), price_extension=1.0,
                     price_volume_correlation=0.0, amplitude=1.0)
        for heat in heat_history
    ]
    current = _observation(volume_heat=230.0, price_extension=0.0,
                           price_volume_correlation=1.0, amplitude=0.0)

    assert np.quantile(heat_history, 0.90) <= 230.0
    assert np.quantile(heat_history, 0.95) > 230.0
    assert crowding_points_percentile(prior, current, 0.90) == 1
    assert crowding_points_percentile(prior, current, 0.95) == 0


def test_adding_todays_extreme_to_history_would_change_the_score():
    """The score must come from strictly-prior history: appending today's
    extreme observation to the history moves the quantile past today's
    value, so a non-causal implementation would flip the trigger."""
    prior = [
        _observation(volume_heat=1.0, price_extension=0.10,
                     price_volume_correlation=0.5, amplitude=0.10)
        for _ in range(226)
    ] + [
        _observation(volume_heat=10.0, price_extension=0.10,
                     price_volume_correlation=0.5, amplitude=0.10)
        for _ in range(26)
    ]
    current = _observation(volume_heat=9.5, price_extension=0.0,
                           price_volume_correlation=0.9, amplitude=0.0)

    heat_history = [obs["volume_heat"] for obs in prior]
    assert np.isclose(np.quantile(heat_history, 0.90), 9.1)
    assert np.isclose(np.quantile(heat_history + [9.5], 0.90), 9.9)
    assert crowding_points_percentile(prior, current, 0.90) == 1
    assert crowding_points_percentile(prior + [current], current, 0.90) == 0


def test_percentile_outside_unit_interval_is_rejected():
    prior = [_observation() for _ in range(252)]

    with pytest.raises(ValueError):
        crowding_points_percentile(prior, _observation(), 1.0)
    with pytest.raises(ValueError):
        crowding_points_percentile(prior, _observation(), 0.0)


# ---------------------------------------------------------------------------
# crowd_map_for_index
# ---------------------------------------------------------------------------
def test_crowd_map_falls_back_to_incumbent_before_warmup():
    arrays = _baseline_series(130)
    panel, counts = _make_panel(*arrays)

    # index 119 has bars 0..119, so only 59 strictly-prior computable
    # component observations: below min_obs, incumbent path.
    before = crowd_map_for_index(
        panel, counts, [CODE], 119, 0.90, min_obs=60,
        incumbent_fn=lambda *series: 7,
    )
    # A non-causal implementation would count bar 119 itself as the 60th
    # observation and take the percentile path here instead.
    assert before == {CODE: 7}

    default_incumbent = crowd_map_for_index(
        panel, counts, [CODE], 119, 0.90, min_obs=60)
    closes, highs, lows, volumes = arrays
    assert default_incumbent == {
        CODE: strategy.crowding_points(
            closes[:120], highs[:120], lows[:120], volumes[:120])
    }

    # One session later the 60th prior observation exists: percentile path.
    after = crowd_map_for_index(
        panel, counts, [CODE], 120, 0.90, min_obs=60,
        incumbent_fn=lambda *series: 7,
    )
    current = _components_at(arrays, 121)
    prior = [_components_at(arrays, count) for count in range(61, 121)]
    expected = crowding_points_percentile(prior, current, 0.90, min_obs=60)
    assert after == {CODE: expected}
    assert after[CODE] != 7


def test_crowd_map_percentile_history_is_causal_on_random_panel():
    days = 200
    min_obs = 60
    percentile = 0.90
    arrays = _random_arrays(days, seed=0)
    panel, counts = _make_panel(*arrays)

    flips = 0
    for index in range(150, days):
        count = index + 1
        current = _components_at(arrays, count)
        prior = [_components_at(arrays, c) for c in range(61, count)]
        causal = crowding_points_percentile(
            prior, current, percentile, min_obs=min_obs)
        polluted = crowding_points_percentile(
            prior + [current], current, percentile, min_obs=min_obs)

        got = crowd_map_for_index(
            panel, counts, [CODE], index, percentile, min_obs=min_obs)
        assert causal is not None
        assert got == {CODE: causal}
        if polluted != causal:
            flips += 1

    # The panel is built so that at least one day flips if bar `index`
    # leaked into its own history, so the equality above has teeth.
    assert flips > 0


def test_crowd_map_ignores_bars_after_the_signal_index():
    days = 220
    index = 180
    arrays = _random_arrays(days, seed=1)
    panel, counts = _make_panel(*arrays)
    truncated = tuple(series[: index + 1] for series in arrays)
    truncated_panel, truncated_counts = _make_panel(*truncated)

    full = crowd_map_for_index(
        panel, counts, [CODE], index, 0.90, min_obs=60)
    causal = crowd_map_for_index(
        truncated_panel, truncated_counts, [CODE], index, 0.90, min_obs=60)

    assert full == causal


def test_crowd_map_truncates_history_to_trailing_sessions():
    days = 260
    closes = np.full(days, 3.0)
    closes[:120] = np.linspace(1.0, 3.0, 120)
    closes[-1] = 3.15
    highs = closes * 1.001
    lows = closes * 0.999
    volumes = np.full(days, 1000.0)
    arrays = (closes, highs, lows, volumes)
    panel, counts = _make_panel(*arrays)
    index = days - 1

    current = _components_at(arrays, days)
    prior_full = [_components_at(arrays, c) for c in range(61, days)]
    prior_trailing = [
        _components_at(arrays, c) for c in range(days - 100, days)
    ]

    full = crowd_map_for_index(
        panel, counts, [CODE], index, 0.90, min_obs=60)
    trailing = crowd_map_for_index(
        panel, counts, [CODE], index, 0.90, min_obs=60,
        history_sessions=100)

    assert full == {
        CODE: crowding_points_percentile(
            prior_full, current, 0.90, min_obs=60)
    }
    assert trailing == {
        CODE: crowding_points_percentile(
            prior_trailing, current, 0.90, min_obs=60)
    }
    # Today's mild 4.9% extension is extreme against the trailing flat
    # window but ordinary against the older uptrend, so the trailing
    # window must actually be applied.
    assert full == {CODE: 2}
    assert trailing == {CODE: 4}


# ---------------------------------------------------------------------------
# Dependency policy
# ---------------------------------------------------------------------------
def test_module_imports_stay_minimal_and_sklearn_free():
    source = (
        Path(__file__).resolve().parents[1] / "research" / "wave2_crowd.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])

    assert "sklearn" not in imports
    assert imports <= {"os", "sys", "numpy", "ptrade_adm_etf"}
