import numpy as np
import pandas as pd

from research.openalphas_rp_mom import (
    build_rebalance_signal,
    filter_by_volatility,
    inverse_volatility_weights,
    momentum_score,
)


def test_perfect_exponential_uptrend_has_high_score_and_near_one_r_squared():
    closes = 100.0 * np.exp(0.001 * np.arange(20))

    score, r_squared = momentum_score(closes)

    assert score > 0.25
    assert r_squared > 0.999999


def test_flat_series_has_zero_score():
    score, r_squared = momentum_score(np.full(20, 100.0))

    assert abs(score) < 1e-12
    assert r_squared == 0.0


def test_volatility_filter_drops_too_low_and_too_high_names():
    vol = pd.Series({"low": 0.05, "inside": 0.16, "high": 0.40})

    filtered = filter_by_volatility(vol, (0.08, 0.28))

    assert filtered.index.tolist() == ["inside"]


def test_inverse_volatility_weights_sum_to_one():
    weights = inverse_volatility_weights(
        pd.Series({"first": 0.10, "second": 0.20, "third": 0.25})
    )

    assert np.isclose(weights.sum(), 1.0)
    assert weights["first"] > weights["second"] > weights["third"]


def test_signal_helpers_do_not_look_past_as_of_date():
    rng = np.random.default_rng(20260822)
    dates = pd.bdate_range("2015-01-01", periods=620)
    tickers = ["A", "B", "C", "D", "E", "F"]
    log_returns = rng.normal(0.0003, 0.009, size=(len(dates), len(tickers)))
    prices = pd.DataFrame(
        100.0 * np.exp(np.cumsum(log_returns, axis=0)),
        index=dates,
        columns=tickers,
    )
    as_of = dates[589]
    params = {
        "corr_window": 500,
        "vol_window": 250,
        "momentum_window": 20,
        "top_n_corr": 5,
        "top_n_momentum": 2,
    }

    past_only = build_rebalance_signal(prices.loc[:as_of], as_of, params)
    altered = prices.copy()
    altered.loc[altered.index > as_of] *= np.linspace(
        0.2, 5.0, (altered.index > as_of).sum()
    )[:, None]
    with_changed_future = build_rebalance_signal(altered, as_of, params)

    assert past_only is not None
    assert with_changed_future is not None
    assert past_only["selected"] == with_changed_future["selected"]
    pd.testing.assert_series_equal(
        past_only["volatility"], with_changed_future["volatility"]
    )
    pd.testing.assert_series_equal(
        past_only["mean_abs_correlation"],
        with_changed_future["mean_abs_correlation"],
    )
    pd.testing.assert_series_equal(
        past_only["momentum_scores"], with_changed_future["momentum_scores"]
    )
