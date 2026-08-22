# -*- coding: utf-8 -*-
import ast
from pathlib import Path

import pandas as pd
import pytest

from research.source_adapters import (
    DEFAULT_SOURCES,
    SCHEMA,
    baostock_code_of,
    bars_from_stockdb_payload,
    fetch_akshare,
    fetch_baostock,
    fetch_free_stockdb,
    fetch_one,
    fetch_ths,
    market_of,
    normalize_bars,
    parse_ths_jsonp,
    resolve_sources,
    sina_symbol_of,
    six_digit,
    ths_symbol_of,
)


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_LIVE_IMPORTS = {
    "akshare",
    "aakshare",
    "baostock",
    "stockdb",
    "stock_sdk",
    "mootdx",
    "sklearn",
}


def _sample_bars(n=3, start="2020-01-02"):
    dates = pd.bdate_range(start, periods=n)
    close = pd.Series(range(10, 10 + n), dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": [1000.0] * n,
            "amount": (close * 1000.0).tolist(),
        }
    )


def test_code_helpers_map_etf_and_index_symbols():
    assert six_digit("510300.SS") == "510300"
    assert market_of("510300.SS") == "sh"
    assert market_of("159915.SZ") == "sz"
    assert market_of("000300.SS") == "sh"
    assert sina_symbol_of("159915.SZ") == "sz159915"
    assert baostock_code_of("510300.SS") == "sh.510300"
    assert baostock_code_of("159915.SZ") == "sz.159915"
    assert ths_symbol_of("513100.SS") == "hs_513100"


def test_resolve_sources_aliases_aakshare_and_tonghuashun():
    assert resolve_sources("aakshare,tonghuashun,10jqka,akshare") == ("akshare", "ths")
    assert resolve_sources("free_stockdb,stockdb") == ("free-stockdb",)
    assert resolve_sources(None) == DEFAULT_SOURCES
    with pytest.raises(ValueError):
        resolve_sources("not-a-source")


def test_normalize_bars_maps_chinese_columns_and_lot_volume():
    raw = pd.DataFrame(
        {
            "日期": ["20200102", "20200103"],
            "开盘": ["1.0", "1.1"],
            "最高": ["1.2", "1.3"],
            "最低": ["0.9", "1.0"],
            "收盘": ["1.1", "1.2"],
            "成交量": ["10", "20"],
        }
    )
    frame = normalize_bars(raw, volume_in_lots=True)
    assert list(frame.columns) == SCHEMA
    assert frame["volume"].tolist() == [1000.0, 2000.0]
    assert frame["amount"].tolist() == [1100.0, 2400.0]


def test_parse_ths_jsonp_splits_semicolon_rows_and_converts_lots():
    raw = (
        'quotebridge_v6_line_hs_510300_01_all({"data":'
        '"20200102,3.50,3.60,3.40,3.55,10,3550;20200103,3.55,3.70,3.50,3.66,20,7320"})'
    )
    frame = parse_ths_jsonp(raw)
    assert len(frame) == 2
    assert frame["close"].tolist() == [3.55, 3.66]
    assert frame["volume"].tolist() == [1000.0, 2000.0]
    assert parse_ths_jsonp("<html>blocked</html>").empty
    assert parse_ths_jsonp("window.location.href='/'").empty


def test_bars_from_stockdb_payload_accepts_dict_list_and_range_json():
    rows = [
        {
            "date": 20200102,
            "open": 3.5,
            "high": 3.6,
            "low": 3.4,
            "close": 3.55,
            "volume": 1000,
            "amount": 3550,
        }
    ]
    frame = bars_from_stockdb_payload(rows)
    assert frame["close"].iloc[0] == 3.55
    wrapped = bars_from_stockdb_payload({"data": rows})
    assert len(wrapped) == 1
    keyed = bars_from_stockdb_payload({"510300": rows})
    assert keyed["volume"].iloc[0] == 1000.0
    assert bars_from_stockdb_payload("").empty


def test_fetch_one_falls_through_empty_then_uses_next_source(monkeypatch):
    import research.source_adapters as adapters

    calls = []

    def empty(_code, sina_symbol=None):
        calls.append("sina")
        return pd.DataFrame(columns=SCHEMA)

    def boom(_code, sina_symbol=None):
        calls.append("baostock")
        raise RuntimeError("login down")

    def ok(_code, sina_symbol=None):
        calls.append("ths")
        return _sample_bars()

    monkeypatch.setitem(adapters.SOURCE_FETCHERS, "sina", empty)
    monkeypatch.setitem(adapters.SOURCE_FETCHERS, "baostock", boom)
    monkeypatch.setitem(adapters.SOURCE_FETCHERS, "ths", ok)

    frame, source = fetch_one(
        "510300.SS", "sh510300", sources=["sina", "baostock", "ths"], min_rows=1
    )
    assert source == "ths"
    assert len(frame) == 3
    assert calls == ["sina", "baostock", "ths"]


def test_fetch_one_skips_short_series_so_recent_only_feeds_cannot_win(monkeypatch):
    import research.source_adapters as adapters

    def short(_code, sina_symbol=None):
        return _sample_bars(n=3)

    def long(_code, sina_symbol=None):
        return _sample_bars(n=5, start="2018-01-02")

    monkeypatch.setitem(adapters.SOURCE_FETCHERS, "baostock", short)
    monkeypatch.setitem(adapters.SOURCE_FETCHERS, "ths", long)
    frame, source = fetch_one(
        "510300.SS", "sh510300", sources=["baostock", "ths"], min_rows=4
    )
    assert source == "ths"
    assert len(frame) == 5


def _ths_opener_stub():
    return type("O", (), {"open": staticmethod(lambda *args, **kwargs: None)})()


def test_fetch_ths_uses_all_js_when_history_is_long_enough(monkeypatch):
    def fake_get(url, code, opener):
        assert "all.js" in url
        rows = []
        for year in range(2018, 2027):
            for day in range(1, 46):
                month = 1 if day <= 28 else 2
                dom = day if day <= 28 else day - 28
                rows.append("%d%02d%02d,1,1,1,1,1,1" % (year, month, dom))
        return 'quotebridge({"data":"%s"})' % ";".join(rows)

    monkeypatch.setattr("research.source_adapters._ths_get", fake_get)
    monkeypatch.setattr("research.source_adapters._ths_opener", _ths_opener_stub)
    frame = fetch_ths("510300.SS", start_year=2018, end_year=2018)
    assert len(frame) >= 400
    assert frame["volume"].iloc[0] == 100.0


def test_fetch_ths_merges_yearly_files_when_all_js_is_short(monkeypatch):
    def fake_get(url, code, opener):
        if "all.js" in url:
            return 'quotebridge({"data":"20200102,1,1,1,1,1,1"})'
        if url.endswith("/2020.js"):
            return 'quotebridge({"data":"20200102,1,1,1,1,2,1;20200103,1,1,1,1,3,1"})'
        return "<html>no</html>"

    monkeypatch.setattr("research.source_adapters._ths_get", fake_get)
    monkeypatch.setattr("research.source_adapters._ths_opener", _ths_opener_stub)
    frame = fetch_ths("510300.SS", start_year=2020, end_year=2020)
    assert list(frame["volume"]) == [200.0, 300.0]


def test_fetch_baostock_reads_query_rows(monkeypatch):
    class Result(object):
        error_code = "0"
        error_msg = ""
        fields = ["date", "open", "high", "low", "close", "volume", "amount"]

        def __init__(self):
            self._rows = [
                ["2020-01-02", "1", "1.2", "0.9", "1.1", "1000", "1100"],
                ["2020-01-03", "1.1", "1.3", "1.0", "1.2", "2000", "2400"],
            ]

        def next(self):
            return bool(self._rows)

        def get_row_data(self):
            return self._rows.pop(0)

    class FakeBs(object):
        def login(self):
            return type("Login", (), {"error_code": "0", "error_msg": ""})()

        def query_history_k_data_plus(self, *args, **kwargs):
            assert kwargs["adjustflag"] == "3"
            assert args[0] == "sh.510300"
            return Result()

    monkeypatch.setattr("research.source_adapters._import_baostock", lambda: FakeBs())
    monkeypatch.setattr("research.source_adapters._BAOSTOCK_LOGGED_IN", False)
    import research.source_adapters as adapters

    adapters._BAOSTOCK_LOGGED_IN = False
    frame = fetch_baostock("510300.SS")
    assert list(frame["close"]) == [1.1, 1.2]
    assert list(frame["volume"]) == [1000.0, 2000.0]


def test_fetch_akshare_prefers_em_etf_and_treats_aakshare_alias(monkeypatch):
    class FakeAk(object):
        def fund_etf_hist_em(self, **kwargs):
            assert kwargs["symbol"] == "510300"
            assert kwargs["adjust"] == ""
            return pd.DataFrame(
                {
                    "日期": ["2020-01-02"],
                    "开盘": [1.0],
                    "最高": [1.2],
                    "最低": [0.9],
                    "收盘": [1.1],
                    "成交量": [10],
                    "成交额": [1100],
                }
            )

        def fund_etf_hist_sina(self, **kwargs):
            raise AssertionError("sina should not run when EM succeeds")

    monkeypatch.setattr("research.source_adapters._import_akshare", lambda: FakeAk())
    frame = fetch_akshare("510300.SS")
    assert frame["volume"].iloc[0] == 1000.0
    assert resolve_sources(["aakshare"]) == ("akshare",)


def test_fetch_free_stockdb_reads_local_dump(tmp_path, monkeypatch):
    path = tmp_path / "510300.SS.parquet"
    _sample_bars().to_parquet(path, index=False)
    monkeypatch.setenv("FREE_STOCKDB_DIR", str(tmp_path))
    frame = fetch_free_stockdb("510300.SS")
    assert len(frame) == 3
    assert frame["close"].iloc[0] == 10.0


def test_fetch_free_stockdb_http_parses_engine_json(monkeypatch):
    payload = [
        {
            "date": 20200102,
            "open": 1.0,
            "high": 1.2,
            "low": 0.9,
            "close": 1.1,
            "volume": 1000,
            "amount": 1100,
        }
    ]

    def fake_get(url, headers=None, encoding="utf-8", opener=None):
        assert "cmd=" in url
        return __import__("json").dumps(payload)

    monkeypatch.delenv("FREE_STOCKDB_DIR", raising=False)
    monkeypatch.setattr("research.source_adapters._http_get", fake_get)
    monkeypatch.setattr("research.source_adapters._fetch_stockdb_sdk", lambda *args, **kwargs: pd.DataFrame(columns=SCHEMA))
    frame = fetch_free_stockdb("510300.SS")
    assert frame["close"].iloc[0] == 1.1


def test_fetch_free_stockdb_surfaces_http_error_when_engine_is_down(monkeypatch):
    monkeypatch.delenv("FREE_STOCKDB_DIR", raising=False)

    def boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("research.source_adapters._http_get", boom)
    monkeypatch.setattr(
        "research.source_adapters._fetch_stockdb_sdk",
        lambda *args, **kwargs: pd.DataFrame(columns=SCHEMA),
    )
    with pytest.raises(OSError, match="connection refused"):
        fetch_free_stockdb("510300.SS")


def test_fetch_cli_selects_universe_from_comma_string():
    from research.fetch_free_etf_bars import _selected_universe

    rows = _selected_universe("510300.SS,159915.SZ")
    assert [row[0] for row in rows] == ["510300.SS", "159915.SZ"]
    assert _selected_universe("sh510300")[0][0] == "510300.SS"


def test_live_ptrade_files_do_not_import_research_feeds():
    files = sorted(ROOT.glob("ptrade_*.py"))
    assert files
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert imports.isdisjoint(FORBIDDEN_LIVE_IMPORTS), path.name
        assert "source_adapters" not in path.read_text(encoding="utf-8")
        assert "fetch_free_etf_bars" not in path.read_text(encoding="utf-8")
