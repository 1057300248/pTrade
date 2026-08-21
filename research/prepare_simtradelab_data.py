# -*- coding: utf-8 -*-
"""把仓库内 ETF CSV 转成 SimTradeLab 需要的 cn/stocks/*.parquet。"""
from __future__ import print_function

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "test", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "simtradelab_data", "cn", "stocks")

CODE_MAP = {
    "510300": "510300.SS",
    "510500": "510500.SS",
    "510880": "510880.SS",
    "159915": "159915.SZ",
    "513100": "513100.SS",
    "518880": "518880.SS",
}


def _normalize(code):
    code = str(code)
    if code.endswith(".SS") or code.endswith(".SZ"):
        return code
    if code in CODE_MAP:
        return CODE_MAP[code]
    if code.startswith("5") or code.startswith("6"):
        return code + ".SS"
    return code + ".SZ"


def _write_bars(code, frame):
    frame = frame.copy()
    frame = frame.dropna(subset=["close"])
    if frame.empty:
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, code + ".parquet")
    if os.path.exists(path):
        old = pd.read_parquet(path)
        old["date"] = pd.to_datetime(old["date"])
        frame = pd.concat([old, frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=["date"]).sort_values("date")
    frame.to_parquet(path, index=False)
    return len(frame)


def from_wide(path):
    df = pd.read_csv(path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    written = {}
    for col in df.columns[1:]:
        code = _normalize(col)
        series = df[[date_col, col]].dropna()
        series.columns = ["date", "close"]
        bars = pd.DataFrame({
            "date": series["date"],
            "open": series["close"],
            "high": series["close"],
            "low": series["close"],
            "close": series["close"],
            "volume": 1e6,
            "amount": series["close"] * 1e6,
        })
        written[code] = _write_bars(code, bars)
    return written


def from_panel(path):
    df = pd.read_csv(path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df["code"] = df["code"].map(_normalize)
    daily = df.groupby([df[date_col].dt.normalize(), "code"]).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "money": "sum",
    }).reset_index()
    daily.columns = ["date", "code", "open", "high", "low", "close", "volume", "amount"]
    written = {}
    for code, part in daily.groupby("code"):
        written[code] = _write_bars(code, part.drop(columns=["code"]))
    return written


def main():
    written = {}
    written.update(from_wide(os.path.join(DATA_DIR, "etf_data.csv")))
    written.update(from_wide(os.path.join(DATA_DIR, "etf_data2.csv")))
    written.update(from_panel(os.path.join(DATA_DIR, "market_data20241013-20251013.csv")))
    hs300 = os.path.join(OUT_DIR, "510300.SS.parquet")
    bench = os.path.join(OUT_DIR, "000300.SS.parquet")
    if os.path.exists(hs300):
        pd.read_parquet(hs300).to_parquet(bench, index=False)
        written["000300.SS"] = written.get("510300.SS", 0)
    print("parquet rows:")
    for code in sorted(written):
        print("  %s %d" % (code, written[code]))
    print("output: %s" % OUT_DIR)
    return written


if __name__ == "__main__":
    main()
