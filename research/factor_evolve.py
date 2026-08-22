#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic seed composition under the repository anti-overfit protocol.

The formula grammar and all 30 candidates are declared below before evaluation.
No OOS result changes a lookback, formula, sign, threshold, or weight.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, List, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from etf_panel import load_panel
except ImportError:
    from research.etf_panel import load_panel

from ptrade_rmdc_etf import GROWTH as LIVE_GROWTH


CACHE_DIR = HERE / "cache" / "etf_daily"
REPORT_PATH = HERE / "factor_evolve.md"
PLOT_PATH = HERE / "plots" / "factor_evolve_ic.png"

GROWTH = tuple(LIVE_GROWTH)
CONFIRM_CODES = ("510300.SS", "159915.SZ", "513100.SS", "518880.SS")
MARKET = "510300.SS"
GOLD = "518880.SS"
TRAIN_START = pd.Timestamp("2018-01-01")
FREEZE_DATE = pd.Timestamp("2022-01-01")
PROMOTION_END = pd.Timestamp("2026-01-01")
OOS_END = pd.Timestamp("2027-01-01")
OOS_YEARS = tuple(range(2022, 2027))
MIN_CROSS_SECTION = 5
MIN_TS_WEEKS = 12
IR_THRESHOLD = 0.30
MAX_LIVE_FACTORS = 4
DECLARED_N = 30

SEEDS = (
    "ts_mom_12_1",
    "month_gate_21d",
    "term_spread_10_5",
    "crowding_points_neg",
    "inv_vol20",
    "close_ma120",
    "gold_vs_300_relative",
)

COMPOSITIONS = (
    "mom_month_sum",
    "mom_term_sum",
    "mom_invvol_sum",
    "mom_trend_sum",
    "mom_crowding_sum",
    "term_month_sum",
    "term_invvol_sum",
    "term_trend_sum",
    "trend_invvol_sum",
    "trend_month_sum",
    "defensive_sum",
    "momentum_trio",
    "quality_momentum",
    "decrowded_momentum",
    "balanced_term_trend",
    "gold_invvol_sum",
    "gold_trend_sum",
    "gold_mom_diff",
    "mom_rank_resid_300",
    "term_rank_resid_300",
    "trend_rank_resid_300",
    "invvol_rank_resid_300",
    "composite_rank_resid_300",
)

FORMULAS = SEEDS + COMPOSITIONS
if len(FORMULAS) != DECLARED_N or len(set(FORMULAS)) != DECLARED_N:
    raise AssertionError("exactly 30 unique formulas must be declared")

FORMULA_DEFINITIONS = {
    "ts_mom_12_1": "close(T-21)/close(T-252)-1; 126d/5d fallback",
    "month_gate_21d": "1 when 21d return > 0, else 0",
    "term_spread_10_5": "10d return minus 5d return (a priori 国泰海通 seed)",
    "crowding_points_neg": "negative of the live 0-4 crowding score",
    "inv_vol20": "inverse 20d annualized log-return volatility",
    "close_ma120": "close / 120d moving average - 1",
    "gold_vs_300_relative": "63d gold return minus 63d 510300 return",
    "mom_month_sum": "rank(mom) + rank(month gate)",
    "mom_term_sum": "rank(mom) + rank(term spread)",
    "mom_invvol_sum": "rank(mom) + rank(inv vol)",
    "mom_trend_sum": "rank(mom) + rank(close/MA120)",
    "mom_crowding_sum": "rank(mom) + rank(negative crowding)",
    "term_month_sum": "rank(term spread) + rank(month gate)",
    "term_invvol_sum": "rank(term spread) + rank(inv vol)",
    "term_trend_sum": "rank(term spread) + rank(close/MA120)",
    "trend_invvol_sum": "rank(close/MA120) + rank(inv vol)",
    "trend_month_sum": "rank(close/MA120) + rank(month gate)",
    "defensive_sum": "rank(inv vol) + rank(negative crowding)",
    "momentum_trio": "rank(mom) + rank(month gate) + rank(term spread)",
    "quality_momentum": "rank(mom) + rank(close/MA120) + rank(inv vol)",
    "decrowded_momentum": "rank(mom) + rank(negative crowding) + rank(inv vol)",
    "balanced_term_trend": "rank(term) + rank(trend) + rank(negative crowding)",
    "gold_invvol_sum": "rank(gold-vs-300) + rank(inv vol)",
    "gold_trend_sum": "rank(gold-vs-300) + rank(close/MA120)",
    "gold_mom_diff": "rank(mom) - rank(gold-vs-300)",
    "mom_rank_resid_300": "rank(mom ETF) - rank(mom 510300)",
    "term_rank_resid_300": "rank(term ETF) - rank(term 510300)",
    "trend_rank_resid_300": "rank(trend ETF) - rank(trend 510300)",
    "invvol_rank_resid_300": "rank(inv vol ETF) - rank(inv vol 510300)",
    "composite_rank_resid_300": (
        "rank(mom)+rank(term)+rank(trend), minus same 510300 ranks"
    ),
}


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0.0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def load_daily() -> Dict[str, pd.DataFrame]:
    codes = tuple(dict.fromkeys(GROWTH + CONFIRM_CODES))
    arrays = load_panel(CACHE_DIR, codes=codes)
    return {
        code: pd.DataFrame(
            {
                column: bars[column]
                for column in ("high", "low", "close", "volume", "amount")
            },
            index=pd.DatetimeIndex(bars["dates"], name="date"),
        )
        for code, bars in arrays.items()
    }


def _weekly_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    return pd.DatetimeIndex(
        dates.groupby(index.to_period("W-SUN"), sort=True).last().to_numpy()
    )


def _crowding_points(frame: pd.DataFrame) -> pd.Series:
    close = frame["close"]
    volume = frame["volume"]
    volume_ratio = _safe_ratio(
        volume.rolling(20, min_periods=20).mean(),
        volume.rolling(60, min_periods=60).mean(),
    )
    ma60 = close.rolling(60, min_periods=60).mean()
    close_volume_corr = close.rolling(20, min_periods=20).corr(volume)
    amplitude = _safe_ratio(frame["high"] - frame["low"], close.shift(1))
    points = (
        (volume_ratio > 2.0).astype(float)
        + (_safe_ratio(close, ma60) - 1.0 > 0.15).astype(float)
        + (close_volume_corr < 0.10).astype(float)
        + (amplitude.rolling(20, min_periods=20).mean() > 0.04).astype(float)
    )
    return points.where(close.rolling(61, min_periods=61).count() >= 61)


def _seed_frame(
    frame: pd.DataFrame, gold_relative: pd.Series
) -> pd.DataFrame:
    close = frame["close"]
    log_return = np.log(close).diff()
    ret5 = close.pct_change(5)
    ret10 = close.pct_change(10)
    ret21 = close.pct_change(21)
    primary_mom = _safe_ratio(close.shift(21), close.shift(252)) - 1.0
    fallback_mom = _safe_ratio(close.shift(5), close.shift(126)) - 1.0
    vol20 = log_return.rolling(20, min_periods=20).std(ddof=1) * math.sqrt(252.0)

    seeds = pd.DataFrame(index=frame.index)
    seeds["close"] = close
    seeds["ts_mom_12_1"] = primary_mom.combine_first(fallback_mom)
    seeds["month_gate_21d"] = ret21.gt(0.0).astype(float).where(ret21.notna())
    seeds["term_spread_10_5"] = ret10 - ret5
    seeds["crowding_points_neg"] = -_crowding_points(frame)
    seeds["inv_vol20"] = _safe_ratio(pd.Series(1.0, index=frame.index), vol20)
    seeds["close_ma120"] = (
        _safe_ratio(close, close.rolling(120, min_periods=120).mean()) - 1.0
    )
    seeds["gold_vs_300_relative"] = gold_relative.reindex(frame.index)
    return seeds


def _causal_ranks(panel: pd.DataFrame) -> pd.DataFrame:
    output = panel.sort_values(["code", "signal_date"]).copy()

    # Use one macro observation per week for every ETF. This prevents a stale
    # individual ETF bar from giving the common gold-vs-300 seed artificial
    # cross-sectional dispersion.
    benchmark_gold_value = (
        output.loc[
            output["code"].eq(MARKET),
            ["week_order", "gold_vs_300_relative"],
        ]
        .drop_duplicates("week_order")
        .set_index("week_order")["gold_vs_300_relative"]
    )
    output["gold_vs_300_relative"] = output["week_order"].map(
        benchmark_gold_value
    )

    for seed in SEEDS:
        ranked = (
            output.groupby("code", sort=False)[seed]
            .expanding(min_periods=MIN_TS_WEEKS)
            .rank(method="average", pct=True)
        )
        ranked.index = ranked.index.droplevel(0)
        output["rank_" + seed] = ranked.reindex(output.index)

    # The gold seed is a common macro series. Use one benchmark history so ETF
    # inception dates cannot create artificial cross-sectional rank variation.
    benchmark_gold_rank = (
        output.loc[
            output["code"].eq(MARKET),
            ["week_order", "rank_gold_vs_300_relative"],
        ]
        .drop_duplicates("week_order")
        .set_index("week_order")["rank_gold_vs_300_relative"]
    )
    output["rank_gold_vs_300_relative"] = output["week_order"].map(
        benchmark_gold_rank
    )
    return output.sort_index()


def _compose(panel: pd.DataFrame) -> pd.DataFrame:
    output = panel.copy()
    mom = output["rank_ts_mom_12_1"]
    month = output["rank_month_gate_21d"]
    term = output["rank_term_spread_10_5"]
    crowd = output["rank_crowding_points_neg"]
    invvol = output["rank_inv_vol20"]
    trend = output["rank_close_ma120"]
    gold = output["rank_gold_vs_300_relative"]

    output["mom_month_sum"] = mom + month
    output["mom_term_sum"] = mom + term
    output["mom_invvol_sum"] = mom + invvol
    output["mom_trend_sum"] = mom + trend
    output["mom_crowding_sum"] = mom + crowd
    output["term_month_sum"] = term + month
    output["term_invvol_sum"] = term + invvol
    output["term_trend_sum"] = term + trend
    output["trend_invvol_sum"] = trend + invvol
    output["trend_month_sum"] = trend + month
    output["defensive_sum"] = invvol + crowd
    output["momentum_trio"] = mom + month + term
    output["quality_momentum"] = mom + trend + invvol
    output["decrowded_momentum"] = mom + crowd + invvol
    output["balanced_term_trend"] = term + trend + crowd
    output["gold_invvol_sum"] = gold + invvol
    output["gold_trend_sum"] = gold + trend
    output["gold_mom_diff"] = mom - gold

    benchmark = output.loc[
        output["code"].eq(MARKET),
        [
            "week_order",
            "rank_ts_mom_12_1",
            "rank_term_spread_10_5",
            "rank_close_ma120",
            "rank_inv_vol20",
        ],
    ].drop_duplicates("week_order").set_index("week_order")
    bench_mom = output["week_order"].map(benchmark["rank_ts_mom_12_1"])
    bench_term = output["week_order"].map(benchmark["rank_term_spread_10_5"])
    bench_trend = output["week_order"].map(benchmark["rank_close_ma120"])
    bench_invvol = output["week_order"].map(benchmark["rank_inv_vol20"])
    output["mom_rank_resid_300"] = mom - bench_mom
    output["term_rank_resid_300"] = term - bench_term
    output["trend_rank_resid_300"] = trend - bench_trend
    output["invvol_rank_resid_300"] = invvol - bench_invvol
    output["composite_rank_resid_300"] = (
        mom + term + trend - bench_mom - bench_term - bench_trend
    )
    return output


def build_panel(daily: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    gold_ret63 = daily[GOLD]["close"].pct_change(63)
    market_ret63 = daily[MARKET]["close"].pct_change(63)
    gold_relative = gold_ret63 - market_ret63
    rows = []
    for code, frame in daily.items():
        seeds = _seed_frame(frame, gold_relative)
        weekly_dates = _weekly_dates(frame.index)
        weekly = seeds.loc[weekly_dates].copy()
        weekly["code"] = code
        weekly["signal_date"] = weekly.index
        periods = weekly.index.to_period("W-SUN")
        weekly["week_order"] = np.asarray([period.ordinal for period in periods])
        is_next_week = weekly["week_order"].shift(-1).eq(
            weekly["week_order"] + 1
        )
        weekly["forward_return"] = (
            weekly["close"].shift(-1) / weekly["close"] - 1.0
        ).where(is_next_week)
        weekly["target_date"] = pd.Series(
            weekly.index, index=weekly.index
        ).shift(-1).where(is_next_week)
        rows.append(weekly.reset_index(drop=True))
    panel = pd.concat(rows, ignore_index=True, sort=False)
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    panel["target_date"] = pd.to_datetime(panel["target_date"])
    return _compose(_causal_ranks(panel))


def weekly_rank_ic(frame: pd.DataFrame, formula: str) -> pd.Series:
    observations = {}
    equity = frame.loc[frame["code"].isin(GROWTH)]
    for week, group in equity.groupby("week_order", sort=True):
        pair = (
            group.loc[:, [formula, "forward_return"]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if len(pair) < MIN_CROSS_SECTION:
            continue
        if pair[formula].nunique() < 2 or pair["forward_return"].nunique() < 2:
            continue
        ranks = pair.rank(method="average")
        value = ranks[formula].corr(ranks["forward_return"])
        if np.isfinite(value):
            observations[int(week)] = float(value)
    return pd.Series(observations, dtype=float, name=formula).sort_index()


def per_name_ts_ic(
    frame: pd.DataFrame, formula: str, codes: Sequence[str]
) -> pd.Series:
    observations = {}
    universe = frame.loc[frame["code"].isin(codes)]
    for code, group in universe.groupby("code", sort=True):
        pair = (
            group.loc[:, [formula, "forward_return"]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if len(pair) < MIN_TS_WEEKS:
            continue
        if pair[formula].nunique() < 2 or pair["forward_return"].nunique() < 2:
            continue
        value = pair[formula].corr(pair["forward_return"])
        if np.isfinite(value):
            observations[str(code)] = float(value)
    return pd.Series(observations, dtype=float, name=formula).sort_index()


def summary(values: Iterable[float]) -> Dict[str, float]:
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    count = int(len(series))
    if count == 0:
        return {"n": 0, "mean": np.nan, "ir": np.nan, "hit_rate": np.nan}
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
    }


def adjusted_stats(metrics: Mapping[str, float]) -> Dict[str, float]:
    normal = NormalDist()
    gamma = 0.5772156649015329
    expected_max_z = (
        (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / DECLARED_N)
        + gamma * normal.inv_cdf(1.0 - 1.0 / (DECLARED_N * math.e))
    )
    count = int(metrics["n"])
    hurdle = expected_max_z / math.sqrt(count) if count > 0 else np.nan
    ir = metrics["ir"]
    deflated = ir - hurdle if np.isfinite(ir) else np.nan
    z_score = abs(ir) * math.sqrt(count) if count and np.isfinite(ir) else np.nan
    p_value = (
        math.erfc(z_score / math.sqrt(2.0)) if np.isfinite(z_score) else np.nan
    )
    return {
        "hurdle": hurdle,
        "deflated": deflated,
        "bonferroni_p": (
            min(1.0, DECLARED_N * p_value) if np.isfinite(p_value) else np.nan
        ),
    }


def evaluate(panel: pd.DataFrame) -> Dict[str, object]:
    training = panel.loc[
        (panel["signal_date"] >= TRAIN_START)
        & (panel["target_date"] < FREEZE_DATE)
    ]
    if training.empty or not bool((training["target_date"] < FREEZE_DATE).all()):
        raise AssertionError("invalid frozen training boundary")

    annual = {}
    annual_series = {}
    for year in OOS_YEARS:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year + 1, month=1, day=1)
        test = panel.loc[
            (panel["signal_date"] >= start) & (panel["signal_date"] < end)
        ]
        annual[year] = {}
        annual_series[year] = {}
        for formula in FORMULAS:
            values = weekly_rank_ic(test, formula)
            annual_series[year][formula] = values
            annual[year][formula] = summary(values)

    promotion_panel = panel.loc[
        (panel["signal_date"] >= FREEZE_DATE)
        & (panel["signal_date"] < PROMOTION_END)
    ]
    full_oos_panel = panel.loc[
        (panel["signal_date"] >= FREEZE_DATE)
        & (panel["signal_date"] < OOS_END)
    ]
    prior_main_values = {
        formula: weekly_rank_ic(promotion_panel, formula) for formula in FORMULAS
    }
    prior_confirm_values = {
        formula: per_name_ts_ic(promotion_panel, formula, CONFIRM_CODES)
        for formula in FORMULAS
    }
    full_main_values = {
        formula: weekly_rank_ic(full_oos_panel, formula) for formula in FORMULAS
    }
    full_confirm_values = {
        formula: per_name_ts_ic(full_oos_panel, formula, CONFIRM_CODES)
        for formula in FORMULAS
    }
    prior_main = {formula: summary(prior_main_values[formula]) for formula in FORMULAS}
    prior_confirm = {
        formula: summary(prior_confirm_values[formula]) for formula in FORMULAS
    }
    full_main = {formula: summary(full_main_values[formula]) for formula in FORMULAS}
    full_confirm = {
        formula: summary(full_confirm_values[formula]) for formula in FORMULAS
    }
    prior_main_adjusted = {
        formula: adjusted_stats(prior_main[formula]) for formula in FORMULAS
    }
    prior_confirm_adjusted = {
        formula: adjusted_stats(prior_confirm[formula]) for formula in FORMULAS
    }

    promoted = [
        formula
        for formula in FORMULAS
        if np.isfinite(prior_main[formula]["ir"])
        and prior_main[formula]["ir"] > IR_THRESHOLD
        and np.isfinite(prior_confirm[formula]["ir"])
        and prior_confirm[formula]["ir"] > IR_THRESHOLD
        and prior_main_adjusted[formula]["deflated"] > 0.0
        and prior_confirm_adjusted[formula]["deflated"] > 0.0
    ]
    promoted.sort(key=lambda formula: prior_main[formula]["ir"], reverse=True)
    promoted = promoted[:MAX_LIVE_FACTORS]
    return {
        "annual": annual,
        "annual_series": annual_series,
        "prior_main": prior_main,
        "prior_confirm": prior_confirm,
        "prior_main_adjusted": prior_main_adjusted,
        "prior_confirm_adjusted": prior_confirm_adjusted,
        "full_main": full_main,
        "full_confirm": full_confirm,
        "promoted": promoted,
        "training_rows": int(len(training)),
        "training_last_label": training["target_date"].max(),
    }


def _fmt(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return ("%." + str(digits) + "f") % value


def _pct(value: float) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return "%.1f%%" % (100.0 * value)


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    def clean(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(clean(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(clean(value) for value in row) + " |" for row in rows
    )
    return "\n".join(lines)


def write_plot(results: Mapping[str, object]) -> None:
    annual = results["annual"]
    matrix = np.asarray(
        [
            [annual[year][formula]["mean"] for year in OOS_YEARS]
            for formula in FORMULAS
        ],
        dtype=float,
    )
    finite = np.abs(matrix[np.isfinite(matrix)])
    limit = max(0.10, float(finite.max()) if finite.size else 0.10)
    figure, axis = plt.subplots(figsize=(11.5, 12.5))
    image = axis.imshow(
        matrix,
        cmap="RdBu_r",
        aspect="auto",
        interpolation="nearest",
        vmin=-limit,
        vmax=limit,
    )
    axis.set_xticks(np.arange(len(OOS_YEARS)))
    axis.set_xticklabels([str(year) for year in OOS_YEARS])
    axis.set_yticks(np.arange(len(FORMULAS)))
    axis.set_yticklabels(FORMULAS, fontsize=7)
    axis.set_xlabel("Strict OOS calendar year")
    axis.set_ylabel("Frozen formula")
    axis.set_title("Equity GROWTH cross-sectional Rank IC mean (N=30 declared)")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            text = "N/A" if not np.isfinite(value) else "%.2f" % value
            color = "white" if np.isfinite(value) and abs(value) > 0.60 * limit else "black"
            axis.text(column, row, text, ha="center", va="center", fontsize=6, color=color)
    colorbar = figure.colorbar(image, ax=axis, fraction=0.025, pad=0.025)
    colorbar.set_label("Weekly Rank IC mean")
    figure.tight_layout()
    PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_PATH, dpi=180, bbox_inches="tight")
    plt.close(figure)


def build_report(results: Mapping[str, object]) -> str:
    prior_main = results["prior_main"]
    prior_confirm = results["prior_confirm"]
    main_adjusted = results["prior_main_adjusted"]
    confirm_adjusted = results["prior_confirm_adjusted"]
    full_main = results["full_main"]
    full_confirm = results["full_confirm"]
    promoted = results["promoted"]

    rows = []
    for formula in sorted(
        FORMULAS,
        key=lambda name: (
            prior_main[name]["ir"]
            if np.isfinite(prior_main[name]["ir"])
            else -np.inf
        ),
        reverse=True,
    ):
        main = prior_main[formula]
        confirm = prior_confirm[formula]
        rows.append(
            [
                formula,
                int(main["n"]),
                _fmt(main["mean"]),
                _fmt(main["ir"]),
                _fmt(main_adjusted[formula]["deflated"]),
                _fmt(main_adjusted[formula]["bonferroni_p"], 4),
                int(confirm["n"]),
                _fmt(confirm["mean"]),
                _fmt(confirm["ir"]),
                _fmt(confirm_adjusted[formula]["deflated"]),
                "YES" if formula in promoted else "no",
            ]
        )

    full_rows = []
    for formula in sorted(
        FORMULAS,
        key=lambda name: (
            full_main[name]["ir"] if np.isfinite(full_main[name]["ir"]) else -np.inf
        ),
        reverse=True,
    ):
        full_rows.append(
            [
                formula,
                _fmt(full_main[formula]["mean"]),
                _fmt(full_main[formula]["ir"]),
                _pct(full_main[formula]["hit_rate"]),
                _fmt(full_confirm[formula]["mean"]),
                _fmt(full_confirm[formula]["ir"]),
            ]
        )

    annual_rows = []
    for formula in FORMULAS:
        annual_rows.append(
            [formula]
            + [_fmt(results["annual"][year][formula]["mean"]) for year in OOS_YEARS]
        )

    formula_rows = [
        [number + 1, formula, FORMULA_DEFINITIONS[formula]]
        for number, formula in enumerate(FORMULAS)
    ]
    live_text = (
        "Promoted live-research candidates (maximum four): %s."
        % ", ".join("`%s`" % formula for formula in promoted)
        if promoted
        else "No formula passes every promotion gate; there is no mined live factor."
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = [
        "# Autonomous seed-composition factor evolution",
        "",
        "Generated by `research/factor_evolve.py` at %s." % generated,
        "",
        "## Frozen anti-overfit protocol",
        "",
        "- Split-adjusted free ETF bars are loaded through `research/etf_panel.py`.",
        "- The seven literature seeds and all N=30 formulas were declared before "
        "evaluation. Evolution is limited to sums, differences, causal expanding "
        "ranks, and rank residuals versus 510300; there is no OOS formula search.",
        "- The 2018-2021 interval is the frozen design/training window. Only "
        "2022-2026 is reported as OOS.",
        "- Promotion uses 2022-2025 OOS only. 2026, including July, is a final "
        "stress/reporting slice and cannot create a candidate.",
        "- Main evidence is weekly equity-only `GROWTH` cross-sectional Spearman "
        "Rank IC against strict next-week returns. Confirmation is per-name "
        "time-series IC on `%s`." % "`, `".join(CONFIRM_CODES),
        "- Promotion requires prior-OOS main IR > %.2f, four-asset IR > %.2f, "
        "and positive N=30 deflated scores in both tests. At most %d formulas "
        "may be recommended. Thresholds and signs are never relaxed."
        % (IR_THRESHOLD, IR_THRESHOLD, MAX_LIVE_FACTORS),
        "",
        "The deflated score subtracts the expected best null IC IR across 30 "
        "independent Gaussian trials. Bonferroni p-values are also reported. "
        "The four-asset test has only four names, so passing its deflated hurdle "
        "is intentionally difficult.",
        "",
        "## Promotion result",
        "",
        live_text,
        "",
        "Frozen training rows: %d; last training label: %s."
        % (
            results["training_rows"],
            results["training_last_label"].date().isoformat(),
        ),
        "",
        "## Promotion evidence: prior OOS 2022-2025",
        "",
        _table(
            [
                "Formula",
                "CS weeks",
                "CS mean",
                "CS IR",
                "CS deflated",
                "CS Bonf p",
                "Confirm names",
                "Confirm mean",
                "Confirm IR",
                "Confirm deflated",
                "Promote",
            ],
            rows,
        ),
        "",
        "## Full OOS diagnostic: 2022-2026",
        "",
        "These numbers are diagnostics only; 2026 never changes promotion.",
        "",
        _table(
            [
                "Formula",
                "CS mean",
                "CS IR",
                "CS hit",
                "4-asset mean",
                "4-asset IR",
            ],
            full_rows,
        ),
        "",
        "## Annual OOS equity-CS IC mean",
        "",
        _table(["Formula"] + [str(year) for year in OOS_YEARS], annual_rows),
        "",
        "![Factor evolution IC](plots/factor_evolve_ic.png)",
        "",
        "## Declared formula inventory",
        "",
        _table(["#", "Formula", "Frozen definition"], formula_rows),
        "",
        "## Limits",
        "",
        "- The 30 formulas are highly dependent, so N=30 is declared rather "
        "than reduced post hoc.",
        "- ETF survivorship bias remains. Later funds enter after inception; "
        "historical delisted funds may be absent.",
        "- IC is a signal diagnostic, not a traded portfolio result. Costs, "
        "capacity, and execution are not modeled.",
        "",
    ]
    return "\n".join(sections)


def run() -> Dict[str, object]:
    panel = build_panel(load_daily())
    results = evaluate(panel)
    write_plot(results)
    REPORT_PATH.write_text(build_report(results), encoding="utf-8")
    print(
        "formulas=%d panel_rows=%d training_last_label=%s"
        % (
            len(FORMULAS),
            len(panel),
            results["training_last_label"].date().isoformat(),
        )
    )
    print("report=%s" % REPORT_PATH)
    print("plot=%s" % PLOT_PATH)
    print("promoted=%s" % results["promoted"])
    print("top prior-OOS formulas:")
    for formula in sorted(
        FORMULAS,
        key=lambda name: (
            results["prior_main"][name]["ir"]
            if np.isfinite(results["prior_main"][name]["ir"])
            else -np.inf
        ),
        reverse=True,
    )[:10]:
        print(
            "  %-27s CS_IR=% .3f CS_defl=% .3f confirm_IR=% .3f confirm_defl=% .3f"
            % (
                formula,
                results["prior_main"][formula]["ir"],
                results["prior_main_adjusted"][formula]["deflated"],
                results["prior_confirm"][formula]["ir"],
                results["prior_confirm_adjusted"][formula]["deflated"],
            )
        )
    return results


if __name__ == "__main__":
    run()
