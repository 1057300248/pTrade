# -*- coding: utf-8 -*-
"""Download CSI 300 daily bars for the HOT-LEADER-V1 research proxy.

Uses the existing Sina adapter (research-only). Does not scrape Tonghuashun
hot boards or hexin-v. Membership is the current CSI 300 list (survivorship
must be disclosed in the report).
"""
from __future__ import print_function

import json
import os
import sys
import time
import urllib.request

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.source_adapters import UA, fetch_sina, six_digit

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "hot_leader_daily")
HS300_NODE = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page=%d&num=100&sort=symbol&asc=1&node=hs300"
)
PAUSE_SEC = 0.35
MIN_ROWS = 400


def _http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if not raw:
        return []
    return json.loads(raw)


def fetch_hs300_symbols():
    rows = []
    for page in (1, 2, 3, 4):
        chunk = _http_json(HS300_NODE % page)
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < 100:
            break
        time.sleep(0.2)
    codes = []
    seen = set()
    for item in rows:
        symbol = str(item.get("symbol") or "")
        digits = six_digit(symbol or item.get("code") or "")
        if symbol.startswith("sh"):
            code = digits + ".SS"
        else:
            code = digits + ".SZ"
        if code in seen:
            continue
        seen.add(code)
        name = str(item.get("name") or "")
        if "ST" in name.upper():
            continue
        codes.append(code)
    return codes


def canonical_parquet_name(code):
    return str(code)


def fetch_index_300():
    """Sina index bars for 沪深300; force the Shanghai symbol."""
    return fetch_sina("000300.SS", sina_symbol="sh000300", datalen=2500)


def download_code(code, cache_dir, sina_symbol=None):
    path = os.path.join(cache_dir, canonical_parquet_name(code) + ".parquet")
    if os.path.isfile(path):
        try:
            existing = pd.read_parquet(path)
            if len(existing) >= MIN_ROWS:
                return "cached", len(existing)
        except Exception:
            pass
    frame = fetch_sina(code, sina_symbol=sina_symbol, datalen=2500)
    if frame is None or frame.empty:
        return "empty", 0
    frame.to_parquet(path, index=False)
    return "ok", len(frame)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print("fetching CSI 300 membership")
    codes = fetch_hs300_symbols()
    print("members", len(codes))
    status, rows = download_code("000300.SS", CACHE_DIR, sina_symbol="sh000300")
    print("index 000300", status, rows)
    ok = 0
    empty = 0
    cached = 0
    for i, code in enumerate(codes):
        try:
            status, rows = download_code(code, CACHE_DIR)
        except Exception as exc:
            print("fail", code, type(exc).__name__, str(exc)[:120])
            time.sleep(1.0)
            try:
                status, rows = download_code(code, CACHE_DIR)
            except Exception as exc2:
                print("fail2", code, type(exc2).__name__, str(exc2)[:120])
                empty += 1
                continue
        if status == "cached":
            cached += 1
        elif status == "ok":
            ok += 1
        else:
            empty += 1
        if (i + 1) % 20 == 0:
            print("progress", i + 1, "/", len(codes), "ok", ok, "cached", cached, "empty", empty)
        time.sleep(PAUSE_SEC)
    print("done ok", ok, "cached", cached, "empty", empty, "members", len(codes))
    with open(os.path.join(CACHE_DIR, "universe.txt"), "w") as handle:
        handle.write("\n".join(codes) + "\n")


if __name__ == "__main__":
    main()
