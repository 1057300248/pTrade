# -*- coding: utf-8 -*-
"""EvoQuant Wave 2 candidate W2-CROWD: causal percentile crowding score.

Research-only companion to ``research/evoquant_wave2_plan.md`` and
``research/evoquant_genome_wave2.json``. It re-expresses the incumbent
fixed-threshold ``crowding_points`` from ``ptrade_adm_etf.py`` as raw
component values, then re-scores each component against causal rolling
percentiles of the asset's own history:

- only observations strictly before the signal bar are used, with a
  trailing maximum of 1,250 sessions;
- at least 252 prior component observations are required, otherwise the
  percentile score is ``None`` and callers fall back to the incumbent
  fixed-threshold ``crowding_points``;
- volume heat, price extension and amplitude trigger in the upper tail at
  ``percentile``; price-volume correlation triggers in the lower tail at
  ``1 - percentile``;
- the aggregate veto is unchanged: the score stays 0-4 and callers still
  block risk assets at >= 4.

The IS grid ``percentile in {0.90, 0.95}`` belongs to the runner, not to
this module. The live strategy file is imported only to reuse the incumbent
formulas; it is never modified.
"""
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ptrade_adm_etf as strategy


COMPONENT_NAMES = (
    "volume_heat",
    "price_extension",
    "price_volume_correlation",
    "amplitude",
)
LOWER_TAIL_COMPONENTS = ("price_volume_correlation",)
HISTORY_SESSIONS = 1250
MIN_PRIOR_OBSERVATIONS = 252
# Same minimum bar count as the incumbent crowding_points.
MIN_COMPONENT_BARS = 61


def _finite_or_none(value):
    value = float(value)
    if not np.isfinite(value):
        return None
    return value


def crowding_component_values(closes, highs, lows, volumes):
    """Return dict with keys volume_heat, price_extension, amplitude,
    price_volume_correlation.

    Values are raw floats or None if not computable. Same windows as live
    crowding_points: 20/60-session volume means, 60-session close mean,
    20-session price-volume correlation (reusing the live ``_corr``, so a
    degenerate window keeps its incumbent 0.0 value) and 20-session
    high-low amplitude over the previous close.
    """
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    values = {name: None for name in COMPONENT_NAMES}
    count = min(len(closes), len(highs), len(lows), len(volumes))
    if count < MIN_COMPONENT_BARS:
        return values
    closes = closes[-count:]
    highs = highs[-count:]
    lows = lows[-count:]
    volumes = volumes[-count:]

    volume20 = float(np.mean(volumes[-20:]))
    volume60 = float(np.mean(volumes[-60:]))
    if volume60 > 0:
        values["volume_heat"] = _finite_or_none(volume20 / volume60)

    ma60 = float(np.mean(closes[-60:]))
    if ma60 > 0:
        values["price_extension"] = _finite_or_none(closes[-1] / ma60 - 1.0)

    values["price_volume_correlation"] = _finite_or_none(
        strategy._corr(closes[-20:], volumes[-20:])
    )

    previous = closes[-21:-1]
    amplitude = (highs[-20:] - lows[-20:]) / np.maximum(previous, 1e-8)
    values["amplitude"] = _finite_or_none(np.mean(amplitude))
    return values


def crowding_points_percentile(prior_components, current_components,
                               percentile, min_obs=MIN_PRIOR_OBSERVATIONS):
    """prior_components: list[dict] strictly earlier days, newest last,
    already truncated to 1250.

    Return int 0-4, or None if len(prior_components) < min_obs. Any
    component with fewer than ``min_obs`` non-None prior observations also
    returns None, so the caller falls back to the incumbent
    fixed-threshold ``crowding_points``. A None current component simply
    never triggers.
    """
    percentile = float(percentile)
    if not 0.0 < percentile < 1.0:
        raise ValueError("percentile must be strictly inside (0, 1)")
    min_obs = int(min_obs)
    if prior_components is None or len(prior_components) < min_obs:
        return None

    points = 0
    for name in COMPONENT_NAMES:
        history = [
            observation.get(name)
            for observation in prior_components
            if observation.get(name) is not None
        ]
        if len(history) < min_obs:
            return None
        current = current_components.get(name)
        if current is None:
            continue
        if name in LOWER_TAIL_COMPONENTS:
            threshold = float(np.quantile(history, 1.0 - percentile))
            triggered = float(current) <= threshold
        else:
            threshold = float(np.quantile(history, percentile))
            triggered = float(current) >= threshold
        if triggered:
            points += 1
    return int(min(4, points))


def crowd_map_for_index(panel, counts, codes, index, percentile,
                        calendar=None, history_sessions=HISTORY_SESSIONS,
                        min_obs=MIN_PRIOR_OBSERVATIONS, incumbent_fn=None):
    """Convenience: build {code: points} at calendar index.

    If percentile path returns None, use incumbent_fn(closes, highs, lows,
    volumes) or import ptrade_adm_etf.crowding_points. MUST be causal: do
    not include bar ``index`` in the percentile history.

    ``calendar`` is accepted for engine-call compatibility; the ``counts``
    row already encodes the calendar position, exactly as in
    ``research.ablate_adm_knobs.build_counts``.
    """
    if incumbent_fn is None:
        incumbent_fn = strategy.crowding_points
    history_sessions = int(history_sessions)

    crowd = {}
    for code in codes:
        bars = panel[code]
        count = int(counts[code][index])
        closes = bars["close"][:count]
        highs = bars["high"][:count]
        lows = bars["low"][:count]
        volumes = bars["volume"][:count]

        current = crowding_component_values(closes, highs, lows, volumes)
        # Prior sessions are the asset's own bars strictly before bar
        # ``count`` (the bar at calendar ``index``), trailing at most
        # ``history_sessions``; earlier bar counts cannot produce a
        # component value, so they are skipped.
        first = max(MIN_COMPONENT_BARS, count - history_sessions)
        # Cache on the panel object, not on ``id(close)``. Numpy array
        # identities are reused after GC, so a process-global id() map
        # can return another test's (or another series') components.
        cache = panel.setdefault("__wave2_crowd_cache__", {})
        prior = []
        for prior_count in range(first, count):
            key = (code, prior_count)
            values = cache.get(key)
            if values is None:
                values = crowding_component_values(
                    bars["close"][:prior_count],
                    bars["high"][:prior_count],
                    bars["low"][:prior_count],
                    bars["volume"][:prior_count],
                )
                cache[key] = values
            prior.append(values)

        points = crowding_points_percentile(
            prior, current, percentile, min_obs=min_obs)
        if points is None:
            points = incumbent_fn(closes, highs, lows, volumes)
        crowd[code] = int(points)
    return crowd
