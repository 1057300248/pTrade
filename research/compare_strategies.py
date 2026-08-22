#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run available ETF backtests and write a compact strategy comparison."""

from __future__ import print_function

import contextlib
import importlib.util
import inspect
import io
import math
import os
import re


HERE = os.path.abspath(os.path.dirname(__file__))
OUTPUT = os.path.join(HERE, "compare_strategies.md")
STRATEGIES = (
    ("RMDC", "backtest_rmdc_etf"),
    ("Combo", "backtest_combo_etf"),
    ("GEM", "backtest_gem_etf"),
)
MONTHS = ("2024-02", "2026-07")
START = "2018-01-01"
END = "2026-08-21"
IS_END = "2021-12-31"
OOS_START = "2022-01-01"

SAMPLE_RE = re.compile(
    r"backtest\s+(\d{4}-\d{2}-\d{2})\s*(?:\.\.|~|to)\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
METRICS_RE = re.compile(
    r"strategy\s*:\s*CAGR=\s*([-+]?\d+(?:\.\d+)?)%"
    r".*?MDD=\s*([-+]?\d+(?:\.\d+)?)%"
    r".*?Sharpe=\s*([-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
WINDOW_RE = re.compile(
    r"window\s+(\d{4}-\d{2})-\d{2}\s*\.\.\s*\d{4}-\d{2}-\d{2}"
    r"\s*:\s*strategy\s+ret=\s*([-+]?\d+(?:\.\d+)?)%",
    re.IGNORECASE,
)
SUBPERIOD_RE = re.compile(
    r"^(IS|OOS)\b[^\n]*\n\s*strategy\s*:\s*CAGR="
    r"\s*([-+]?\d+(?:\.\d+)?)%",
    re.IGNORECASE | re.MULTILINE,
)


def _load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot create an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _callable_without_required_args(func):
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return False
    return not any(
        parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in parameters
    )


def _run_or_import_results(module):
    for name in ("run", "main"):
        candidate = getattr(module, name, None)
        if callable(candidate) and _callable_without_required_args(candidate):
            return candidate(), name
    for name in ("RESULTS", "results", "SUMMARY", "summary"):
        if hasattr(module, name):
            return getattr(module, name), name
    return None, None


def _mapping_value(mapping, names):
    if not isinstance(mapping, dict):
        return None
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _as_number(value, percent=False):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        is_percent = text.endswith("%")
        if is_percent:
            text = text[:-1]
        number = float(text)
        return number / 100.0 if is_percent or percent else number
    number = float(value)
    return number / 100.0 if percent else number


def _result_mapping(result):
    if not isinstance(result, dict):
        return {}
    full = result.get("full")
    if isinstance(full, dict):
        return full
    if isinstance(full, (tuple, list)) and len(full) >= 3:
        return {"cagr": full[0], "mdd": full[1], "sharpe": full[2]}
    if any(key in result for key in ("cagr", "ann", "mdd", "maxdd", "sharpe")):
        return result
    for key in ("strategy", "summary", "stats", "metrics"):
        value = result.get(key)
        if isinstance(value, dict):
            return value
    return result


def _window_return(mapping, month):
    if not isinstance(mapping, dict):
        return None
    for container_name in ("windows", "window_returns", "stress_windows"):
        container = mapping.get(container_name)
        if not isinstance(container, dict):
            continue
        value = container.get(month)
        if value is None:
            for key, candidate in container.items():
                if str(key).startswith(month):
                    value = candidate
                    break
        if isinstance(value, dict):
            value = _mapping_value(value, ("return", "ret", "strategy_return"))
        elif isinstance(value, (tuple, list)):
            value = value[0] if value else None
        if value is not None:
            return _as_number(value)
    return None


def _subperiod_cagrs(result, output):
    values = {"is": None, "oos": None}
    if isinstance(result, dict):
        for name in values:
            value = result.get(name)
            if isinstance(value, dict):
                value = _mapping_value(value, ("cagr", "ann", "annual_return"))
            elif isinstance(value, (tuple, list)):
                value = value[0] if value else None
            if value is not None:
                values[name] = _as_number(value)
    for name, value in SUBPERIOD_RE.findall(output):
        key = name.lower()
        if values[key] is None:
            values[key] = _as_number(value, percent=True)
    return values


def _extract_row(strategy, result, output):
    mapping = _result_mapping(result)
    cagr = _as_number(_mapping_value(mapping, ("cagr", "ann", "annual_return")))
    mdd = _as_number(_mapping_value(mapping, ("mdd", "maxdd", "max_drawdown")))
    sharpe = _as_number(_mapping_value(mapping, ("sharpe", "sharpe_ratio")))

    metric_match = METRICS_RE.search(output)
    if metric_match:
        if cagr is None:
            cagr = _as_number(metric_match.group(1), percent=True)
        if mdd is None:
            mdd = _as_number(metric_match.group(2), percent=True)
        if sharpe is None:
            sharpe = _as_number(metric_match.group(3))

    sample = _mapping_value(mapping, ("sample", "period", "date_range"))
    if sample is None:
        start = _mapping_value(mapping, ("start", "start_date"))
        end = _mapping_value(mapping, ("end", "end_date"))
        if start is not None and end is not None:
            sample = "%s to %s" % (start, end)
    if sample is None:
        sample_match = SAMPLE_RE.search(output)
        if sample_match:
            sample = "%s to %s" % sample_match.groups()

    windows = {}
    for month in MONTHS:
        value = _window_return(mapping, month)
        if value is None:
            value = _window_return(result, month)
        windows[month] = value
    for month, value in WINDOW_RE.findall(output):
        if month in windows and windows[month] is None:
            windows[month] = _as_number(value, percent=True)
    subperiods = _subperiod_cagrs(result, output)

    missing = [
        name
        for name, value in (
            ("sample", sample),
            ("CAGR", cagr),
            ("MDD", mdd),
            ("Sharpe", sharpe),
        )
        if value is None
    ]
    if missing:
        raise ValueError("missing %s" % ", ".join(missing))
    return {
        "strategy": strategy,
        "sample": str(sample),
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
        "windows": windows,
        "is_cagr": subperiods["is"],
        "oos_cagr": subperiods["oos"],
    }


def _benchmark_row():
    import numpy as np
    import pandas as pd

    path = os.path.join(HERE, "cache", "etf_daily", "510300.SS.parquet")
    if not os.path.isfile(path):
        raise IOError("%s is missing" % path)
    frame = pd.read_parquet(path)
    frame = frame.dropna(subset=["date", "close"]).sort_values("date")
    frame = frame.drop_duplicates("date", keep="last")
    dates = pd.DatetimeIndex(frame["date"])
    mask = (dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))
    dates = dates[mask]
    navs = frame.loc[mask, "close"].to_numpy(dtype=float)
    navs = navs / navs[0]

    def perf(sub_navs, sub_dates):
        years = max((sub_dates[-1] - sub_dates[0]).days / 365.25, 1e-9)
        cagr = float((sub_navs[-1] / sub_navs[0]) ** (1.0 / years) - 1.0)
        peak = np.maximum.accumulate(sub_navs)
        mdd = float(np.min(sub_navs / peak - 1.0))
        returns = np.diff(sub_navs) / sub_navs[:-1]
        std = float(np.std(returns, ddof=1)) if len(returns) > 2 else 0.0
        sharpe = float(np.mean(returns) / std * math.sqrt(252.0)) if std > 0 else 0.0
        return cagr, mdd, sharpe

    def subperiod(start, end):
        sub_mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        sub_navs = navs[sub_mask]
        if len(sub_navs) < 2:
            return None
        return perf(sub_navs / sub_navs[0], dates[sub_mask])

    full = perf(navs, dates)
    windows = {}
    for month in MONTHS:
        start = month + "-01"
        end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        window = subperiod(start, end)
        sub_mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        sub_navs = navs[sub_mask]
        windows[month] = (
            float(sub_navs[-1] / sub_navs[0] - 1.0) if window is not None else None
        )
    is_perf = subperiod(START, IS_END)
    oos_perf = subperiod(OOS_START, END)
    return {
        "strategy": "510300 buy-and-hold",
        "sample": "%s to %s" % (dates[0].date(), dates[-1].date()),
        "cagr": full[0],
        "mdd": full[1],
        "sharpe": full[2],
        "windows": windows,
        "is_cagr": None if is_perf is None else is_perf[0],
        "oos_cagr": None if oos_perf is None else oos_perf[0],
    }


def _percent(value):
    return "n/a" if value is None else "%.2f%%" % (value * 100.0)


def _write_markdown(rows):
    lines = [
        "# ETF strategy comparison",
        "",
        "| strategy | sample | CAGR | MDD | Sharpe | 2024-02 | 2026-07 | IS CAGR | OOS CAGR |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {strategy} | {sample} | {cagr} | {mdd} | {sharpe:.2f} | "
            "{feb} | {jul} | {is_cagr} | {oos_cagr} |".format(
                strategy=row["strategy"],
                sample=row["sample"],
                cagr=_percent(row["cagr"]),
                mdd=_percent(row["mdd"]),
                sharpe=row["sharpe"],
                feb=_percent(row["windows"]["2024-02"]),
                jul=_percent(row["windows"]["2026-07"]),
                is_cagr=_percent(row["is_cagr"]),
                oos_cagr=_percent(row["oos_cagr"]),
            )
        )
    lines.extend(
        [
            "",
            "The stress-window columns show strategy returns for each calendar month.",
            "",
        ]
    )
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main():
    rows = []
    for strategy, module_name in STRATEGIES:
        path = os.path.join(HERE, module_name + ".py")
        if not os.path.isfile(path):
            print("Skipping %s: %s is missing." % (strategy, os.path.basename(path)))
            continue
        try:
            module = _load_module(module_name, path)
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                result, source = _run_or_import_results(module)
            output = captured.getvalue()
            if output:
                print(output.rstrip())
            if source is None:
                print("Skipping %s: no callable backtest or imported results." % strategy)
                continue
            rows.append(_extract_row(strategy, result, output))
        except Exception as exc:
            print("Skipping %s: backtest failed: %s" % (strategy, exc))

    try:
        rows.append(_benchmark_row())
    except Exception as exc:
        print("Skipping 510300 buy-and-hold: %s" % exc)

    if not rows:
        raise RuntimeError("no strategy produced a complete result row")
    _write_markdown(rows)
    print("Wrote %s with %d strategy row(s)." % (OUTPUT, len(rows)))
    return rows


if __name__ == "__main__":
    main()
