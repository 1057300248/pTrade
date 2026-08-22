# -*- coding: utf-8 -*-
"""Fetch ETF daily bars from free public / local research APIs.

Live 国金 PTrade strategies must NOT import this file. They use get_history.
Default chain: Sina, Tencent, baostock, akshare, Tonghuashun free K, free-stockdb.
"""
from __future__ import print_function

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.source_adapters import (
    SCHEMA,
    TARGET_LAST_DATE,
    fetch_one,
    probe_sources,
    resolve_sources,
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
SIM_DIR = os.path.join(os.path.dirname(__file__), "simtradelab_data", "cn", "stocks")

# Sina symbol and display name. This is GROWTH + DIVERSIFIER from the strategy,
# plus the benchmark index and cash ETF used by the backtest.
UNIVERSE = [
    ("510300.SS", "sh510300", "沪深300"),
    ("510500.SS", "sh510500", "中证500"),
    ("512100.SS", "sh512100", "中证1000"),
    ("159915.SZ", "sz159915", "创业板"),
    ("588000.SS", "sh588000", "科创50"),
    ("512480.SS", "sh512480", "半导体"),
    ("515880.SS", "sh515880", "通信"),
    ("515980.SS", "sh515980", "人工智能"),
    ("512660.SS", "sh512660", "军工"),
    ("512010.SS", "sh512010", "医药"),
    ("512800.SS", "sh512800", "银行"),
    ("516160.SS", "sh516160", "新能源"),
    ("518880.SS", "sh518880", "黄金"),
    ("513100.SS", "sh513100", "纳指"),
    ("513500.SS", "sh513500", "标普500"),
    ("513520.SS", "sh513520", "日经"),
    ("513030.SS", "sh513030", "德国DAX"),
    ("510880.SS", "sh510880", "上证红利"),
    ("512890.SS", "sh512890", "红利低波"),
    ("511010.SS", "sh511010", "国债"),
    ("511090.SS", "sh511090", "30年国债"),
    ("511260.SS", "sh511260", "十年国债"),
    ("512880.SS", "sh512880", "证券"),
    ("512690.SS", "sh512690", "酒"),
    ("512400.SS", "sh512400", "有色"),
    ("515030.SS", "sh515030", "新能源车"),
    ("511880.SS", "sh511880", "银华日利"),
    ("515220.SS", "sh515220", "煤炭"),
    ("000300.SS", "sh000300", "沪深300指数"),
]


def _write(frame, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame[SCHEMA].to_parquet(path, index=False)


def _is_current(path):
    if not os.path.exists(path):
        return False
    try:
        dates = pd.read_parquet(path, columns=SCHEMA)["date"]
        dates = pd.to_datetime(dates, errors="coerce").dropna()
    except Exception:
        return False
    return bool(
        not dates.empty
        and dates.max().date() == TARGET_LAST_DATE.date()
    )


def _reuse_current_outputs(code, cache_path, sim_path):
    current = [path for path in (cache_path, sim_path) if _is_current(path)]
    if len(current) == 2:
        print("SKIP %s already current through %s" % (code, TARGET_LAST_DATE.date()))
        return True
    if not current:
        return False

    # One copy is current and the other is absent/stale: mirror locally instead
    # of spending another public API request.
    try:
        frame = pd.read_parquet(current[0], columns=SCHEMA)
        frame["date"] = pd.to_datetime(frame["date"])
    except Exception:
        return False
    other = sim_path if current[0] == cache_path else cache_path
    _write(frame, other)
    print("SKIP %s copied current data to %s" % (code, other))
    return True


def _selected_universe(codes):
    if not codes:
        return list(UNIVERSE)
    if isinstance(codes, str):
        codes = [codes]
    wanted = set()
    for item in codes:
        for part in str(item).replace(";", ",").split(","):
            part = part.strip()
            if part:
                wanted.add(part.upper())
    selected = [row for row in UNIVERSE if row[0] in wanted or row[1].upper() in wanted]
    if not selected:
        raise ValueError("no UNIVERSE match for %s" % codes)
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch research ETF daily bars")
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma list: sina,tencent,baostock,akshare,ths,free-stockdb "
        "(aliases: aakshare, tonghuashun). Env: PTRADE_RESEARCH_SOURCES",
    )
    parser.add_argument("--force", action="store_true", help="Refetch even if cache is current")
    parser.add_argument("--probe", action="store_true", help="Ping each source on one code and exit")
    parser.add_argument("--codes", default=None, help="Subset, e.g. 510300.SS,159915.SZ")
    args = parser.parse_args(argv)

    sources = resolve_sources(args.sources)
    if args.probe:
        code, sina_symbol, name = _selected_universe(args.codes)[0]
        print("probe %s %s sources=%s" % (code, name, ",".join(sources)))
        rows = probe_sources(code, sina_symbol, sources=sources)
        for row in rows:
            print(
                "PROBE %s ok=%s rows=%s %s..%s %sms error=%s"
                % (
                    row["source"],
                    row["ok"],
                    row["rows"],
                    row["first"],
                    row["last"],
                    row["ms"],
                    row["error"],
                )
            )
        return rows

    summary = []
    for code, sina_symbol, name in _selected_universe(args.codes):
        cache_path = os.path.join(CACHE_DIR, code + ".parquet")
        sim_path = os.path.join(SIM_DIR, code + ".parquet")
        if not args.force and _reuse_current_outputs(code, cache_path, sim_path):
            summary.append((code, name, 0, None, str(TARGET_LAST_DATE.date()), "existing"))
            continue
        frame, source = fetch_one(code, sina_symbol, sources=sources)
        if frame.empty:
            print("FAIL %s %s" % (code, name))
            summary.append((code, name, 0, None, None, None))
            continue
        _write(frame, cache_path)
        _write(frame, sim_path)
        first = frame["date"].iloc[0].date()
        last = frame["date"].iloc[-1].date()
        print("OK %s %s n=%d %s..%s src=%s" % (code, name, len(frame), first, last, source))
        summary.append((code, name, len(frame), str(first), str(last), source))
    print("cache=%s" % CACHE_DIR)
    print("simtradelab=%s" % SIM_DIR)
    print("sources=%s" % ",".join(sources))
    return summary


if __name__ == "__main__":
    main()
