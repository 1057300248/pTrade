#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Leakage-safe weekly cross-sectional ETF factor walk-forward research.

The script reads the local parquet cache, computes factors only from data
available at each weekly signal date, evaluates next-week equity-only
cross-sectional Rank IC and per-ETF time-series IC, writes heatmaps, and
writes ``factor_walkforward_report.md``.

The factor transformations are fixed before the OOS period.  The expanding
window is therefore an information-set boundary rather than a fitted
cross-sectional model.  The only adaptive rule is the combo: for year Y it
uses factors whose pooled IC IR exceeded 0.3 in completed OOS years before Y.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from etf_panel import load_panel
except ImportError:
    from research.etf_panel import load_panel


HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache" / "etf_daily"
REPORT_PATH = HERE / "factor_walkforward_report.md"
PLOT_DIR = HERE / "plots"

MARKET = "510300.SS"
SIZE = "510500.SS"
NON_ETF_FILES = {"000300.SS"}
TEST_YEARS = tuple(range(2019, 2027))
MIN_CROSS_SECTION = 5
MIN_TS_WEEKS = 12
COMBO_IR_THRESHOLD = 0.30

# The GROWTH lists in ptrade_rmdc_etf.py and ptrade_combo_etf.py are identical.
# Keep the research universe explicit so importing this module never imports a
# live PTrade strategy.
EQUITY_CODES = (
    "510300.SS",
    "510500.SS",
    "512100.SS",
    "159915.SZ",
    "588000.SS",
    "512480.SS",
    "515880.SS",
    "515980.SS",
    "512660.SS",
    "512010.SS",
    "512800.SS",
    "512880.SS",
    "512690.SS",
    "512400.SS",
    "515030.SS",
    "516160.SS",
    "515220.SS",
)

FACTORS = (
    "ts_mom_12_1",
    "ts_mom_63",
    "ts_mom_21",
    "close_ma120",
    "close_ma60",
    "term_spread",
    "crowding_points",
    "residual_mom",
)

DISPLAY_NAME = {
    "ts_mom_12_1": "ts_mom_12_1",
    "ts_mom_63": "ts_mom_63",
    "ts_mom_21": "ts_mom_21",
    "close_ma120": "close/ma120",
    "close_ma60": "close/ma60",
    "term_spread": "term_spread",
    "crowding_points": "crowding_points",
    "residual_mom": "residual_mom",
}


def load_daily_panel() -> Dict[str, pd.DataFrame]:
    """Load all ETF files, excluding the standalone 000300 index series."""
    array_panel = load_panel(CACHE_DIR)
    panel = {}
    for code, bars in array_panel.items():
        if code in NON_ETF_FILES:
            continue
        panel[code] = pd.DataFrame(
            {
                column: bars[column]
                for column in ("high", "low", "close", "volume", "amount")
            },
            index=pd.DatetimeIndex(bars["dates"], name="date"),
        )
    missing_refs = {MARKET, SIZE}.difference(panel)
    if missing_refs:
        raise ValueError("missing required reference ETFs: %s" % sorted(missing_refs))
    return panel


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0.0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def _weekly_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return the actual final trading date in every Monday-Sunday week."""
    dates = pd.Series(index, index=index)
    periods = index.to_period("W-SUN")
    return pd.DatetimeIndex(dates.groupby(periods, sort=True).last().to_numpy())


def _residual_momentum(
    regression_frame: pd.DataFrame,
    signal_dates: pd.DatetimeIndex,
    fit_window: int = 120,
    score_window: int = 60,
    skip: int = 5,
) -> pd.Series:
    """Clone the live score: 120d OLS, latest 5 returns skipped, 60d residual sum/std."""
    clean = regression_frame.dropna().sort_index()
    values = clean.loc[:, ["asset", "market", "size_spread"]].to_numpy(dtype=float)
    clean_index = clean.index
    output = pd.Series(np.nan, index=signal_dates, dtype=float)

    for signal_date in signal_dates:
        available = int(clean_index.searchsorted(signal_date, side="right"))
        fit_end = available - skip
        fit_start = fit_end - fit_window
        if fit_start < 0:
            continue
        sample = values[fit_start:fit_end]
        y = sample[:, 0]
        x = np.column_stack(
            (np.ones(len(sample)), sample[:, 1], sample[:, 2])
        )
        beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
        residuals = y - x.dot(beta)
        tail = residuals[-score_window:]
        standard_deviation = float(np.std(tail, ddof=1))
        if np.isfinite(standard_deviation) and standard_deviation >= 1e-12:
            output.loc[signal_date] = float(np.sum(tail) / standard_deviation)
    return output


def _crowding_points(frame: pd.DataFrame) -> pd.Series:
    """Vectorized clone of the live 0-4 crowding score."""
    close = frame["close"]
    volume = frame["volume"]
    volume_ratio = _safe_ratio(
        volume.rolling(20, min_periods=20).mean(),
        volume.rolling(60, min_periods=60).mean(),
    )
    ma60 = close.rolling(60, min_periods=60).mean()
    close_volume_corr = close.rolling(20, min_periods=20).corr(volume)
    amplitude = _safe_ratio(frame["high"] - frame["low"], close.shift(1))
    mean_amplitude = amplitude.rolling(20, min_periods=20).mean()

    points = (
        (volume_ratio > 2.0).astype(float)
        + (_safe_ratio(close, ma60) - 1.0 > 0.15).astype(float)
        + (close_volume_corr < 0.10).astype(float)
        + (mean_amplitude > 0.04).astype(float)
    )
    return points.where(close.rolling(61, min_periods=61).count() >= 61)


def _reference_series(
    reference: pd.Series, target_index: pd.DatetimeIndex
) -> pd.Series:
    """Backward-only alignment for rare reference/ETF holiday mismatches."""
    return reference.reindex(target_index, method="ffill")


def build_factor_panel(daily: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Build one row per ETF and week, including the strict T+1-week label."""
    market_return = np.log(daily[MARKET]["close"]).diff().rename("market")
    size_return = np.log(daily[SIZE]["close"]).diff()
    size_spread = (size_return - market_return).rename("size_spread")

    records = []
    for code, source in sorted(daily.items()):
        frame = source.copy()
        close = frame["close"]
        asset_return = np.log(close).diff().rename("asset")
        weekly_dates = _weekly_dates(frame.index)

        features = pd.DataFrame(index=frame.index)
        features["close"] = close
        primary_12_1 = _safe_ratio(close.shift(21), close.shift(252)) - 1.0
        fallback_12_1 = _safe_ratio(close.shift(5), close.shift(126)) - 1.0
        features["ts_mom_12_1"] = primary_12_1.combine_first(fallback_12_1)
        features["ts_mom_63"] = close.pct_change(63)
        features["ts_mom_21"] = close.pct_change(21)
        ma120 = close.rolling(120, min_periods=120).mean()
        ma60 = close.rolling(60, min_periods=60).mean()
        features["close_ma120"] = _safe_ratio(close, ma120)
        features["close_ma60"] = _safe_ratio(close, ma60)
        features["term_spread"] = (
            close.pct_change(10) - close.pct_change(5)
        )
        features["crowding_points"] = _crowding_points(frame)

        regression_frame = pd.concat(
            [
                asset_return,
                _reference_series(market_return, frame.index),
                _reference_series(size_spread, frame.index),
            ],
            axis=1,
        )
        features["residual_mom"] = _residual_momentum(
            regression_frame, weekly_dates
        ).reindex(frame.index)

        weekly = features.loc[weekly_dates].copy()
        weekly["code"] = code
        weekly["signal_date"] = weekly.index
        period = weekly.index.to_period("W-SUN")
        weekly["week_order"] = np.asarray([item.ordinal for item in period], dtype=int)
        iso_calendar = weekly.index.isocalendar()
        weekly["iso_year"] = iso_calendar["year"].to_numpy(dtype=int)
        weekly["iso_week"] = iso_calendar["week"].to_numpy(dtype=int)

        next_week_order = weekly["week_order"].shift(-1)
        is_next_week = next_week_order.eq(weekly["week_order"] + 1)
        weekly["forward_return"] = (
            weekly["close"].shift(-1) / weekly["close"] - 1.0
        ).where(is_next_week)
        weekly["target_date"] = pd.Series(
            weekly.index, index=weekly.index
        ).shift(-1).where(is_next_week)
        records.append(weekly.reset_index(drop=True))

    panel = pd.concat(records, ignore_index=True, sort=False)
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    panel["target_date"] = pd.to_datetime(panel["target_date"])
    panel["test_year"] = panel["signal_date"].dt.year
    return panel


def weekly_rank_ic(
    frame: pd.DataFrame, factor: str, minimum_assets: int = MIN_CROSS_SECTION
) -> pd.Series:
    """Spearman (rank Pearson) IC for each week."""
    observations = {}
    columns = [factor, "forward_return"]
    for week_order, group in frame.groupby("week_order", sort=True):
        pair = group.loc[:, columns].replace([np.inf, -np.inf], np.nan).dropna()
        if len(pair) < minimum_assets:
            continue
        if pair[factor].nunique() < 2 or pair["forward_return"].nunique() < 2:
            continue
        ranks = pair.rank(method="average")
        value = ranks[factor].corr(ranks["forward_return"])
        if np.isfinite(value):
            observations[int(week_order)] = float(value)
    return pd.Series(observations, dtype=float, name=factor).sort_index()


def per_name_time_series_ic(
    frame: pd.DataFrame, factor: str, minimum_weeks: int = MIN_TS_WEEKS
) -> pd.Series:
    """Pearson corr(factor_t, next-week return_t) within each ETF."""
    observations = {}
    for code, group in frame.groupby("code", sort=True):
        pair = (
            group.loc[:, [factor, "forward_return"]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if len(pair) < minimum_weeks:
            continue
        if pair[factor].nunique() < 2 or pair["forward_return"].nunique() < 2:
            continue
        value = pair[factor].corr(pair["forward_return"])
        if np.isfinite(value):
            observations[str(code)] = float(value)
    return pd.Series(observations, dtype=float, name=factor).sort_index()


def ic_summary(values: Iterable[float]) -> Dict[str, float]:
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    count = int(len(series))
    if count == 0:
        return {
            "n": 0,
            "mean": np.nan,
            "ir": np.nan,
            "hit_rate": np.nan,
            "annualized_ic_sharpe": np.nan,
        }
    standard_deviation = float(series.std(ddof=1)) if count > 1 else np.nan
    mean = float(series.mean())
    ir = (
        mean / standard_deviation
        if standard_deviation and np.isfinite(standard_deviation)
        else np.nan
    )
    return {
        "n": count,
        "mean": mean,
        "ir": ir,
        "hit_rate": float((series > 0.0).mean()),
        "annualized_ic_sharpe": ir * math.sqrt(52.0) if np.isfinite(ir) else np.nan,
    }


def _combo_score(frame: pd.DataFrame, selected: Sequence[str]) -> pd.Series:
    if not selected:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    ranks = frame.groupby("week_order", sort=False)[list(selected)].rank(
        method="average", pct=True
    )
    complete = ranks.notna().sum(axis=1).eq(len(selected))
    return ranks.mean(axis=1).where(complete)


def _pooled_history(
    history: Mapping[str, List[pd.Series]], factor: str
) -> pd.Series:
    parts = history.get(factor, [])
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts).sort_index()


def run_walk_forward(panel: pd.DataFrame) -> Dict[str, object]:
    """Evaluate annual OOS slices and form the strictly lagged equity-CS combo."""
    cs_history: Dict[str, List[pd.Series]] = {factor: [] for factor in FACTORS}
    cs_annual: Dict[int, Dict[str, Dict[str, float]]] = {}
    ts_annual: Dict[int, Dict[str, Dict[str, float]]] = {}
    ts_name_values: Dict[int, Dict[str, pd.Series]] = {}
    combo_history: List[pd.Series] = []
    combo_selected: Dict[int, List[str]] = {}
    audit_rows = []
    tsmom_hit_rows = []
    oos_frames = []

    for year in TEST_YEARS:
        cutoff = pd.Timestamp(year=year, month=1, day=1)
        next_cutoff = pd.Timestamp(year=year + 1, month=1, day=1)

        # A training observation is eligible only if its T+1-week label is
        # already known before the test year starts.
        train = panel.loc[panel["target_date"] < cutoff].copy()
        test = panel.loc[
            (panel["signal_date"] >= cutoff)
            & (panel["signal_date"] < next_cutoff)
        ].copy()
        if not train.empty and not bool((train["target_date"] < cutoff).all()):
            raise AssertionError("training labels cross the %d test boundary" % year)
        if not test.empty and not bool(
            (test["signal_date"] >= cutoff).all()
            and (test["signal_date"] < next_cutoff).all()
        ):
            raise AssertionError("test signals fall outside year %d" % year)

        equity_test = test.loc[test["code"].isin(EQUITY_CODES)].copy()
        present_equities = set(equity_test["code"].unique())
        unexpected_equities = present_equities.difference(EQUITY_CODES)
        if unexpected_equities or len(present_equities) < MIN_CROSS_SECTION:
            raise AssertionError(
                "invalid equity cross-section in %d: count=%d unexpected=%s"
                % (year, len(present_equities), sorted(unexpected_equities))
            )

        # Freeze combo membership before evaluating any labels in this year.
        selected = []
        if year > TEST_YEARS[0]:
            for factor in FACTORS:
                prior_values = _pooled_history(cs_history, factor)
                prior_ir = ic_summary(prior_values)["ir"]
                if np.isfinite(prior_ir) and prior_ir > COMBO_IR_THRESHOLD:
                    selected.append(factor)
        combo_selected[year] = selected
        equity_test["combo"] = _combo_score(equity_test, selected)
        combo_values = (
            weekly_rank_ic(equity_test, "combo")
            if selected
            else pd.Series(dtype=float)
        )
        combo_history.append(combo_values)

        cs_annual[year] = {}
        ts_annual[year] = {}
        ts_name_values[year] = {}
        for factor in FACTORS:
            cs_values = weekly_rank_ic(equity_test, factor)
            cs_annual[year][factor] = ic_summary(cs_values)
            cs_history[factor].append(cs_values)

            ts_values = per_name_time_series_ic(test, factor)
            ts_name_values[year][factor] = ts_values
            ts_annual[year][factor] = ic_summary(ts_values)
        cs_annual[year]["combo"] = ic_summary(combo_values)

        positive_tsmom = equity_test.loc[
            equity_test["ts_mom_12_1"].gt(0.0)
            & equity_test["forward_return"].notna()
        ]
        tsmom_hit_rows.append(
            {
                "year": year,
                "weeks": int(positive_tsmom["week_order"].nunique()),
                "observations": int(len(positive_tsmom)),
                "hit_rate": (
                    float(positive_tsmom["forward_return"].gt(0.0).mean())
                    if not positive_tsmom.empty
                    else np.nan
                ),
            }
        )
        oos_frames.append(test)

        labeled_test = test.loc[test["forward_return"].notna()]
        audit_rows.append(
            {
                "year": year,
                "train_start": (
                    train["signal_date"].min().date().isoformat()
                    if not train.empty
                    else "N/A"
                ),
                "last_train_label": (
                    train["target_date"].max().date().isoformat()
                    if not train.empty
                    else "N/A"
                ),
                "train_weeks": int(train["week_order"].nunique()),
                "test_start": (
                    labeled_test["signal_date"].min().date().isoformat()
                    if not labeled_test.empty
                    else "N/A"
                ),
                "test_end": (
                    labeled_test["signal_date"].max().date().isoformat()
                    if not labeled_test.empty
                    else "N/A"
                ),
                "test_weeks": int(labeled_test["week_order"].nunique()),
            }
        )

    oos_panel = pd.concat(oos_frames, ignore_index=True, sort=False)
    cs_pooled = {
        factor: ic_summary(_pooled_history(cs_history, factor))
        for factor in FACTORS
    }
    cs_pooled["combo"] = ic_summary(pd.concat(combo_history))
    ts_pooled_values = {
        factor: per_name_time_series_ic(oos_panel, factor) for factor in FACTORS
    }
    ts_pooled = {
        factor: ic_summary(ts_pooled_values[factor]) for factor in FACTORS
    }
    positive_tsmom_oos = oos_panel.loc[
        oos_panel["code"].isin(EQUITY_CODES)
        & oos_panel["ts_mom_12_1"].gt(0.0)
        & oos_panel["forward_return"].notna()
    ]
    tsmom_hit_pooled = {
        "year": "Pooled",
        "weeks": int(positive_tsmom_oos["week_order"].nunique()),
        "observations": int(len(positive_tsmom_oos)),
        "hit_rate": (
            float(positive_tsmom_oos["forward_return"].gt(0.0).mean())
            if not positive_tsmom_oos.empty
            else np.nan
        ),
    }
    return {
        "cs_annual": cs_annual,
        "cs_pooled": cs_pooled,
        "cs_history": cs_history,
        "ts_annual": ts_annual,
        "ts_pooled": ts_pooled,
        "ts_name_values": ts_name_values,
        "ts_pooled_values": ts_pooled_values,
        "combo_history": combo_history,
        "combo_selected": combo_selected,
        "tsmom_hit": tsmom_hit_rows + [tsmom_hit_pooled],
        "audit": audit_rows,
    }


def _fmt(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return ("%." + str(digits) + "f") % value


def _pct(value: float, digits: int = 1) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return ("%." + str(digits) + "f%%") % (value * 100.0)


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    def clean(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    output = [
        "| " + " | ".join(clean(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend(
        "| " + " | ".join(clean(item) for item in row) + " |" for row in rows
    )
    return "\n".join(output)


def _annual_matrix(
    annual: Mapping[int, Mapping[str, Mapping[str, float]]],
    metric: str,
    formatter,
) -> str:
    rows = []
    for factor in FACTORS:
        rows.append(
            [DISPLAY_NAME[factor]]
            + [formatter(annual[year][factor][metric]) for year in TEST_YEARS]
        )
    return _markdown_table(["Factor"] + [str(year) for year in TEST_YEARS], rows)


def _multiple_testing_rows(
    pooled: Mapping[str, Mapping[str, float]],
    number_of_tests: int,
    annualize: bool,
) -> List[List[object]]:
    normal = NormalDist()
    euler_gamma = 0.5772156649015329
    expected_max_z = (
        (1.0 - euler_gamma) * normal.inv_cdf(1.0 - 1.0 / number_of_tests)
        + euler_gamma
        * normal.inv_cdf(1.0 - 1.0 / (number_of_tests * math.e))
    )
    rows = []
    for factor in sorted(
        FACTORS,
        key=lambda name: pooled[name]["ir"],
        reverse=True,
    ):
        metrics = pooled[factor]
        count = int(metrics["n"])
        scale = math.sqrt(52.0) if annualize else 1.0
        observed = metrics["ir"] * scale if np.isfinite(metrics["ir"]) else np.nan
        hurdle = (
            expected_max_z * scale / math.sqrt(count) if count > 0 else np.nan
        )
        deflated = observed - hurdle if np.isfinite(observed) else np.nan
        z_score = (
            abs(metrics["ir"]) * math.sqrt(count)
            if count > 0 and np.isfinite(metrics["ir"])
            else np.nan
        )
        p_value = (
            math.erfc(z_score / math.sqrt(2.0)) if np.isfinite(z_score) else np.nan
        )
        bonferroni = (
            min(1.0, number_of_tests * p_value) if np.isfinite(p_value) else np.nan
        )
        rows.append(
            [
                DISPLAY_NAME[factor],
                _fmt(observed),
                _fmt(hurdle),
                _fmt(deflated),
                _fmt(bonferroni, 4),
            ]
        )
    return rows


def _write_heatmap(
    annual: Mapping[int, Mapping[str, Mapping[str, float]]],
    title: str,
    path: Path,
) -> None:
    matrix = np.asarray(
        [
            [annual[year][factor]["mean"] for year in TEST_YEARS]
            for factor in FACTORS
        ],
        dtype=float,
    )
    finite = np.abs(matrix[np.isfinite(matrix)])
    limit = max(0.10, float(finite.max()) if finite.size else 0.10)

    figure, axis = plt.subplots(figsize=(12.0, 5.6))
    image = axis.imshow(
        matrix,
        cmap="RdBu_r",
        aspect="auto",
        interpolation="nearest",
        vmin=-limit,
        vmax=limit,
    )
    axis.set_xticks(np.arange(len(TEST_YEARS)))
    axis.set_xticklabels([str(year) for year in TEST_YEARS])
    axis.set_yticks(np.arange(len(FACTORS)))
    axis.set_yticklabels([DISPLAY_NAME[factor] for factor in FACTORS])
    axis.set_xlabel("OOS test year")
    axis.set_ylabel("A priori factor")
    axis.set_title(title)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            label = "N/A" if not np.isfinite(value) else "%.2f" % value
            color = "white" if np.isfinite(value) and abs(value) > 0.58 * limit else "black"
            axis.text(column, row, label, ha="center", va="center", fontsize=8, color=color)
    colorbar = figure.colorbar(image, ax=axis, fraction=0.03, pad=0.03)
    colorbar.set_label("IC mean")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_heatmaps(results: Mapping[str, object]) -> List[Path]:
    paths = [
        PLOT_DIR / "equity_cs_ic_mean_heatmap.png",
        PLOT_DIR / "ts_ic_mean_heatmap.png",
    ]
    _write_heatmap(
        results["cs_annual"],
        "Equity-only cross-sectional weekly Rank IC mean",
        paths[0],
    )
    _write_heatmap(
        results["ts_annual"],
        "Per-ETF time-series IC mean across names",
        paths[1],
    )
    return paths


def build_report(
    panel: pd.DataFrame,
    results: Mapping[str, object],
    source_file_count: int,
) -> str:
    annual = results["cs_annual"]
    pooled = results["cs_pooled"]
    ts_annual = results["ts_annual"]
    ts_pooled = results["ts_pooled"]
    combo_selected = results["combo_selected"]

    pooled_rows = []
    for factor in sorted(FACTORS, key=lambda name: pooled[name]["ir"], reverse=True):
        metrics = pooled[factor]
        pooled_rows.append(
            [
                DISPLAY_NAME[factor],
                int(metrics["n"]),
                _fmt(metrics["mean"]),
                _fmt(metrics["ir"]),
                _pct(metrics["hit_rate"]),
            ]
        )

    ts_pooled_rows = []
    for factor in sorted(FACTORS, key=lambda name: ts_pooled[name]["ir"], reverse=True):
        metrics = ts_pooled[factor]
        ts_pooled_rows.append(
            [
                DISPLAY_NAME[factor],
                int(metrics["n"]),
                _fmt(metrics["mean"]),
                _fmt(metrics["ir"]),
                _pct(metrics["hit_rate"]),
            ]
        )

    audit_rows = [
        [
            row["year"],
            row["train_start"],
            row["last_train_label"],
            row["train_weeks"],
            row["test_start"],
            row["test_end"],
            row["test_weeks"],
        ]
        for row in results["audit"]
    ]

    combo_rows = []
    for year in TEST_YEARS:
        metrics = annual[year]["combo"]
        selected = combo_selected[year]
        if selected:
            selection_text = ", ".join(DISPLAY_NAME[item] for item in selected)
        elif year == TEST_YEARS[0]:
            selection_text = "None (first OOS year)"
        else:
            selection_text = "None (no prior-OOS IC IR > %.2f)" % COMBO_IR_THRESHOLD
        combo_rows.append(
            [
                year,
                selection_text,
                int(metrics["n"]),
                _fmt(metrics["mean"]),
                _fmt(metrics["ir"]),
                _pct(metrics["hit_rate"]),
            ]
        )
    combo_pooled = pooled["combo"]
    combo_rows.append(
        [
            "Pooled",
            "Year-specific, selected before each test year",
            int(combo_pooled["n"]),
            _fmt(combo_pooled["mean"]),
            _fmt(combo_pooled["ir"]),
            _pct(combo_pooled["hit_rate"]),
        ]
    )

    top_factors = sorted(
        FACTORS, key=lambda name: pooled[name]["ir"], reverse=True
    )[:5]
    best_text = ", ".join(
        "%s (IR %s)" % (DISPLAY_NAME[name], _fmt(pooled[name]["ir"]))
        for name in top_factors
    )
    top_ts_factors = sorted(
        FACTORS, key=lambda name: ts_pooled[name]["ir"], reverse=True
    )[:5]
    best_ts_text = ", ".join(
        "%s (IC %s, IR %s)"
        % (
            DISPLAY_NAME[name],
            _fmt(ts_pooled[name]["mean"]),
            _fmt(ts_pooled[name]["ir"]),
        )
        for name in top_ts_factors
    )

    tsmom_hit_rows = [
        [
            row["year"],
            row["weeks"],
            row["observations"],
            _pct(row["hit_rate"]),
        ]
        for row in results["tsmom_hit"]
    ]
    any_combo = any(bool(selected) for selected in combo_selected.values())
    combo_note = (
        "At least one factor crossed the prior-OOS equity-CS IC IR threshold; "
        "each year's membership shown above was frozen before that year's labels."
        if any_combo
        else "No factor crossed the specified prior-OOS equity-CS IC IR threshold, "
        "so the rule produces no combo observations. Forcing a combo or lowering "
        "the threshold after seeing these results would violate the predeclared "
        "selection protocol."
    )

    first_date = panel["signal_date"].min().date().isoformat()
    last_date = panel["signal_date"].max().date().isoformat()
    etf_count = int(panel["code"].nunique())
    equity_count = int(panel.loc[panel["code"].isin(EQUITY_CODES), "code"].nunique())
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        "# ETF factor expanding-window walk-forward",
        "",
        "Generated by `research/factor_walkforward.py` at %s." % generated,
        "",
        "## Protocol and leakage controls",
        "",
        "- Data: %d parquet files; %d ETFs after excluding the standalone "
        "`000300.SS` index; %d equity ETFs in the live `GROWTH` sleeve; weekly "
        "signal coverage %s through %s."
        % (source_file_count, etf_count, equity_count, first_date, last_date),
        "- Signal row: Friday or the last available bar of each ISO week. "
        "Label: close-to-close return from that row to the next ISO week only. "
        "Missing whole weeks are not bridged.",
        "- Equity-CS IC: weekly cross-sectional Spearman correlation using only "
        "the 17-name `GROWTH` equity sleeve, requiring at least %d names. IC IR "
        "is mean weekly IC divided by its weekly standard deviation."
        % MIN_CROSS_SECTION,
        "- TS-IC: within each ETF, Pearson corr(factor at T, next-week return), "
        "requiring at least %d weeks; the reported IC is the mean across ETF "
        "names and its IR uses dispersion across names." % MIN_TS_WEEKS,
        "- Walk-forward: for test year Y, training observations must have their "
        "next-week label strictly before January 1 of Y. Fixed factor formulas "
        "have no cross-sectional fitted coefficients. The residual factor's "
        "120-day time-series OLS ends five trading returns before each signal.",
        "- Combo: equal-weight average of complete equity cross-sectional "
        "percentile ranks. A factor enters only when its pooled equity-CS IC IR "
        "across already completed OOS years exceeds %.2f. TS-IC is not mixed "
        "into this selector, and current-year labels are appended only after "
        "membership is fixed." % COMBO_IR_THRESHOLD,
        "- No month or subperiod, including 2026-07, receives special tuning or "
        "selection treatment.",
        "",
        "A priori factors: `ts_mom_12_1` is close(T-21)/close(T-252)-1, "
        "falling back to close(T-5)/close(T-126)-1 until 252 bars exist; "
        "`term_spread` is the 10-day return minus the 5-day return. "
        "`crowding_points` is the raw live 0-4 score and `residual_mom` is the "
        "existing 120-day OLS residual score; both are retained as predeclared "
        "negative controls. Common-series gold/bond spreads are excluded "
        "because subtracting one value from every name cannot change a "
        "cross-sectional rank.",
        "",
        "## Walk-forward boundary audit",
        "",
        _markdown_table(
            [
                "Test year",
                "Train signal start",
                "Last train label",
                "Train weeks",
                "Test signal start",
                "Test signal end",
                "Labeled test weeks",
            ],
            audit_rows,
        ),
        "",
        "The first OOS year is 2019. Its combo is deliberately absent because "
        "there is no prior OOS evidence available for factor selection.",
        "",
        "## Equity-only cross-sectional IC",
        "",
        "### Pooled OOS results (2019-2026)",
        "",
        _markdown_table(
            ["Factor", "Weeks", "IC mean", "IC IR", "Hit rate"], pooled_rows
        ),
        "",
        "Top pooled equity-CS rows by IC IR: %s." % best_text,
        "",
        "### IC mean by test year",
        "",
        _annual_matrix(annual, "mean", _fmt),
        "",
        "### IC IR by test year",
        "",
        _annual_matrix(annual, "ir", _fmt),
        "",
        "### Positive-IC hit rate by test year",
        "",
        _annual_matrix(annual, "hit_rate", _pct),
        "",
        "![Equity-CS IC heatmap](plots/equity_cs_ic_mean_heatmap.png)",
        "",
        "## Per-ETF time-series IC",
        "",
        "For each ETF and test slice, IC is the Pearson correlation over time "
        "between the factor and the strict next-week return. The pooled table "
        "recomputes each name's correlation over all OOS weeks rather than "
        "averaging annual correlations.",
        "",
        _markdown_table(
            ["Factor", "ETFs", "Mean per-name IC", "Cross-name IR", "Positive-name rate"],
            ts_pooled_rows,
        ),
        "",
        "Top pooled TS rows by cross-name IR: %s." % best_ts_text,
        "",
        "### Mean per-name TS-IC by test year",
        "",
        _annual_matrix(ts_annual, "mean", _fmt),
        "",
        "### Cross-name TS-IC IR by test year",
        "",
        _annual_matrix(ts_annual, "ir", _fmt),
        "",
        "### Positive-name TS-IC rate by test year",
        "",
        _annual_matrix(ts_annual, "hit_rate", _pct),
        "",
        "![TS-IC heatmap](plots/ts_ic_mean_heatmap.png)",
        "",
        "## TSMOM conditional hit rate (equity only)",
        "",
        "This is the fraction of positive next-week returns among equity "
        "ETF-weeks where `ts_mom_12_1 > 0`. It is diagnostic only and never "
        "enters combo selection.",
        "",
        _markdown_table(
            ["Year", "Weeks with signals", "Positive-signal ETF-weeks", "Hit rate"],
            tsmom_hit_rows,
        ),
        "",
        "## Strictly lagged OOS combo",
        "",
        _markdown_table(
            ["Year", "Factors fixed before year", "Weeks", "IC mean", "IC IR", "Hit rate"],
            combo_rows,
        ),
        "",
        combo_note,
        "",
        "## Multiple-testing adjustment",
        "",
        "There are N=%d predeclared factor tests. For equity-CS, the table "
        "reports annualized IC Sharpe (`sqrt(52) * IC IR`), an expected-best "
        "null hurdle for N independent Gaussian tests, their difference, and a "
        "two-sided normal p-value multiplied by N (Bonferroni)." % len(FACTORS),
        "",
        _markdown_table(
            [
                "Factor",
                "Annualized IC Sharpe",
                "N-test null hurdle",
                "Deflated score",
                "Bonferroni p",
            ],
            _multiple_testing_rows(pooled, len(FACTORS), annualize=True),
        ),
        "",
        "For TS-IC, temporal annualization is inappropriate because the "
        "observations summarized by the IR are per-name correlations. The same "
        "N-test adjustment is therefore shown in raw cross-name IC IR units.",
        "",
        _markdown_table(
            [
                "Factor",
                "Cross-name IC IR",
                "N-test null hurdle",
                "Deflated IR",
                "Bonferroni p",
            ],
            _multiple_testing_rows(ts_pooled, len(FACTORS), annualize=False),
        ),
        "",
        "These simple corrections treat weekly ICs or ETF-level ICs as "
        "independent for the expected-maximum hurdle, which is only an "
        "approximation. Bonferroni remains a conservative family-wise screen "
        "under dependence. Neither adjustment removes ETF-universe survivorship "
        "bias.",
        "",
        "## Interpretation limits",
        "",
        "- These are predictive cross-sectional and per-name diagnostics, not a "
        "traded portfolio backtest; turnover, costs, capacity, and constraints "
        "are not included.",
        "- The cache contains today's known ETF universe. ETFs enter only after "
        "their own history begins, but delisted or unavailable historical ETFs "
        "may be absent.",
        "- 2026 is a partial year ending at the cache boundary. Its final week "
        "has no next-week label and is automatically excluded.",
        "",
    ]
    return "\n".join(sections)


def run() -> Dict[str, object]:
    daily = load_daily_panel()
    factor_panel = build_factor_panel(daily)
    results = run_walk_forward(factor_panel)
    source_count = len(list(CACHE_DIR.glob("*.parquet")))
    plot_paths = write_heatmaps(results)
    report = build_report(factor_panel, results, source_count)
    REPORT_PATH.write_text(report, encoding="utf-8")

    cs_ranked = sorted(
        FACTORS,
        key=lambda name: results["cs_pooled"][name]["ir"],
        reverse=True,
    )
    ts_ranked = sorted(
        FACTORS,
        key=lambda name: results["ts_pooled"][name]["ir"],
        reverse=True,
    )
    print("report=%s" % REPORT_PATH)
    print("plots=%s" % ", ".join(str(path) for path in plot_paths))
    print(
        "panel=%d ETF-weeks, ETFs=%d, equities=%d, OOS years=%d-%d"
        % (
            len(factor_panel),
            factor_panel["code"].nunique(),
            factor_panel.loc[
                factor_panel["code"].isin(EQUITY_CODES), "code"
            ].nunique(),
            TEST_YEARS[0],
            TEST_YEARS[-1],
        )
    )
    print("best pooled equity-CS factors:")
    for factor in cs_ranked[:5]:
        metrics = results["cs_pooled"][factor]
        print(
            "  %-20s IC=% .4f IR=% .3f hit=%5.1f%% n=%d"
            % (
                DISPLAY_NAME[factor],
                metrics["mean"],
                metrics["ir"],
                metrics["hit_rate"] * 100.0,
                metrics["n"],
            )
        )
    print("best pooled TS-IC factors:")
    for factor in ts_ranked[:5]:
        metrics = results["ts_pooled"][factor]
        print(
            "  %-20s IC=% .4f IR=% .3f positive_names=%5.1f%% n=%d"
            % (
                DISPLAY_NAME[factor],
                metrics["mean"],
                metrics["ir"],
                metrics["hit_rate"] * 100.0,
                metrics["n"],
            )
        )
    combo = results["cs_pooled"]["combo"]
    print(
        "strict lagged combo: IC=% .4f IR=% .3f hit=%5.1f%% n=%d"
        % (
            combo["mean"],
            combo["ir"],
            combo["hit_rate"] * 100.0,
            combo["n"],
        )
    )
    return results


if __name__ == "__main__":
    run()
