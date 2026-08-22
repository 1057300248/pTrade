# -*- coding: utf-8 -*-
"""Regenerate SimTradeLab ETF bars from the split-adjusted research cache."""
from __future__ import print_function

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.etf_panel import load_panel


CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
OUT_DIR = os.path.join(os.path.dirname(__file__), "simtradelab_data", "cn", "stocks")
SCHEMA = ("date", "open", "high", "low", "close", "volume", "amount")


def _adjusted_frame(source_path, bars):
    """Restore adjusted open from the shared loader's close adjustment factor."""
    raw = pd.read_parquet(source_path, columns=["date", "open", "close"])
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = (
        raw.dropna(subset=["date", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    raw["open"] = pd.to_numeric(raw["open"], errors="coerce")
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")

    adjusted_dates = pd.DatetimeIndex(bars["dates"])
    raw_dates = pd.DatetimeIndex(raw["date"])
    if not raw_dates.equals(adjusted_dates):
        raise ValueError("source and adjusted dates differ for %s" % source_path)

    raw_close = raw["close"].to_numpy(dtype=float)
    factor = np.divide(
        bars["close"],
        raw_close,
        out=np.full(raw_close.shape, np.nan, dtype=float),
        where=np.isfinite(raw_close) & (raw_close != 0.0),
    )
    adjusted_open = raw["open"].to_numpy(dtype=float) * factor
    return pd.DataFrame(
        {
            "date": adjusted_dates,
            "open": adjusted_open,
            "high": bars["high"],
            "low": bars["low"],
            "close": bars["close"],
            "volume": bars["volume"],
            # CNY turnover is invariant under a split and is not rescaled.
            "amount": bars["amount"],
        },
        columns=SCHEMA,
    )


def regenerate(cache_dir=CACHE_DIR, out_dir=OUT_DIR):
    """Overwrite generated SimTradeLab bars with split-adjusted cache data."""
    panel = load_panel(cache_dir)
    os.makedirs(out_dir, exist_ok=True)
    expected_names = {code + ".parquet" for code in panel}
    for name in os.listdir(out_dir):
        if name.endswith(".parquet") and name not in expected_names:
            os.remove(os.path.join(out_dir, name))

    written = {}
    for code, bars in panel.items():
        source_path = os.path.join(cache_dir, code + ".parquet")
        frame = _adjusted_frame(source_path, bars)
        frame.to_parquet(os.path.join(out_dir, code + ".parquet"), index=False)
        written[code] = len(frame)
    return written


def main():
    written = regenerate()
    print("parquet rows:")
    for code in sorted(written):
        print("  %s %d" % (code, written[code]))
    print("output: %s" % OUT_DIR)
    return written


if __name__ == "__main__":
    main()
