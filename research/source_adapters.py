# -*- coding: utf-8 -*-
"""Research-only ETF daily-bar adapters.

Live 国金 PTrade files must not import this module. They use get_history.
These adapters normalize public/local feeds onto
date, open, high, low, close, volume, amount.
"""
from __future__ import print_function

import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd


SCHEMA = ["date", "open", "high", "low", "close", "volume", "amount"]
PAUSE_SEC = 0.25
DEFAULT_START = "2016-01-01"
TARGET_LAST_DATE = pd.Timestamp("2026-08-21")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

SOURCE_ALIASES = {
    "aakshare": "akshare",
    "tonghuashun": "ths",
    "10jqka": "ths",
    "同花顺": "ths",
    "freestockdb": "free-stockdb",
    "free_stockdb": "free-stockdb",
    "stockdb": "free-stockdb",
}

# sina/tencent first so existing caches stay stable; the four requested
# sources are extra fallbacks, not a live-file dependency.
DEFAULT_SOURCES = (
    "sina",
    "tencent",
    "baostock",
    "akshare",
    "ths",
    "free-stockdb",
)

COLUMN_ALIASES = {
    "date": "date",
    "day": "date",
    "日期": "date",
    "时间": "date",
    "open": "open",
    "开盘": "open",
    "开盘价": "open",
    "high": "high",
    "最高": "high",
    "最高价": "high",
    "low": "low",
    "最低": "low",
    "最低价": "low",
    "close": "close",
    "收盘": "close",
    "收盘价": "close",
    "volume": "volume",
    "vol": "volume",
    "成交量": "volume",
    "amount": "amount",
    "成交额": "amount",
    "成交金额": "amount",
}


def six_digit(code):
    text = str(code).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        raise ValueError("cannot parse security code: %s" % code)
    return digits[-6:]


def market_of(code):
    text = str(code).strip()
    lower = text.lower()
    upper = text.upper()
    if upper.endswith((".SZ", ".XSHE")) or lower.startswith("sz"):
        return "sz"
    if upper.endswith((".SS", ".SH", ".XSHG")) or lower.startswith("sh"):
        return "sh"
    digits = six_digit(code)
    if digits.startswith(("15", "16", "12", "00", "30")):
        return "sz"
    return "sh"


def sina_symbol_of(code, sina_symbol=None):
    if sina_symbol:
        return sina_symbol
    return market_of(code) + six_digit(code)


def baostock_code_of(code):
    return "%s.%s" % (market_of(code), six_digit(code))


def ths_symbol_of(code):
    return "hs_%s" % six_digit(code)


def canonical_source(name):
    key = str(name or "").strip().lower()
    return SOURCE_ALIASES.get(key, key)


def resolve_sources(sources=None):
    if sources is None:
        raw = os.environ.get("PTRADE_RESEARCH_SOURCES", "")
        sources = raw if raw.strip() else DEFAULT_SOURCES
    if isinstance(sources, str):
        sources = [part.strip() for part in sources.replace(";", ",").split(",")]
    resolved = []
    seen = set()
    for item in sources:
        if not item:
            continue
        name = canonical_source(item)
        if name in seen:
            continue
        if name not in SOURCE_FETCHERS:
            raise ValueError("unknown research source: %s" % item)
        seen.add(name)
        resolved.append(name)
    if not resolved:
        raise ValueError("no research sources selected")
    return tuple(resolved)


def normalize_bars(frame, volume_in_lots=False):
    if frame is None:
        return pd.DataFrame(columns=SCHEMA)
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    if frame.empty:
        return pd.DataFrame(columns=SCHEMA)

    renamed = {}
    for column in frame.columns:
        key = str(column).strip()
        mapped = COLUMN_ALIASES.get(key) or COLUMN_ALIASES.get(key.lower())
        if mapped:
            renamed[column] = mapped
    frame = frame.rename(columns=renamed).copy()
    missing = [column for column in ("date", "open", "high", "low", "close") if column not in frame.columns]
    if missing:
        return pd.DataFrame(columns=SCHEMA)

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = pd.NA
    if volume_in_lots:
        frame["volume"] = frame["volume"] * 100.0
    amount_missing = ~pd.notna(frame["amount"])
    frame.loc[amount_missing, "amount"] = frame.loc[amount_missing, "close"] * frame.loc[amount_missing, "volume"]
    frame = frame.dropna(subset=["date", "close"])
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return frame[SCHEMA].reset_index(drop=True)


def _http_get(url, headers=None, encoding="utf-8", opener=None):
    request_headers = {"User-Agent": UA}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    handle = opener.open if opener is not None else urllib.request.urlopen
    with handle(req, timeout=30) as resp:
        return resp.read().decode(encoding, errors="replace")


def fetch_sina(code, sina_symbol=None, datalen=2500):
    symbol = sina_symbol_of(code, sina_symbol)
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d"
        % (symbol, datalen)
    )
    raw = _http_get(url)
    if not raw or raw == "null":
        return pd.DataFrame(columns=SCHEMA)
    rows = json.loads(raw)
    return normalize_bars(pd.DataFrame(rows))


def fetch_tencent(code, sina_symbol=None, count=800):
    symbol = sina_symbol_of(code, sina_symbol)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq"
        % (symbol, count)
    )
    payload = json.loads(_http_get(url))
    block = (payload.get("data") or {}).get(symbol) or {}
    series = block.get("qfqday") or block.get("day") or []
    if not series:
        return pd.DataFrame(columns=SCHEMA)
    frame = pd.DataFrame(series, columns=["date", "open", "close", "high", "low", "volume"])
    return normalize_bars(frame, volume_in_lots=True)


def parse_ths_jsonp(raw):
    """Parse 同花顺 d.10jqka JSONP into the research bar schema."""
    if not raw or "window.location" in raw or "<html" in raw.lower():
        return pd.DataFrame(columns=SCHEMA)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return pd.DataFrame(columns=SCHEMA)
    payload = json.loads(match.group(0))
    data = payload.get("data")
    if data is None:
        return pd.DataFrame(columns=SCHEMA)
    if isinstance(data, list):
        frame = pd.DataFrame(data)
        if frame.shape[1] >= 5 and "date" not in frame.columns:
            frame = frame.iloc[:, :7]
            frame.columns = SCHEMA[: frame.shape[1]]
        return normalize_bars(frame, volume_in_lots=True)
    rows = []
    for item in str(data).split(";"):
        parts = [part.strip() for part in item.split(",") if part != ""]
        if len(parts) < 5:
            continue
        row = {
            "date": parts[0],
            "open": parts[1],
            "high": parts[2],
            "low": parts[3],
            "close": parts[4],
            "volume": parts[5] if len(parts) > 5 else None,
            "amount": parts[6] if len(parts) > 6 else None,
        }
        rows.append(row)
    return normalize_bars(pd.DataFrame(rows), volume_in_lots=True)


def _ths_opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def _ths_headers(code, hexin=None):
    headers = {
        "User-Agent": UA,
        "Referer": "https://stockpage.10jqka.com.cn/%s/" % six_digit(code),
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if hexin:
        headers["hexin-v"] = hexin
        headers["Cookie"] = "v=%s" % hexin
    return headers


def _ths_get(url, code, opener):
    hexin = os.environ.get("THS_HEXIN_V") or os.environ.get("HEXIN_V")
    return _http_get(url, headers=_ths_headers(code, hexin), opener=opener)


def fetch_ths(code, sina_symbol=None, start_year=2016, end_year=None):
    """Tonghuashun free daily K from d.10jqka.com.cn (not iFinD)."""
    code6 = six_digit(code)
    symbol = ths_symbol_of(code)
    opener = _ths_opener()
    try:
        opener.open(
            urllib.request.Request(
                "https://stockpage.10jqka.com.cn/%s/" % code6,
                headers=_ths_headers(code),
            ),
            timeout=15,
        )
    except Exception:
        pass

    frames = []
    all_url = "https://d.10jqka.com.cn/v6/line/%s/01/all.js" % symbol
    try:
        frames.append(parse_ths_jsonp(_ths_get(all_url, code, opener)))
    except Exception:
        frames.append(pd.DataFrame(columns=SCHEMA))
    if not frames[-1].empty and len(frames[-1]) >= 400:
        return frames[-1]

    last_year = int(end_year or TARGET_LAST_DATE.year)
    for year in range(int(start_year), last_year + 1):
        for version in ("v6", "v2"):
            url = "https://d.10jqka.com.cn/%s/line/%s/01/%d.js" % (version, symbol, year)
            try:
                part = parse_ths_jsonp(_ths_get(url, code, opener))
            except Exception:
                part = pd.DataFrame(columns=SCHEMA)
            if not part.empty:
                frames.append(part)
                break
        time.sleep(0.15)
    if not frames:
        return pd.DataFrame(columns=SCHEMA)
    return normalize_bars(pd.concat(frames, ignore_index=True), volume_in_lots=False)


_BAOSTOCK_LOGGED_IN = False


def _import_baostock():
    try:
        import baostock as bs
    except ImportError as exc:
        raise ImportError("baostock is not installed; pip install baostock") from exc
    return bs


def _baostock_login():
    global _BAOSTOCK_LOGGED_IN
    if _BAOSTOCK_LOGGED_IN:
        return
    bs = _import_baostock()
    login = bs.login()
    if getattr(login, "error_code", "0") not in (None, "", "0"):
        raise RuntimeError("baostock login failed: %s" % getattr(login, "error_msg", login))
    _BAOSTOCK_LOGGED_IN = True


def fetch_baostock(code, sina_symbol=None, start_date=DEFAULT_START, end_date=None):
    """BaoStock query_history_k_data_plus, unadjusted so etf_panel can split-fix."""
    bs = _import_baostock()
    _baostock_login()
    end_date = end_date or TARGET_LAST_DATE.strftime("%Y-%m-%d")
    result = bs.query_history_k_data_plus(
        baostock_code_of(code),
        "date,open,high,low,close,volume,amount",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3",
    )
    if getattr(result, "error_code", "0") not in (None, "", "0"):
        raise RuntimeError("baostock query failed: %s" % getattr(result, "error_msg", result))
    rows = []
    while getattr(result, "error_code", "0") in (None, "", "0") and result.next():
        rows.append(result.get_row_data())
    if not rows:
        return pd.DataFrame(columns=SCHEMA)
    frame = pd.DataFrame(rows, columns=result.fields)
    return normalize_bars(frame)


def _import_akshare():
    try:
        import akshare as ak
        return ak
    except ImportError:
        try:
            import aakshare as ak
            return ak
        except ImportError as exc:
            raise ImportError("akshare is not installed; pip install akshare") from exc


def _call_first(functions):
    last_error = None
    for func in functions:
        try:
            frame = func()
        except Exception as exc:
            last_error = exc
            continue
        if frame is not None and isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame
    if last_error is not None:
        raise last_error
    return pd.DataFrame(columns=SCHEMA)


def fetch_akshare(code, sina_symbol=None, start_date="20160101", end_date=None):
    """AKShare (user spelling: aakshare). ETF hist first, then index/stock."""
    ak = _import_akshare()
    code6 = six_digit(code)
    symbol = sina_symbol_of(code, sina_symbol)
    end_date = end_date or TARGET_LAST_DATE.strftime("%Y%m%d")

    def _em_etf():
        return ak.fund_etf_hist_em(
            symbol=code6,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )

    def _sina_etf():
        return ak.fund_etf_hist_sina(symbol=symbol)

    def _index_daily():
        return ak.stock_zh_index_daily(symbol=symbol)

    def _index_em():
        return ak.stock_zh_index_daily_em(symbol=symbol)

    def _stock_hist():
        return ak.stock_zh_a_hist(
            symbol=code6,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )

    is_index = code6.startswith("000")
    if is_index:
        order = (_index_daily, _index_em, _em_etf, _sina_etf, _stock_hist)
        volume_in_lots = False
    else:
        order = (_em_etf, _sina_etf, _stock_hist, _index_daily)
        volume_in_lots = True
    frame = _call_first(order)
    if frame is None or frame.empty:
        return pd.DataFrame(columns=SCHEMA)
    # Sina-wrapped frames are already in shares; EM ETF volume is lots.
    source_cols = set(str(column) for column in frame.columns)
    em_like = bool(source_cols & {"成交量", "成交额", "开盘", "收盘"})
    return normalize_bars(frame, volume_in_lots=(volume_in_lots and em_like))


def bars_from_stockdb_payload(payload):
    if payload is None or payload == "":
        return pd.DataFrame(columns=SCHEMA)
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return pd.DataFrame(columns=SCHEMA)
        payload = json.loads(text)
    if isinstance(payload, dict):
        if "data" in payload and not any(key in payload for key in ("close", "open", "date")):
            payload = payload["data"]
        elif any(key in payload for key in SCHEMA):
            payload = [payload]
        else:
            nested = None
            for value in payload.values():
                if isinstance(value, list):
                    nested = value
                    break
            payload = nested if nested is not None else [payload]
    if not isinstance(payload, list) or not payload:
        return pd.DataFrame(columns=SCHEMA)
    if isinstance(payload[0], dict):
        return normalize_bars(pd.DataFrame(payload))
    width = len(payload[0])
    columns = SCHEMA[:width] if width <= 7 else None
    frame = pd.DataFrame(payload, columns=columns)
    return normalize_bars(frame)


def _stockdb_local_paths(code, directory):
    code6 = six_digit(code)
    names = (
        code,
        code6,
        code.replace(".SS", ".SH").replace(".SZ", ".SZ"),
        "日k_%s" % code6,
    )
    suffixes = (".parquet", ".csv")
    paths = []
    for name in names:
        for suffix in suffixes:
            paths.append(os.path.join(directory, name + suffix))
            paths.append(os.path.join(directory, "日k", name + suffix))
    return paths


def _load_stockdb_local(code, directory):
    for path in _stockdb_local_paths(code, directory):
        if not os.path.isfile(path):
            continue
        if path.endswith(".csv"):
            frame = pd.read_csv(path)
        else:
            frame = pd.read_parquet(path)
        frame = normalize_bars(frame)
        if not frame.empty:
            return frame
    return pd.DataFrame(columns=SCHEMA)


def _stockdb_http_urls(base, code, start, end):
    code6 = six_digit(code)
    tokens = (
        "日k:%s:%s<%s" % (code6, start, end),
        "日k:%s:%s<N" % (code6, start),
        "日k:%s:*" % code6,
    )
    urls = []
    for cmd in ("get", "vals"):
        for token in tokens:
            query = urllib.parse.urlencode({"cmd": cmd, "t": token}, safe=":<>*")
            urls.append("%s/?%s" % (base, query))
            urls.append("%s/?cmd=%s&t=%s" % (base, cmd, token))
    return urls


def _fetch_stockdb_http(code, start, end):
    base = os.environ.get("FREE_STOCKDB_URL", "http://127.0.0.1:7899").rstrip("/")
    last_error = None
    for url in _stockdb_http_urls(base, code, start, end):
        try:
            raw = _http_get(url)
            frame = bars_from_stockdb_payload(raw)
        except Exception as exc:
            last_error = exc
            continue
        if not frame.empty:
            return frame
    if last_error is not None:
        raise last_error
    return pd.DataFrame(columns=SCHEMA)


def _fetch_stockdb_sdk(code, start, end):
    try:
        from stock_sdk import StockDBClient
    except ImportError:
        try:
            from pybao.stock_sdk import StockDBClient
        except ImportError:
            return pd.DataFrame(columns=SCHEMA)
    client = StockDBClient()
    frame = client.get_data(
        code=six_digit(code),
        start=start,
        end=end,
        frequency="1d",
        fq=None,
        as_df=True,
    )
    return normalize_bars(frame)


def fetch_free_stockdb(code, sina_symbol=None, start="20160101", end=None):
    """Local hello245m/free-stockdb engine: dump dir, HTTP :7899, or Python SDK."""
    end = end or TARGET_LAST_DATE.strftime("%Y%m%d")
    directory = os.environ.get("FREE_STOCKDB_DIR")
    if directory:
        frame = _load_stockdb_local(code, directory)
        if not frame.empty:
            return frame
    try:
        frame = _fetch_stockdb_http(code, start, end)
        if not frame.empty:
            return frame
    except Exception:
        frame = pd.DataFrame(columns=SCHEMA)
    sdk_frame = _fetch_stockdb_sdk(code, start, end)
    if not sdk_frame.empty:
        return sdk_frame
    return frame


SOURCE_FETCHERS = {
    "sina": fetch_sina,
    "tencent": fetch_tencent,
    "ths": fetch_ths,
    "baostock": fetch_baostock,
    "akshare": fetch_akshare,
    "free-stockdb": fetch_free_stockdb,
}


def fetch_one(code, sina_symbol=None, sources=None):
    last_error = None
    for name in resolve_sources(sources):
        try:
            frame = SOURCE_FETCHERS[name](code, sina_symbol=sina_symbol)
        except Exception as exc:
            print("  %s fail %s %s" % (name, code, exc))
            last_error = exc
            continue
        if frame is not None and not frame.empty:
            return normalize_bars(frame), name
        time.sleep(PAUSE_SEC)
    if last_error is not None:
        print("  all sources failed %s last=%s" % (code, last_error))
    return pd.DataFrame(columns=SCHEMA), None


def probe_sources(code="510300.SS", sina_symbol="sh510300", sources=None):
    rows = []
    for name in resolve_sources(sources):
        started = time.time()
        error = None
        frame = pd.DataFrame(columns=SCHEMA)
        try:
            frame = SOURCE_FETCHERS[name](code, sina_symbol=sina_symbol)
        except Exception as exc:
            error = str(exc)
        elapsed_ms = int((time.time() - started) * 1000)
        rows.append(
            {
                "source": name,
                "ok": bool(frame is not None and not frame.empty),
                "rows": 0 if frame is None or frame.empty else int(len(frame)),
                "first": None
                if frame is None or frame.empty
                else str(pd.to_datetime(frame["date"].iloc[0]).date()),
                "last": None
                if frame is None or frame.empty
                else str(pd.to_datetime(frame["date"].iloc[-1]).date()),
                "ms": elapsed_ms,
                "error": error,
            }
        )
    return rows
