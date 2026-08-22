import math

import numpy as np
import pandas as pd

from research.oos_protocol import (
    overfit_warning,
    split_is_oos,
    time_series_ic,
)


def _expected_sharpe(nav):
    returns = np.asarray(nav[1:], dtype=float) / np.asarray(nav[:-1], dtype=float) - 1.0
    return float(returns.mean() / returns.std(ddof=1) * math.sqrt(252.0))


def test_time_series_ic_is_spearman_and_drops_nan_pairs():
    factor = pd.Series(
        [1.0, 2.0, np.nan, 4.0],
        index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]),
    )
    forward = pd.Series(
        [16.0, 1.0, 4.0, 9.0, 100.0],
        index=pd.to_datetime(
            ["2020-01-04", "2020-01-01", "2020-01-02", "2020-01-03", "2020-01-05"]
        ),
    )

    assert np.isclose(time_series_ic(factor, forward), 1.0)
    assert np.isclose(time_series_ic([1, 2, 3, 4], [1, 4, 9, 16]), 1.0)


def test_split_is_oos_reports_segment_performance():
    dates = pd.to_datetime(
        [
            "2021-01-01",
            "2021-07-02",
            "2021-12-31",
            "2022-01-03",
            "2022-07-01",
            "2022-12-30",
        ]
    )
    nav = np.array([100.0, 110.0, 105.0, 105.0, 120.0, 108.0])

    result = split_is_oos(dates, nav)

    assert set(result) == {"is", "oos"}
    assert set(result["is"]) == {"cagr", "mdd", "sharpe"}
    assert set(result["oos"]) == {"cagr", "mdd", "sharpe"}
    assert np.isclose(result["is"]["mdd"], 105.0 / 110.0 - 1.0)
    assert np.isclose(result["oos"]["mdd"], 108.0 / 120.0 - 1.0)
    assert np.isclose(result["is"]["sharpe"], _expected_sharpe(nav[:3]))
    assert np.isclose(result["oos"]["sharpe"], _expected_sharpe(nav[3:]))

    is_years = (dates[2] - dates[0]).days / 365.25
    oos_years = (dates[-1] - dates[3]).days / 365.25
    assert np.isclose(result["is"]["cagr"], (105.0 / 100.0) ** (1.0 / is_years) - 1.0)
    assert np.isclose(result["oos"]["cagr"], (108.0 / 105.0) ** (1.0 / oos_years) - 1.0)


def test_overfit_warning_uses_strict_ratio_threshold():
    assert overfit_warning(1.0, 0.49) is True
    assert overfit_warning(1.0, 0.50) is False
    assert overfit_warning(2.0, 1.49, ratio=0.75) is True
    assert overfit_warning(2.0, 1.50, ratio=0.75) is False
