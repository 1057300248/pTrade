"""Small, dependency-light helpers for out-of-sample research protocols."""

import math
from statistics import NormalDist

import numpy as np
import pandas as pd


__all__ = [
    "expanding_year_splits",
    "rank_ic",
    "deflated_sharpe",
    "max_drawdown",
    "assert_no_lookahead",
]


def expanding_year_splits(dates):
    """Return expanding-train/calendar-year-test boolean masks.

    The first observed year seeds the training set, so testing starts with the
    second observed year.  ``NaT`` entries are excluded from every split.
    """
    converted = pd.to_datetime(dates)
    if isinstance(converted, pd.Timestamp):
        date_index = pd.DatetimeIndex([converted])
    else:
        date_index = pd.DatetimeIndex(converted)

    valid = ~date_index.isna()
    years = np.asarray(date_index.year)
    observed_years = sorted({int(year) for year in years[valid]})

    splits = []
    for year in observed_years[1:]:
        train_mask = np.asarray(valid & (years < year), dtype=bool)
        test_mask = np.asarray(valid & (years == year), dtype=bool)
        splits.append((train_mask, test_mask, year))
    return splits


def rank_ic(factor_row, fwd_return_row):
    """Calculate cross-sectional Spearman rank information coefficient.

    Pandas Series are aligned on their common labels.  Otherwise inputs are
    compared positionally.  Non-finite pairs are omitted; fewer than two valid
    pairs or a constant ranked input produces ``nan``.
    """
    if isinstance(factor_row, pd.Series) and isinstance(fwd_return_row, pd.Series):
        paired = pd.concat(
            [factor_row.rename("factor"), fwd_return_row.rename("return")],
            axis=1,
            join="inner",
        )
        factor = paired["factor"].to_numpy(dtype=float)
        forward = paired["return"].to_numpy(dtype=float)
    else:
        factor = np.asarray(factor_row, dtype=float).reshape(-1)
        forward = np.asarray(fwd_return_row, dtype=float).reshape(-1)
        if factor.size != forward.size:
            raise ValueError("factor_row and fwd_return_row must have equal length")

    finite = np.isfinite(factor) & np.isfinite(forward)
    if finite.sum() < 2:
        return float("nan")

    factor_rank = pd.Series(factor[finite]).rank(method="average").to_numpy()
    return_rank = pd.Series(forward[finite]).rank(method="average").to_numpy()
    factor_rank -= factor_rank.mean()
    return_rank -= return_rank.mean()
    denominator = math.sqrt(
        float(np.dot(factor_rank, factor_rank) * np.dot(return_rank, return_rank))
    )
    if denominator == 0.0:
        return float("nan")
    return float(np.dot(factor_rank, return_rank) / denominator)


def deflated_sharpe(sharpe, n_obs, n_trials, sr_benchmark=0):
    """Return the probability that a Sharpe exceeds a trial-adjusted benchmark.

    This is the Gaussian-return form of the deflated Sharpe ratio.  It uses the
    estimated Sharpe standard error and the Bailey-Lopez de Prado approximation
    for the expected maximum across ``n_trials`` independent trials.  The
    result is a probability in ``[0, 1]`` rather than an adjusted Sharpe value.
    """
    if n_obs <= 1:
        raise ValueError("n_obs must be greater than 1")
    if isinstance(n_trials, (bool, np.bool_)) or int(n_trials) != n_trials:
        raise ValueError("n_trials must be a positive integer")
    n_trials = int(n_trials)
    if n_trials < 1:
        raise ValueError("n_trials must be a positive integer")

    sharpe = float(sharpe)
    sr_benchmark = float(sr_benchmark)
    if not (math.isfinite(sharpe) and math.isfinite(sr_benchmark)):
        return float("nan")

    standard_error = math.sqrt((1.0 + 0.5 * sharpe * sharpe) / (n_obs - 1.0))
    adjusted_benchmark = sr_benchmark
    if n_trials > 1:
        normal = NormalDist()
        euler_gamma = 0.5772156649015329
        upper = np.nextafter(1.0, 0.0)
        first_probability = min(1.0 - 1.0 / n_trials, upper)
        second_probability = min(1.0 - 1.0 / (n_trials * math.e), upper)
        expected_maximum = (
            (1.0 - euler_gamma) * normal.inv_cdf(first_probability)
            + euler_gamma * normal.inv_cdf(second_probability)
        )
        adjusted_benchmark += standard_error * expected_maximum

    z_score = (sharpe - adjusted_benchmark) / standard_error
    return float(NormalDist().cdf(z_score))


def max_drawdown(equity):
    """Return the worst peak-to-trough equity return as a non-positive value."""
    values = np.asarray(equity, dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    if np.any(values < 0.0):
        raise ValueError("equity values must be non-negative")

    running_peak = np.maximum.accumulate(values)
    drawdowns = np.zeros_like(values)
    positive_peak = running_peak > 0.0
    drawdowns[positive_peak] = (
        values[positive_peak] / running_peak[positive_peak] - 1.0
    )
    return float(min(0.0, drawdowns.min()))


def assert_no_lookahead(signal_index, fill_index):
    """Assert that each fill is strictly later than its paired signal."""
    signals = np.asarray(signal_index)
    fills = np.asarray(fill_index)
    signals = signals.reshape(1) if signals.ndim == 0 else signals.reshape(-1)
    fills = fills.reshape(1) if fills.ndim == 0 else fills.reshape(-1)

    if signals.size != fills.size:
        raise AssertionError("signal_index and fill_index must have equal length")
    if signals.size == 0:
        return

    try:
        valid_order = np.asarray(fills > signals, dtype=bool)
    except (TypeError, ValueError) as exc:
        raise AssertionError("signal and fill indexes are not comparable") from exc
    if not valid_order.all():
        bad = int(np.flatnonzero(~valid_order)[0])
        raise AssertionError(
            "lookahead detected at position %d: fill %r is not after signal %r"
            % (bad, fills[bad], signals[bad])
        )


if __name__ == "__main__":
    sample_dates = pd.to_datetime(["2022-01-03", "2023-01-03", "2024-01-03"])
    sample_splits = expanding_year_splits(sample_dates)
    assert [year for _, _, year in sample_splits] == [2023, 2024]
    assert np.isclose(rank_ic([1, 2, 3], [3, 2, 1]), -1.0)
    assert max_drawdown([1.0, 1.2, 0.9, 1.3]) == -0.25
    assert_no_lookahead(sample_dates[:-1], sample_dates[1:])
    assert 0.0 <= deflated_sharpe(1.0, 252, 10) <= 1.0
    print("oos_protocol self-check passed")
