"""Shared split-adjusted loader for the local ETF daily-bar cache.

Sina's free ETF bars are not adjusted for share splits and consolidations.
For every raw close-to-close move above 22%, this loader treats the move as a
corporate action and back-adjusts all earlier OHLC values by the close ratio.
Earlier volume is divided by the same positive ratio.  ``amount`` is CNY
turnover, so finite source values are deliberately left unchanged; missing
values are filled with adjusted close times adjusted volume, whose product is
also invariant to this adjustment.
"""

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "cache" / "etf_daily"
REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")
OHLC_COLUMNS = ("open", "high", "low", "close")
JUMP_THRESHOLD = 0.22


def detect_jumps(close):
    """Return positions whose raw absolute close-to-close return exceeds 22%."""
    values = np.asarray(close, dtype=float).reshape(-1)
    if values.size < 2:
        return []

    previous = values[:-1]
    current = values[1:]
    valid = (
        np.isfinite(previous)
        & np.isfinite(current)
        & (previous > 0.0)
        & (current > 0.0)
    )
    returns = np.full(previous.shape, np.nan, dtype=float)
    returns[valid] = current[valid] / previous[valid] - 1.0
    return (np.flatnonzero(np.abs(returns) > JUMP_THRESHOLD) + 1).tolist()


def _load_one(path):
    frame = pd.read_parquet(path, columns=list(REQUIRED_COLUMNS))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = (
        frame.dropna(subset=["date", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    for column in REQUIRED_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    raw_close = frame["close"].to_numpy(dtype=float, copy=True)
    jump_positions = detect_jumps(raw_close)
    adjusted = {
        column: frame[column].to_numpy(dtype=float, copy=True)
        for column in OHLC_COLUMNS
    }
    adjusted_volume = frame["volume"].to_numpy(dtype=float, copy=True)

    for position in jump_positions:
        ratio = raw_close[position] / raw_close[position - 1]
        if not (np.isfinite(ratio) and ratio > 0.0):
            continue
        for values in adjusted.values():
            values[:position] *= ratio
        adjusted_volume[:position] /= ratio

    amount = frame["amount"].to_numpy(dtype=float, copy=True)
    fallback_amount = adjusted["close"] * adjusted_volume
    amount = np.where(np.isfinite(amount), amount, fallback_amount)
    return {
        "dates": frame["date"].to_numpy(dtype="datetime64[ns]"),
        "open": adjusted["open"],
        "high": adjusted["high"],
        "low": adjusted["low"],
        "close": adjusted["close"],
        "volume": adjusted_volume,
        "amount": amount,
    }


def load_panel(cache_dir=DEFAULT_CACHE_DIR, codes=None):
    """Load split-adjusted ETF bars keyed by security code.

    ``codes`` can restrict loading to a required subset.  Missing requested
    files raise ``FileNotFoundError``; an empty unrestricted cache does too.
    """
    cache_dir = Path(cache_dir)
    if codes is None:
        paths = sorted(cache_dir.glob("*.parquet"))
        if not paths:
            raise FileNotFoundError("no parquet files under %s" % cache_dir)
    else:
        unique_codes = tuple(dict.fromkeys(str(code) for code in codes))
        paths = [cache_dir / (code + ".parquet") for code in unique_codes]
        missing = [path for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError("missing cached bars: %s" % missing[0])

    return {path.stem: _load_one(path) for path in paths}
