#!/usr/bin/env python3
"""Download/cache US adjusted closes and run the OpenAlphas reproduction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from openalphas_rp_mom import DEFAULT_PARAMS, run_article_backtest


POOL = (
    "SPY",
    "QQQ",
    "GLD",
    "TLT",
    "XLV",
    "XLF",
    "XLK",
    "XLE",
    "EWJ",
    "FXI",
    "HYG",
    "LQD",
    "SLV",
    "USO",
    "EEM",
)
BACKTEST_START = "2018-01-01"
PUBLISHED_END = "2024-03-31"
EXTENDED_END = "2026-08-21"
# More than 500 trading sessions before the first possible 2018 Friday.
DOWNLOAD_START = "2015-01-01"
CACHE_DIR = Path(__file__).resolve().parent / "cache" / "openalphas_us"
METADATA_PATH = CACHE_DIR / "_metadata.json"
RESULTS_PATH = Path(__file__).resolve().parent / "openalphas_us_results.md"


def _normalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    normalized = panel.copy()
    normalized.index = pd.DatetimeIndex(pd.to_datetime(normalized.index)).tz_localize(
        None
    )
    normalized = normalized.apply(pd.to_numeric, errors="coerce")
    normalized = normalized.sort_index().loc[
        ~normalized.index.duplicated(keep="last")
    ]
    missing = [ticker for ticker in POOL if ticker not in normalized.columns]
    if missing:
        raise ValueError("source omitted tickers: %s" % ", ".join(missing))
    normalized = normalized.loc[:, list(POOL)].dropna(how="any")
    normalized = normalized.loc[
        (normalized.index >= pd.Timestamp(DOWNLOAD_START))
        & (normalized.index <= pd.Timestamp(EXTENDED_END))
    ]
    if len(normalized) < 750:
        raise ValueError("only %d aligned rows returned" % len(normalized))
    if normalized.index.min() > pd.Timestamp("2016-01-15"):
        raise ValueError("not enough pre-2018 indicator history")
    if normalized.index.max() < pd.Timestamp("2024-03-28"):
        raise ValueError(
            "data stop at %s, before published window"
            % normalized.index.max().date()
        )
    if (normalized <= 0.0).any().any():
        raise ValueError("source returned non-positive adjusted closes")
    return normalized.astype(float)


def _download_yfinance() -> tuple[pd.DataFrame, str]:
    import yfinance as yf

    raw = yf.download(
        list(POOL),
        start=DOWNLOAD_START,
        end=(pd.Timestamp(EXTENDED_END) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=True,
        group_by="column",
    )
    if raw.empty:
        raise RuntimeError("empty response")
    if isinstance(raw.columns, pd.MultiIndex):
        first_level = raw.columns.get_level_values(0)
        if "Adj Close" not in first_level:
            raise RuntimeError("response has no Adj Close field")
        panel = raw["Adj Close"]
    else:
        if "Adj Close" not in raw:
            raise RuntimeError("response has no Adj Close field")
        if len(POOL) != 1:
            raise RuntimeError("unexpected single-level multi-ticker response")
        panel = raw[["Adj Close"]].rename(columns={"Adj Close": POOL[0]})
    return _normalize_panel(panel), "Yahoo Finance via yfinance (Adj Close)"


def _download_pandas_datareader_yahoo() -> tuple[pd.DataFrame, str]:
    from pandas_datareader import data as web

    series = {}
    for ticker in POOL:
        frame = web.DataReader(
            ticker, "yahoo", pd.Timestamp(DOWNLOAD_START), pd.Timestamp(EXTENDED_END)
        )
        if "Adj Close" not in frame:
            raise RuntimeError("%s has no Adj Close field" % ticker)
        series[ticker] = frame["Adj Close"]
    return (
        _normalize_panel(pd.DataFrame(series)),
        "Yahoo Finance via pandas_datareader (Adj Close)",
    )


def _download_stooq() -> tuple[pd.DataFrame, str]:
    from pandas_datareader import data as web

    series = {}
    for ticker in POOL:
        frame = web.DataReader(
            ticker + ".US",
            "stooq",
            pd.Timestamp(DOWNLOAD_START),
            pd.Timestamp(EXTENDED_END),
        )
        if "Close" not in frame:
            raise RuntimeError("%s has no Close field" % ticker)
        series[ticker] = frame["Close"].sort_index()
    return (
        _normalize_panel(pd.DataFrame(series)),
        "Stooq via pandas_datareader (Close; provider-adjusted history)",
    )


def _load_cache() -> tuple[pd.DataFrame, str] | None:
    paths = {ticker: CACHE_DIR / (ticker + ".parquet") for ticker in POOL}
    if not METADATA_PATH.is_file() or not all(path.is_file() for path in paths.values()):
        return None
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    series = {}
    for ticker, path in paths.items():
        frame = pd.read_parquet(path)
        if "Adj Close" not in frame.columns:
            raise ValueError("invalid cache schema: %s" % path)
        series[ticker] = frame["Adj Close"]
    panel = _normalize_panel(pd.DataFrame(series))
    return panel, str(metadata.get("source", "cached source not recorded"))


def _write_cache(panel: pd.DataFrame, source: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in POOL:
        panel[[ticker]].rename(columns={ticker: "Adj Close"}).to_parquet(
            CACHE_DIR / (ticker + ".parquet"), index=True
        )
    metadata = {
        "source": source,
        "tickers": list(POOL),
        "field": "Adj Close",
        "requested_start": DOWNLOAD_START,
        "requested_end": EXTENDED_END,
        "actual_start": str(panel.index.min().date()),
        "actual_end": str(panel.index.max().date()),
        "aligned_rows": int(len(panel)),
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_or_download_prices() -> tuple[pd.DataFrame, str, list[str]]:
    errors: list[str] = []
    try:
        cached = _load_cache()
        if cached is not None:
            return cached[0], cached[1] + " [parquet cache]", errors
    except Exception as exc:
        errors.append("cache: %s: %s" % (type(exc).__name__, exc))

    sources: tuple[tuple[str, Callable[[], tuple[pd.DataFrame, str]]], ...] = (
        ("yfinance", _download_yfinance),
        ("pandas_datareader/yahoo", _download_pandas_datareader_yahoo),
        ("pandas_datareader/stooq", _download_stooq),
    )
    for label, downloader in sources:
        print("Trying data source: %s" % label)
        try:
            panel, source = downloader()
            _write_cache(panel, source)
            return panel, source, errors
        except Exception as exc:
            message = "%s: %s: %s" % (label, type(exc).__name__, exc)
            errors.append(message)
            print("  failed: %s" % message)
    raise RuntimeError("all three data sources failed\n" + "\n".join(errors))


def _format_metrics(metrics: dict[str, float]) -> str:
    return "CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f  Final=$%s" % (
        metrics["cagr"] * 100.0,
        metrics["max_drawdown"] * 100.0,
        metrics["sharpe"],
        format(metrics["final_value"], ",.2f"),
    )


def _run_window(
    prices: pd.DataFrame, end_date: str, label: str
) -> tuple[str, dict]:
    params = dict(DEFAULT_PARAMS)
    params.update({"start_date": BACKTEST_START, "end_date": end_date})
    result = run_article_backtest(prices, params)
    actual_start = result["portfolio"].index.min().date()
    actual_end = result["portfolio"].index.max().date()
    heading = "%s (actual bars %s .. %s)" % (label, actual_start, actual_end)
    print(heading)
    print("  strategy : %s" % _format_metrics(result["metrics"]))
    print("  benchmark: %s" % _format_metrics(result["benchmark_metrics"]))
    print(
        "  Friday rebalances=%d  signals=%d  skipped=%d  trades=%d"
        % (
            len(result["rebalance_dates"]),
            len(result["signals"]),
            len(result["skipped_rebalances"]),
            len(result["trades"]),
        )
    )
    return heading, result


def _markdown_table_row(label: str, result: dict) -> str:
    strategy = result["metrics"]
    benchmark = result["benchmark_metrics"]
    actual_end = result["portfolio"].index.max().date()
    return (
        "| %s (through %s) | %.2f%% | %.2f%% | %.2f | %.2f%% | %.2f%% | %.2f |\n"
        % (
            label,
            actual_end,
            strategy["cagr"] * 100.0,
            abs(strategy["max_drawdown"]) * 100.0,
            strategy["sharpe"],
            benchmark["cagr"] * 100.0,
            abs(benchmark["max_drawdown"]) * 100.0,
            benchmark["sharpe"],
        )
    )


def _write_results(
    source: str,
    prices: pd.DataFrame | None,
    runs: list[tuple[str, dict]],
    errors: list[str],
    failure: str | None = None,
) -> None:
    lines = [
        "# OpenAlphas risk parity + momentum: US reproduction\n",
        "\n",
        "Research only; no live `ptrade_*.py` strategy is imported or changed.\n",
        "\n",
    ]
    if failure is not None:
        lines.extend(
            [
                "## Data failure\n",
                "\n",
                "The engine and unit-testable helpers are present, but the US run could not "
                "complete after all three configured sources failed.\n",
                "\n",
                "```\n",
                failure + "\n",
                "```\n",
            ]
        )
        RESULTS_PATH.write_text("".join(lines), encoding="utf-8")
        return

    assert prices is not None
    lines.extend(
        [
            "## Data\n",
            "\n",
            "- Pool: `" + ", ".join(POOL) + "`\n",
            "- Source: " + source + "\n",
            "- Field: adjusted close (the Stooq fallback uses its provider-adjusted "
            "historical Close)\n",
            "- Aligned data: %s through %s (%d sessions)\n"
            % (prices.index.min().date(), prices.index.max().date(), len(prices)),
            "- Cache: `research/cache/openalphas_us/*.parquet`\n",
            "\n",
            "## Results\n",
            "\n",
            "| Window | Strategy CAGR | Strategy MDD | Strategy Sharpe | "
            "Benchmark CAGR | Benchmark MDD | Benchmark Sharpe |\n",
            "|---|---:|---:|---:|---:|---:|---:|\n",
        ]
    )
    for label, result in runs:
        lines.append(_markdown_table_row(label, result))

    published = runs[0][1]["metrics"]
    cagr_gap = published["cagr"] * 100.0 - 52.3
    replicated = abs(cagr_gap) <= 1.0
    lines.extend(
        [
            "\n",
            "## Blog comparison\n",
            "\n",
            "Blog claim: CAGR 52.3%, MDD 14.7%, Sharpe 2.6. This run "
            + ("replicates" if replicated else "does **not** replicate")
            + " the claimed 52.3%% CAGR (difference %.2f percentage points). "
            % cagr_gap
            + "Parameters were not retuned.\n",
            "\n",
            "Mechanics: Friday dates missing from the price index are skipped; signals "
            "and fills use the same Friday close; transaction cost is 0.1% per side.\n",
        ]
    )
    if errors:
        lines.extend(
            [
                "\n",
                "Non-fatal source/cache attempts before the successful source:\n",
                "\n",
            ]
        )
        lines.extend("- `%s`\n" % error.replace("`", "'") for error in errors)
    RESULTS_PATH.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    try:
        prices, source, source_errors = load_or_download_prices()
    except Exception as exc:
        failure = "%s: %s" % (type(exc).__name__, exc)
        print(failure)
        _write_results("", None, [], [], failure=failure)
        return 1

    print("Data source: %s" % source)
    print(
        "Aligned adjusted closes: %s .. %s (%d rows, %d tickers)"
        % (
            prices.index.min().date(),
            prices.index.max().date(),
            len(prices),
            len(prices.columns),
        )
    )
    print("Pool: %s" % ", ".join(prices.columns))
    print("")

    published = _run_window(prices, PUBLISHED_END, "Published window")
    print("")
    extended = _run_window(prices, EXTENDED_END, "Extended window")
    runs = [published, extended]
    cagr = published[1]["metrics"]["cagr"] * 100.0
    print("")
    print(
        "Blog claim: CAGR=52.30%% MDD=14.70%% Sharpe=2.60; "
        "reproduced CAGR=%.2f%% (gap=%+.2f percentage points)"
        % (cagr, cagr - 52.3)
    )
    if abs(cagr - 52.3) > 1.0:
        print("Result is far from the blog claim; parameters were not retuned.")
    else:
        print("Result is within 1 percentage point of the claimed CAGR.")

    _write_results(source, prices, runs, source_errors)
    print("Wrote %s" % RESULTS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
