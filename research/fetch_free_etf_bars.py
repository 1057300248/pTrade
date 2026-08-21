# -*- coding: utf-8 -*-
"""Fetch ETF daily bars from free public APIs for local research.

Live 国金 PTrade strategies must NOT import this file. They use get_history.
Default source is Sina; Tencent fqkline is the fallback. Eastmoney is skipped
on purpose (IP blocks). akshare / iFinD / CMES are optional and unused here.
"""
from __future__ import print_function

import json
import os
import time
import urllib.request

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
SIM_DIR = os.path.join(os.path.dirname(__file__), "simtradelab_data", "cn", "stocks")

# Sina symbol, display name. Superset for crowding-sleeve / industry-residual designs.
UNIVERSE = [
    ("510300.SS", "sh510300", "沪深300"),
    ("510500.SS", "sh510500", "中证500"),
    ("512100.SS", "sh512100", "中证1000"),
    ("510050.SS", "sh510050", "上证50"),
    ("159915.SZ", "sz159915", "创业板"),
    ("588000.SS", "sh588000", "科创50"),
    ("512480.SS", "sh512480", "半导体"),
    ("515880.SS", "sh515880", "通信"),
    ("515980.SS", "sh515980", "人工智能"),
    ("159857.SZ", "sz159857", "光伏"),
    ("516650.SS", "sh516650", "有色"),
    ("512660.SS", "sh512660", "军工"),
    ("512010.SS", "sh512010", "医药"),
    ("512800.SS", "sh512800", "银行"),
    ("159992.SZ", "sz159992", "创新药"),
    ("516160.SS", "sh516160", "新能源"),
    ("518880.SS", "sh518880", "黄金"),
    ("513100.SS", "sh513100", "纳指"),
    ("513500.SS", "sh513500", "标普500"),
    ("513180.SS", "sh513180", "恒生科技"),
    ("513520.SS", "sh513520", "日经"),
    ("513030.SS", "sh513030", "德国DAX"),
    ("510880.SS", "sh510880", "上证红利"),
    ("512890.SS", "sh512890", "红利低波"),
    ("511010.SS", "sh511010", "国债"),
    ("511090.SS", "sh511090", "30年国债"),
    ("511260.SS", "sh511260", "十年国债"),
    ("000300.SS", "sh000300", "沪深300指数"),
]

UA = {"User-Agent": "Mozilla/5.0"}
PAUSE_SEC = 0.25


def _get(url, encoding="utf-8"):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode(encoding, errors="replace")


def fetch_sina(sina_symbol, datalen=2500):
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d"
        % (sina_symbol, datalen)
    )
    raw = _get(url)
    if not raw or raw == "null":
        return pd.DataFrame()
    rows = json.loads(raw)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["day"])
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["amount"] = frame["close"] * frame["volume"]
    return frame[["date", "open", "high", "low", "close", "volume", "amount"]].dropna()


def fetch_tencent(sina_symbol, count=800):
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,, %d,qfq"
        % (sina_symbol, count)
    ).replace(" ", "")
    raw = _get(url)
    payload = json.loads(raw)
    block = (payload.get("data") or {}).get(sina_symbol) or {}
    series = block.get("qfqday") or block.get("day") or []
    if not series:
        return pd.DataFrame()
    frame = pd.DataFrame(series, columns=["date", "open", "close", "high", "low", "volume"])
    frame["date"] = pd.to_datetime(frame["date"])
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    # Tencent ETF volume is usually in lots (100 shares).
    if frame["volume"].median() < 1e6:
        frame["volume"] = frame["volume"] * 100.0
    frame["amount"] = frame["close"] * frame["volume"]
    return frame[["date", "open", "high", "low", "close", "volume", "amount"]].dropna()


def fetch_one(code, sina_symbol):
    try:
        frame = fetch_sina(sina_symbol)
        source = "sina"
    except Exception as exc:
        print("  sina fail %s %s" % (code, exc))
        frame = pd.DataFrame()
        source = None
    if frame.empty:
        try:
            frame = fetch_tencent(sina_symbol)
            source = "tencent"
        except Exception as exc:
            print("  tencent fail %s %s" % (code, exc))
            return pd.DataFrame(), None
    if frame.empty:
        return frame, None
    frame = frame.drop_duplicates(subset=["date"]).sort_values("date")
    return frame, source


def _write(frame, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame.to_parquet(path, index=False)


def main():
    summary = []
    for code, sina_symbol, name in UNIVERSE:
        frame, source = fetch_one(code, sina_symbol)
        time.sleep(PAUSE_SEC)
        if frame.empty:
            print("FAIL %s %s" % (code, name))
            summary.append((code, name, 0, None, None, None))
            continue
        _write(frame, os.path.join(CACHE_DIR, code + ".parquet"))
        _write(frame, os.path.join(SIM_DIR, code + ".parquet"))
        first = frame["date"].iloc[0].date()
        last = frame["date"].iloc[-1].date()
        print("OK %s %s n=%d %s..%s src=%s" % (code, name, len(frame), first, last, source))
        summary.append((code, name, len(frame), str(first), str(last), source))
    print("cache=%s" % CACHE_DIR)
    print("simtradelab=%s" % SIM_DIR)
    return summary


if __name__ == "__main__":
    main()
