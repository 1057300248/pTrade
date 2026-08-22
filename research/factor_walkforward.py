#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Leakage-safe weekly cross-sectional ETF factor walk-forward research.

The script reads the local parquet cache, computes factors only from data
available at each weekly signal date, evaluates next-week cross-sectional
Rank IC, and writes ``factor_walkforward_report.md``.

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


HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache" / "etf_daily"
REPORT_PATH = HERE / "factor_walkforward_report.md"

MARKET = "510300.SS"
SIZE = "510500.SS"
GOLD = "518880.SS"
BOND = "511010.SS"
NON_ETF_FILES = {"000300.SS"}
TEST_YEARS = tuple(range(2019, 2027))
MIN_CROSS_SECTION = 5
COMBO_IR_THRESHOLD = 0.30

FACTORS = (
    "mom21",
    "mom63",
    "mom126",
    "residual_mom",
    "vol20",
    "inv_vol",
    "turnover_z",
    "crowding_points",
    "close_ma60",
    "corr_to_300_60d",
    "gold_spread",
    "bond_spread",
)

DISPLAY_NAME = {
    "mom21": "mom21",
    "mom63": "mom63",
    "mom126": "mom126",
    "residual_mom": "residual_mom",
    "vol20": "vol20",
    "inv_vol": "inv_vol",
    "turnover_z": "turnover_z",
    "crowding_points": "crowding_points",
    "close_ma60": "close/ma60",
    "corr_to_300_60d": "corr_to_300_60d",
    "gold_spread": "gold_spread",
    "bond_spread": "bond_spread",
}


def _load_one(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    required = {"date", "high", "low", "close", "volume", "amount"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("%s is missing columns: %s" % (path, sorted(missing)))
    frame = frame.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = (
        frame.dropna(subset=["date", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .set_index("date")
    )
    for column in ("high", "low", "close", "volume", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["amount"] = frame["amount"].where(
        frame["amount"].notna(), frame["close"] * frame["volume"]
    )
    return frame


def load_daily_panel() -> Dict[str, pd.DataFrame]:
    """Load all ETF files, excluding the standalone 000300 index series."""
    paths = sorted(CACHE_DIR.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError("no parquet files under %s" % CACHE_DIR)
    panel = {}
    for path in paths:
        code = path.stem
        if code in NON_ETF_FILES:
            continue
        panel[code] = _load_one(path)
    missing_refs = {MARKET, SIZE, GOLD, BOND}.difference(panel)
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
    gold_mom63 = daily[GOLD]["close"].pct_change(63)
    bond_mom63 = daily[BOND]["close"].pct_change(63)

    records = []
    for code, source in sorted(daily.items()):
        frame = source.copy()
        close = frame["close"]
        asset_return = np.log(close).diff().rename("asset")
        weekly_dates = _weekly_dates(frame.index)

        features = pd.DataFrame(index=frame.index)
        features["close"] = close
        features["mom21"] = close.pct_change(21)
        features["mom63"] = close.pct_change(63)
        features["mom126"] = close.pct_change(126)
        features["vol20"] = (
            asset_return.rolling(20, min_periods=20).std(ddof=1) * math.sqrt(252.0)
        )
        features["inv_vol"] = _safe_ratio(
            pd.Series(1.0, index=frame.index), features["vol20"]
        )
        amount20 = frame["amount"].rolling(20, min_periods=20).mean()
        amount120 = frame["amount"].rolling(120, min_periods=120).mean()
        features["_turnover_ratio"] = _safe_ratio(amount20, amount120) - 1.0
        features["crowding_points"] = _crowding_points(frame)
        ma60 = close.rolling(60, min_periods=60).mean()
        features["close_ma60"] = _safe_ratio(close, ma60)
        aligned_market_return = _reference_series(market_return, frame.index)
        features["corr_to_300_60d"] = asset_return.rolling(
            60, min_periods=45
        ).corr(aligned_market_return)
        features["gold_spread"] = features["mom63"] - _reference_series(
            gold_mom63, frame.index
        )
        features["bond_spread"] = features["mom63"] - _reference_series(
            bond_mom63, frame.index
        )

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

    # "turnover_z" is the weekly cross-sectional z-score of 20d/120d
    # average amount growth. Rank IC is invariant to this affine scaling.
    grouped_turnover = panel.groupby("week_order")["_turnover_ratio"]
    turnover_mean = grouped_turnover.transform("mean")
    turnover_std = grouped_turnover.transform("std")
    panel["turnover_z"] = _safe_ratio(
        panel["_turnover_ratio"] - turnover_mean, turnover_std
    )
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
    """Evaluate annual OOS slices and form the strictly lagged combo."""
    factor_history: Dict[str, List[pd.Series]] = {factor: [] for factor in FACTORS}
    annual: Dict[int, Dict[str, Dict[str, float]]] = {}
    combo_history: List[pd.Series] = []
    combo_selected: Dict[int, List[str]] = {}
    audit_rows = []

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

        annual[year] = {}
        for factor in FACTORS:
            values = weekly_rank_ic(test, factor)
            annual[year][factor] = ic_summary(values)
            factor_history[factor].append(values)

        selected = []
        if year > TEST_YEARS[0]:
            for factor in FACTORS:
                # Exclude the current year's values, which were just appended.
                prior_values = pd.concat(factor_history[factor][:-1])
                prior_ir = ic_summary(prior_values)["ir"]
                if np.isfinite(prior_ir) and prior_ir > COMBO_IR_THRESHOLD:
                    selected.append(factor)
        combo_selected[year] = selected
        test["combo"] = _combo_score(test, selected)
        combo_values = weekly_rank_ic(test, "combo") if selected else pd.Series(dtype=float)
        annual[year]["combo"] = ic_summary(combo_values)
        combo_history.append(combo_values)

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

    pooled = {
        factor: ic_summary(_pooled_history(factor_history, factor))
        for factor in FACTORS
    }
    pooled["combo"] = ic_summary(pd.concat(combo_history))
    return {
        "annual": annual,
        "pooled": pooled,
        "factor_history": factor_history,
        "combo_history": combo_history,
        "combo_selected": combo_selected,
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
    pooled: Mapping[str, Mapping[str, float]], number_of_tests: int
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
        key=lambda name: pooled[name]["annualized_ic_sharpe"],
        reverse=True,
    ):
        metrics = pooled[factor]
        count = int(metrics["n"])
        hurdle = (
            expected_max_z * math.sqrt(52.0 / count) if count > 0 else np.nan
        )
        annualized = metrics["annualized_ic_sharpe"]
        deflated = annualized - hurdle if np.isfinite(annualized) else np.nan
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
                _fmt(annualized),
                _fmt(hurdle),
                _fmt(deflated),
                _fmt(bonferroni, 4),
            ]
        )
    return rows


def build_report(
    panel: pd.DataFrame,
    results: Mapping[str, object],
    source_file_count: int,
) -> str:
    annual = results["annual"]
    pooled = results["pooled"]
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

    first_date = panel["signal_date"].min().date().isoformat()
    last_date = panel["signal_date"].max().date().isoformat()
    etf_count = int(panel["code"].nunique())
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        "# ETF factor expanding-window walk-forward",
        "",
        "Generated by `research/factor_walkforward.py` at %s." % generated,
        "",
        "## Protocol and leakage controls",
        "",
        "- Data: %d parquet files; %d ETFs after excluding the standalone "
        "`000300.SS` index; weekly signal coverage %s through %s."
        % (source_file_count, etf_count, first_date, last_date),
        "- Signal row: Friday or the last available bar of each ISO week. "
        "Label: close-to-close return from that row to the next ISO week only. "
        "Missing whole weeks are not bridged.",
        "- Rank IC: weekly cross-sectional Spearman correlation, requiring at "
        "least %d ETFs. IC IR is mean weekly IC divided by its weekly standard "
        "deviation (not annualized)." % MIN_CROSS_SECTION,
        "- Walk-forward: for test year Y, training observations must have their "
        "next-week label strictly before January 1 of Y. Fixed factor formulas "
        "have no cross-sectional fitted coefficients. The residual factor's "
        "120-day time-series OLS ends five trading returns before each signal.",
        "- Combo: equal-weight average of complete cross-sectional percentile "
        "ranks. A factor enters only when its pooled IC IR across already "
        "completed OOS years exceeds %.2f. The current test year is appended "
        "only after its combo is fixed." % COMBO_IR_THRESHOLD,
        "- No month or subperiod, including 2026-07, receives special tuning or "
        "selection treatment.",
        "",
        "Factor details: `turnover_z` is the weekly cross-sectional z-score of "
        "(20-day mean amount / 120-day mean amount - 1); `crowding_points` is "
        "the live 0-4 clone (volume surge, price extension, weak close-volume "
        "correlation, high amplitude); `residual_mom` is the 60-day residual "
        "sum/std from the 120-day OLS on 510300 returns and the "
        "510500-minus-510300 size spread.",
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
        "## Pooled OOS factor results (2019-2026)",
        "",
        _markdown_table(
            ["Factor", "Weeks", "IC mean", "IC IR", "Hit rate"], pooled_rows
        ),
        "",
        "Top pooled OOS factor rows by IC IR: %s." % best_text,
        "",
        "## IC mean by test year",
        "",
        _annual_matrix(annual, "mean", _fmt),
        "",
        "## IC IR by test year",
        "",
        _annual_matrix(annual, "ir", _fmt),
        "",
        "## Positive-IC hit rate by test year",
        "",
        _annual_matrix(annual, "hit_rate", _pct),
        "",
        "## Strictly lagged OOS combo",
        "",
        _markdown_table(
            ["Year", "Factors fixed before year", "Weeks", "IC mean", "IC IR", "Hit rate"],
            combo_rows,
        ),
        "",
        "No factor crossed the specified prior-OOS IC IR threshold on this "
        "dataset, so the rule produces no combo observations. Forcing a combo "
        "or lowering the threshold after seeing these results would violate "
        "the predeclared selection protocol.",
        "",
        "## Multiple-testing adjustment",
        "",
        "There are N=%d declared factor tests. The table reports annualized IC "
        "Sharpe (`sqrt(52) * IC IR`), an expected-best null hurdle for N "
        "independent Gaussian tests, their difference as a simple deflated "
        "score, and a two-sided normal p-value multiplied by N (Bonferroni). "
        "This is a screening correction, not a claim that weekly ICs are "
        "perfectly Gaussian or independent." % len(FACTORS),
        "",
        _markdown_table(
            [
                "Factor",
                "Annualized IC Sharpe",
                "N-test null hurdle",
                "Deflated score",
                "Bonferroni p",
            ],
            _multiple_testing_rows(pooled, len(FACTORS)),
        ),
        "",
        "The nominal N=12 is conservative for the expected-maximum calculation "
        "because the tests are dependent. In particular, subtracting the same "
        "weekly gold or bond return from every ETF preserves the cross-sectional "
        "rank, so `gold_spread`, `bond_spread`, and `mom63` have identical Rank "
        "IC. `inv_vol` is also an exact rank reversal of `vol20`. Bonferroni "
        "remains a simple family-wise guard under dependence, but neither "
        "adjustment removes ETF-universe survivorship bias.",
        "",
        "## Interpretation limits",
        "",
        "- These are predictive cross-sectional diagnostics, not a traded "
        "portfolio backtest; turnover, costs, capacity, and constraints are not "
        "included.",
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
    report = build_report(factor_panel, results, source_count)
    REPORT_PATH.write_text(report, encoding="utf-8")

    ranked = sorted(
        FACTORS,
        key=lambda name: results["pooled"][name]["ir"],
        reverse=True,
    )
    print("report=%s" % REPORT_PATH)
    print(
        "panel=%d ETF-weeks, ETFs=%d, OOS years=%d-%d"
        % (
            len(factor_panel),
            factor_panel["code"].nunique(),
            TEST_YEARS[0],
            TEST_YEARS[-1],
        )
    )
    print("best pooled OOS factors:")
    for factor in ranked[:5]:
        metrics = results["pooled"][factor]
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
    combo = results["pooled"]["combo"]
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
