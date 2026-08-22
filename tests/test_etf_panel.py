from pathlib import Path

import numpy as np
import pandas as pd

from research.etf_panel import detect_jumps, load_panel


CACHE_DIR = Path(__file__).resolve().parents[1] / "research" / "cache" / "etf_daily"


def test_detect_jumps_and_stack_multiple_adjustments(tmp_path):
    dates = pd.to_datetime(
        ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    )
    close = np.array([100.0, 20.0, 22.0, 44.0])
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": [100.0, 500.0, 400.0, 200.0],
            "amount": [10000.0, 10000.0, 8800.0, 8800.0],
        }
    )
    frame.to_parquet(tmp_path / "TEST.SS.parquet", index=False)

    assert detect_jumps(close) == [1, 3]
    bars = load_panel(tmp_path)["TEST.SS"]

    assert np.allclose(bars["close"], [40.0, 40.0, 44.0, 44.0])
    assert np.allclose(bars["volume"], [250.0, 250.0, 200.0, 200.0])
    assert np.array_equal(bars["amount"], frame["amount"].to_numpy(dtype=float))
    adjusted_returns = bars["close"][1:] / bars["close"][:-1] - 1.0
    assert np.all(np.abs(adjusted_returns) < 0.22)


def test_cached_513100_split_is_back_adjusted():
    path = CACHE_DIR / "513100.SS.parquet"
    assert path.is_file(), "required cached 513100 bars are missing"

    raw = pd.read_parquet(path, columns=["date", "close"])
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values("date").drop_duplicates("date", keep="last")
    before = raw.loc[raw["date"] == pd.Timestamp("2022-01-13"), "close"].iloc[0]
    after = raw.loc[raw["date"] == pd.Timestamp("2022-01-14"), "close"].iloc[0]
    raw_return = float(after / before - 1.0)
    assert raw_return < -0.75

    bars = load_panel(CACHE_DIR, codes=["513100.SS"])["513100.SS"]
    dates = pd.DatetimeIndex(bars["dates"])
    before_position = dates.get_loc(pd.Timestamp("2022-01-13"))
    after_position = dates.get_loc(pd.Timestamp("2022-01-14"))
    adjusted_return = float(
        bars["close"][after_position] / bars["close"][before_position] - 1.0
    )

    assert after_position in detect_jumps(raw["close"].to_numpy(dtype=float))
    assert abs(adjusted_return) < 0.22
