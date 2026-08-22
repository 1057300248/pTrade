#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""High-dimensional, leakage-safe time-series ETF factor mining.

This script evaluates a fixed, literature-motivated set of technical factors.
For every calendar-year OOS slice it computes, within each ETF,

    corr(factor at weekly T, close-to-close return from T to T+1 week)

and summarizes those per-name correlations across names.  The main universe is
the live ``ptrade_rmdc_etf.GROWTH`` equity sleeve.  A prescribed four-asset
universe is evaluated separately and never pooled with the equity test.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from etf_panel import load_panel


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptrade_rmdc_etf import GROWTH as LIVE_GROWTH


CACHE_DIR = HERE / "cache" / "etf_daily"
REPORT_PATH = HERE / "factor_mine_highdim.md"
PLOT_PATH = HERE / "plots" / "highdim_ts_ic_heatmap.png"

GROWTH = tuple(LIVE_GROWTH)
SEPARATE_CODES = ("510300.SS", "159915.SZ", "513100.SS", "518880.SS")
MARKET = "510300.SS"
SIZE = "510500.SS"
TEST_YEARS = tuple(range(2019, 2027))
MIN_TS_WEEKS = 12
COMBO_IR_THRESHOLD = 0.30

FACTOR_DEFINITIONS = {
    "ret5": "5-day close return",
    "ret10": "10-day close return",
    "ret21": "21-day close return",
    "ret63": "63-day close return",
    "ret126": "126-day close return",
    "ret252": "252-day close return",
    "ts_mom_12_1": "close(T-21)/close(T-252)-1; 126d/5d fallback",
    "close_ma20": "close / 20-day moving average",
    "close_ma60": "close / 60-day moving average",
    "close_ma120": "close / 120-day moving average",
    "close_ma200": "close / 200-day moving average",
    "inv_vol10": "inverse 10-day annualized log-return volatility",
    "inv_vol20": "inverse 20-day annualized log-return volatility",
    "inv_vol60": "inverse 60-day annualized log-return volatility",
    "vol_change_10_60": "10-day volatility / 60-day volatility - 1",
    "vol_change_20_120": "20-day volatility / 120-day volatility - 1",
    "amplitude5": "5-day mean (high-low)/previous close",
    "amplitude20": "20-day mean (high-low)/previous close",
    "amplitude60": "60-day mean (high-low)/previous close",
    "close_location20": "close location in trailing 20-day high-low range",
    "close_location60": "close location in trailing 60-day high-low range",
    "term_spread_21_5": "21-day return minus 5-day return",
    "term_spread_10_5": "10-day return minus 5-day return",
    "term_spread_63_21": "63-day return minus 21-day return",
    "turnover_z_5_60": "5d-vs-60d log-amount z-score",
    "turnover_z_20_120": "20d-vs-120d log-amount z-score",
    "crowding_points": "raw live 0-4 crowding score (negative control)",
    "residual_mom": "120d market+size OLS residual score (negative control)",
    "rsi14": "14-day RSI scaled to [0,1]",
    "stochastic14": "close location in trailing 14-day range",
    "macd_12_26": "(EMA12-EMA26)/close",
    "macd_signal_gap": "MACD minus its 9-day EMA, divided by close",
    "price_accel_21_63": "21-day return minus one-third of 63-day return",
    "drawdown60": "close / trailing 60-day high - 1",
    "drawdown252": "close / trailing 252-day high - 1",
    "breakout20": "close / trailing 20-day high - 1",
    "skew20": "20-day daily log-return skew",
    "skew60": "60-day daily log-return skew",
    "autocorr20": "20-day lag-1 daily log-return correlation",
    "beta60_300": "60-day beta to 510300",
    "corr60_300": "60-day daily-return correlation to 510300",
    "illiquidity20": "20-day mean abs(return)/(amount/1e8)",
    "volume_price_corr20": "20-day corr(log-volume change, log return)",
}
FACTORS = tuple(FACTOR_DEFINITIONS)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0.0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def load_daily_panel() -> Dict[str, pd.DataFrame]:
    codes = tuple(dict.fromkeys(GROWTH + SEPARATE_CODES + (MARKET, SIZE)))
    array_panel = load_panel(CACHE_DIR, codes=codes)
    panel = {
        code: pd.DataFrame(
            {
                column: bars[column]
                for column in ("high", "low", "close", "volume", "amount")
            },
            index=pd.DatetimeIndex(bars["dates"], name="date"),
        )
        for code, bars in array_panel.items()
    }
    if tuple(LIVE_GROWTH) != GROWTH:
        raise AssertionError("GROWTH universe changed during run")
    return panel


def _weekly_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    periods = index.to_period("W-SUN")
    return pd.DatetimeIndex(dates.groupby(periods, sort=True).last().to_numpy())


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
    mean_amplitude = amplitude.rolling(20, min_periods=20).mean()
    points = (
        (volume_ratio > 2.0).astype(float)
        + (_safe_ratio(close, ma60) - 1.0 > 0.15).astype(float)
        + (close_volume_corr < 0.10).astype(float)
        + (mean_amplitude > 0.04).astype(float)
    )
    return points.where(close.rolling(61, min_periods=61).count() >= 61)


def _residual_momentum(
    regression_frame: pd.DataFrame,
    signal_dates: pd.DatetimeIndex,
    fit_window: int = 120,
    score_window: int = 60,
    skip: int = 5,
) -> pd.Series:
    """Weekly-only OLS: vectorized factors avoid a daily nested OLS loop."""
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
        x = np.column_stack((np.ones(len(sample)), sample[:, 1], sample[:, 2]))
        beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x.dot(beta)
        tail = residual[-score_window:]
        standard_deviation = float(np.std(tail, ddof=1))
        if np.isfinite(standard_deviation) and standard_deviation >= 1e-12:
            output.loc[signal_date] = float(np.sum(tail) / standard_deviation)
    return output


def _location(
    close: pd.Series, high: pd.Series, low: pd.Series, window: int
) -> pd.Series:
    rolling_high = high.rolling(window, min_periods=window).max()
    rolling_low = low.rolling(window, min_periods=window).min()
    return _safe_ratio(close - rolling_low, rolling_high - rolling_low)


def _turnover_z(log_amount: pd.Series, short: int, long: int) -> pd.Series:
    short_mean = log_amount.rolling(short, min_periods=short).mean()
    long_mean = log_amount.rolling(long, min_periods=long).mean()
    long_std = log_amount.rolling(long, min_periods=long).std(ddof=1)
    return _safe_ratio(short_mean - long_mean, long_std)


def _daily_features(
    frame: pd.DataFrame,
    market_return: pd.Series,
    size_spread: pd.Series,
) -> pd.DataFrame:
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"].where(frame["volume"] > 0.0)
    amount = frame["amount"].where(frame["amount"] > 0.0)
    log_return = np.log(close).diff().rename("asset")
    aligned_market = market_return.reindex(frame.index).rename("market")
    aligned_size = size_spread.reindex(frame.index).rename("size_spread")
    weekly_dates = _weekly_dates(frame.index)

    features = pd.DataFrame(index=frame.index)
    features["close"] = close
    returns = {}
    for days in (5, 10, 21, 63, 126, 252):
        returns[days] = close.pct_change(days)
        features["ret%d" % days] = returns[days]
    features["ts_mom_12_1"] = (
        _safe_ratio(close.shift(21), close.shift(252)) - 1.0
    ).combine_first(_safe_ratio(close.shift(5), close.shift(126)) - 1.0)

    for days in (20, 60, 120, 200):
        moving_average = close.rolling(days, min_periods=days).mean()
        features["close_ma%d" % days] = _safe_ratio(close, moving_average)

    vol = {}
    for days in (10, 20, 60, 120):
        vol[days] = (
            log_return.rolling(days, min_periods=days).std(ddof=1)
            * math.sqrt(252.0)
        )
    for days in (10, 20, 60):
        features["inv_vol%d" % days] = _safe_ratio(
            pd.Series(1.0, index=frame.index), vol[days]
        )
    features["vol_change_10_60"] = _safe_ratio(vol[10], vol[60]) - 1.0
    features["vol_change_20_120"] = _safe_ratio(vol[20], vol[120]) - 1.0

    daily_amplitude = _safe_ratio(high - low, close.shift(1))
    for days in (5, 20, 60):
        features["amplitude%d" % days] = daily_amplitude.rolling(
            days, min_periods=days
        ).mean()
    features["close_location20"] = _location(close, high, low, 20)
    features["close_location60"] = _location(close, high, low, 60)

    features["term_spread_21_5"] = returns[21] - returns[5]
    features["term_spread_10_5"] = returns[10] - returns[5]
    features["term_spread_63_21"] = returns[63] - returns[21]
    log_amount = np.log(amount)
    features["turnover_z_5_60"] = _turnover_z(log_amount, 5, 60)
    features["turnover_z_20_120"] = _turnover_z(log_amount, 20, 120)
    features["crowding_points"] = _crowding_points(frame)

    regression = pd.concat([log_return, aligned_market, aligned_size], axis=1)
    features["residual_mom"] = _residual_momentum(
        regression, weekly_dates
    ).reindex(frame.index)

    change = close.diff()
    average_gain = change.clip(lower=0.0).rolling(14, min_periods=14).mean()
    average_loss = (-change.clip(upper=0.0)).rolling(14, min_periods=14).mean()
    relative_strength = _safe_ratio(average_gain, average_loss)
    features["rsi14"] = (100.0 - 100.0 / (1.0 + relative_strength)) / 100.0
    features["stochastic14"] = _location(close, high, low, 14)

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    features["macd_12_26"] = _safe_ratio(macd, close)
    features["macd_signal_gap"] = _safe_ratio(macd - macd_signal, close)
    features["price_accel_21_63"] = returns[21] - returns[63] / 3.0

    for days in (60, 252):
        trailing_high = close.rolling(days, min_periods=days).max()
        features["drawdown%d" % days] = _safe_ratio(close, trailing_high) - 1.0
    features["breakout20"] = (
        _safe_ratio(close, close.rolling(20, min_periods=20).max()) - 1.0
    )
    features["skew20"] = log_return.rolling(20, min_periods=20).skew()
    features["skew60"] = log_return.rolling(60, min_periods=60).skew()
    features["autocorr20"] = log_return.rolling(20, min_periods=20).corr(
        log_return.shift(1)
    )
    market_variance = aligned_market.rolling(60, min_periods=45).var(ddof=1)
    market_covariance = log_return.rolling(60, min_periods=45).cov(aligned_market)
    features["beta60_300"] = _safe_ratio(market_covariance, market_variance)
    features["corr60_300"] = log_return.rolling(60, min_periods=45).corr(
        aligned_market
    )
    features["illiquidity20"] = (
        _safe_ratio(log_return.abs(), amount / 1.0e8)
        .rolling(20, min_periods=20)
        .mean()
    )
    log_volume_change = np.log(volume).diff()
    features["volume_price_corr20"] = log_volume_change.rolling(
        20, min_periods=20
    ).corr(log_return)
    return features


def build_factor_panel(daily: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    market_return = np.log(daily[MARKET]["close"]).diff()
    size_return = np.log(daily[SIZE]["close"]).diff()
    size_spread = size_return - market_return
    records = []
    for code, frame in daily.items():
        features = _daily_features(frame, market_return, size_spread)
        weekly_dates = _weekly_dates(frame.index)
        weekly = features.loc[weekly_dates].copy()
        weekly["code"] = code
        weekly["signal_date"] = weekly.index
        periods = weekly.index.to_period("W-SUN")
        weekly["week_order"] = np.asarray([period.ordinal for period in periods])
        next_week = weekly["week_order"].shift(-1).eq(weekly["week_order"] + 1)
        weekly["forward_return"] = (
            weekly["close"].shift(-1) / weekly["close"] - 1.0
        ).where(next_week)
        weekly["target_date"] = pd.Series(
            weekly.index, index=weekly.index
        ).shift(-1).where(next_week)
        records.append(weekly.reset_index(drop=True))

    panel = pd.concat(records, ignore_index=True, sort=False)
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    panel["target_date"] = pd.to_datetime(panel["target_date"])
    missing_factors = set(FACTORS).difference(panel.columns)
    if missing_factors:
        raise AssertionError("missing factors: %s" % sorted(missing_factors))
    return add_causal_factor_ranks(panel)


def add_causal_factor_ranks(panel: pd.DataFrame) -> pd.DataFrame:
    """Rank each factor against that ETF's history available through T."""
    ranked_panel = panel.sort_values(["code", "signal_date"]).copy()
    for factor in FACTORS:
        ranked = (
            ranked_panel.groupby("code", sort=False)[factor]
            .expanding(min_periods=MIN_TS_WEEKS)
            .rank(method="average", pct=True)
        )
        ranked.index = ranked.index.droplevel(0)
        ranked_panel["rank_" + factor] = ranked.reindex(ranked_panel.index)
    return ranked_panel.sort_index()


def per_name_ts_ic(
    frame: pd.DataFrame,
    factor: str,
    codes: Sequence[str],
    minimum_weeks: int = MIN_TS_WEEKS,
) -> pd.Series:
    observations = {}
    universe = frame.loc[frame["code"].isin(codes)]
    for code, group in universe.groupby("code", sort=True):
        pair = (
            group.loc[:, [factor, "forward_return"]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if len(pair) < minimum_weeks:
            continue
        if pair[factor].nunique() < 2 or pair["forward_return"].nunique() < 2:
            continue
        correlation = pair[factor].corr(pair["forward_return"])
        if np.isfinite(correlation):
            observations[str(code)] = float(correlation)
    return pd.Series(observations, dtype=float, name=factor).sort_index()


def ic_summary(values: Iterable[float]) -> Dict[str, float]:
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


def multiple_testing_stats(
    summary: Mapping[str, Mapping[str, float]]
) -> Dict[str, Dict[str, float]]:
    number_of_tests = len(FACTORS)
    normal = NormalDist()
    euler_gamma = 0.5772156649015329
    expected_max_z = (
        (1.0 - euler_gamma) * normal.inv_cdf(1.0 - 1.0 / number_of_tests)
        + euler_gamma
        * normal.inv_cdf(1.0 - 1.0 / (number_of_tests * math.e))
    )
    output = {}
    for factor in FACTORS:
        metrics = summary[factor]
        count = int(metrics["n"])
        hurdle = expected_max_z / math.sqrt(count) if count > 0 else np.nan
        ir = metrics["ir"]
        deflated = ir - hurdle if np.isfinite(ir) else np.nan
        z_score = abs(ir) * math.sqrt(count) if count and np.isfinite(ir) else np.nan
        p_value = (
            math.erfc(z_score / math.sqrt(2.0)) if np.isfinite(z_score) else np.nan
        )
        output[factor] = {
            "null_hurdle": hurdle,
            "deflated_score": deflated,
            "bonferroni_p": (
                min(1.0, number_of_tests * p_value)
                if np.isfinite(p_value)
                else np.nan
            ),
        }
    return output


def _combo_score(frame: pd.DataFrame, selected: Sequence[str]) -> pd.Series:
    if not selected:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    rank_columns = ["rank_" + factor for factor in selected]
    ranks = frame.loc[:, rank_columns]
    complete = ranks.notna().sum(axis=1).eq(len(rank_columns))
    return ranks.mean(axis=1).where(complete)


def run_walk_forward(panel: pd.DataFrame) -> Dict[str, object]:
    main_annual = {}
    separate_annual = {}
    combo_annual = {}
    combo_selected = {}
    audit = []
    prior_oos_frames = []
    combo_frames = []

    for year in TEST_YEARS:
        cutoff = pd.Timestamp(year=year, month=1, day=1)
        next_cutoff = pd.Timestamp(year=year + 1, month=1, day=1)
        train = panel.loc[panel["target_date"] < cutoff]
        test = panel.loc[
            (panel["signal_date"] >= cutoff)
            & (panel["signal_date"] < next_cutoff)
        ].copy()
        if not train.empty and not bool((train["target_date"] < cutoff).all()):
            raise AssertionError("training labels cross %d boundary" % year)

        selected = []
        if prior_oos_frames:
            prior_oos = pd.concat(prior_oos_frames, ignore_index=True, sort=False)
            for factor in FACTORS:
                prior_metrics = ic_summary(per_name_ts_ic(prior_oos, factor, GROWTH))
                if (
                    np.isfinite(prior_metrics["ir"])
                    and prior_metrics["ir"] > COMBO_IR_THRESHOLD
                ):
                    selected.append(factor)
        combo_selected[year] = selected

        main_annual[year] = {}
        separate_annual[year] = {}
        for factor in FACTORS:
            main_annual[year][factor] = ic_summary(
                per_name_ts_ic(test, factor, GROWTH)
            )
            separate_annual[year][factor] = ic_summary(
                per_name_ts_ic(test, factor, SEPARATE_CODES)
            )

        main_test = test.loc[test["code"].isin(GROWTH)].copy()
        main_test["combo"] = _combo_score(main_test, selected)
        combo_values = (
            per_name_ts_ic(main_test, "combo", GROWTH)
            if selected
            else pd.Series(dtype=float)
        )
        combo_annual[year] = ic_summary(combo_values)
        if selected:
            combo_frames.append(
                main_test.loc[
                    :, ["code", "signal_date", "forward_return", "combo"]
                ].copy()
            )

        labeled_test = test.loc[test["forward_return"].notna()]
        audit.append(
            {
                "year": year,
                "last_train_label": (
                    train["target_date"].max().date().isoformat()
                    if not train.empty
                    else "N/A"
                ),
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
                "selected": selected,
            }
        )
        prior_oos_frames.append(test)

    oos_panel = pd.concat(prior_oos_frames, ignore_index=True, sort=False)
    main_values = {
        factor: per_name_ts_ic(oos_panel, factor, GROWTH) for factor in FACTORS
    }
    separate_values = {
        factor: per_name_ts_ic(oos_panel, factor, SEPARATE_CODES)
        for factor in FACTORS
    }
    main_pooled = {factor: ic_summary(main_values[factor]) for factor in FACTORS}
    separate_pooled = {
        factor: ic_summary(separate_values[factor]) for factor in FACTORS
    }

    if combo_frames:
        combo_panel = pd.concat(combo_frames, ignore_index=True, sort=False)
        combo_pooled = ic_summary(per_name_ts_ic(combo_panel, "combo", GROWTH))
    else:
        combo_pooled = ic_summary(pd.Series(dtype=float))

    return {
        "main_annual": main_annual,
        "separate_annual": separate_annual,
        "main_values": main_values,
        "separate_values": separate_values,
        "main_pooled": main_pooled,
        "separate_pooled": separate_pooled,
        "main_multiple": multiple_testing_stats(main_pooled),
        "separate_multiple": multiple_testing_stats(separate_pooled),
        "combo_annual": combo_annual,
        "combo_pooled": combo_pooled,
        "combo_selected": combo_selected,
        "audit": audit,
    }


def _fmt(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return ("%." + str(digits) + "f") % value


def _pct(value: float, digits: int = 1) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return ("%." + str(digits) + "f%%") % (100.0 * value)


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
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


def write_heatmap(results: Mapping[str, object]) -> None:
    annual = results["main_annual"]
    matrix = np.asarray(
        [
            [annual[year][factor]["mean"] for year in TEST_YEARS]
            for factor in FACTORS
        ],
        dtype=float,
    )
    finite = np.abs(matrix[np.isfinite(matrix)])
    limit = max(0.10, float(finite.max()) if finite.size else 0.10)
    figure, axis = plt.subplots(figsize=(13.5, 17.0))
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
    axis.set_yticklabels(FACTORS, fontsize=8)
    axis.set_xlabel("OOS calendar year")
    axis.set_ylabel("Predeclared technical factor")
    axis.set_title(
        "GROWTH equity ETFs: mean per-name time-series IC by OOS year"
    )
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            label = "N/A" if not np.isfinite(value) else "%.2f" % value
            color = "white" if np.isfinite(value) and abs(value) > 0.60 * limit else "black"
            axis.text(
                column, row, label, ha="center", va="center", fontsize=5.5, color=color
            )
    colorbar = figure.colorbar(image, ax=axis, fraction=0.02, pad=0.02)
    colorbar.set_label("Mean per-name TS-IC")
    figure.tight_layout()
    PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_PATH, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _pooled_rows(
    pooled: Mapping[str, Mapping[str, float]],
    multiple: Mapping[str, Mapping[str, float]],
) -> List[List[object]]:
    rows = []
    for factor in sorted(FACTORS, key=lambda name: pooled[name]["ir"], reverse=True):
        metrics = pooled[factor]
        adjustment = multiple[factor]
        rows.append(
            [
                factor,
                int(metrics["n"]),
                _fmt(metrics["mean"]),
                _fmt(metrics["ir"]),
                _pct(metrics["hit_rate"]),
                _fmt(adjustment["null_hurdle"]),
                _fmt(adjustment["deflated_score"]),
                _fmt(adjustment["bonferroni_p"], 4),
                "YES" if metrics["ir"] > COMBO_IR_THRESHOLD else "no",
            ]
        )
    return rows


def build_report(
    panel: pd.DataFrame, results: Mapping[str, object]
) -> str:
    main = results["main_pooled"]
    separate = results["separate_pooled"]
    main_multiple = results["main_multiple"]
    separate_multiple = results["separate_multiple"]
    main_passers = [
        factor for factor in FACTORS if main[factor]["ir"] > COMBO_IR_THRESHOLD
    ]
    separate_passers = [
        factor for factor in FACTORS if separate[factor]["ir"] > COMBO_IR_THRESHOLD
    ]
    cross_validated = [
        factor
        for factor in main_passers
        if factor in separate_passers
        and main_multiple[factor]["deflated_score"] > 0.0
        and separate_multiple[factor]["deflated_score"] > 0.0
    ]
    live_candidates = sorted(
        cross_validated, key=lambda factor: main[factor]["ir"], reverse=True
    )[:4]

    if live_candidates:
        live_text = (
            "Protocol-qualified live candidates (maximum four): %s. This is a "
            "factor-screen result, not a position-sizing recommendation."
            % ", ".join("`%s`" % factor for factor in live_candidates)
        )
    elif main_passers == ["term_spread_10_5"] and "term_spread_10_5" not in separate_passers:
        live_text = (
            "`term_spread_10_5` is the only main-universe raw-IR passer, but it "
            "is research-only until the separate four-asset test also passes. "
            "No mined factor is approved for live use."
        )
    else:
        live_text = (
            "No factor cleared the raw IR threshold plus the separate-universe "
            "and deflated-score gates. No mined factor is approved for live use."
        )

    audit_rows = []
    for row in results["audit"]:
        selected = row["selected"]
        audit_rows.append(
            [
                row["year"],
                row["last_train_label"],
                row["test_start"],
                row["test_end"],
                row["test_weeks"],
                ", ".join(selected) if selected else "None",
            ]
        )
    combo_rows = []
    for year in TEST_YEARS:
        metrics = results["combo_annual"][year]
        combo_rows.append(
            [
                year,
                ", ".join(results["combo_selected"][year])
                if results["combo_selected"][year]
                else "None",
                int(metrics["n"]),
                _fmt(metrics["mean"]),
                _fmt(metrics["ir"]),
            ]
        )
    combo = results["combo_pooled"]
    combo_rows.append(
        ["Pooled", "Year-specific", int(combo["n"]), _fmt(combo["mean"]), _fmt(combo["ir"])]
    )

    definition_rows = [
        [index + 1, factor, FACTOR_DEFINITIONS[factor]]
        for index, factor in enumerate(FACTORS)
    ]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = [
        "# High-dimensional time-series ETF factor mining",
        "",
        "Generated by `research/factor_mine_highdim.py` at %s." % generated,
        "",
        "## Frozen protocol",
        "",
        "- Main universe: the %d equity ETFs in `ptrade_rmdc_etf.GROWTH`. "
        "Separate test: `%s`; results are never pooled."
        % (len(GROWTH), "`, `".join(SEPARATE_CODES)),
        "- Signals use Friday or the final available bar in each ISO week. "
        "Labels are next-week close returns only; missing whole weeks are not "
        "bridged.",
        "- For each calendar-year test slice and each ETF, TS-IC is Pearson "
        "corr(factor at T, return T to T+1 week), with at least %d observations. "
        "Reported IC is the mean across names and IC IR is mean/std across names."
        % MIN_TS_WEEKS,
        "- Expanding boundary: a training row is eligible only when its next-week "
        "label is strictly before January 1 of test year Y. Factor formulas and "
        "the factor count N=%d were fixed before examining this run." % len(FACTORS),
        "- Combo membership for Y uses only completed prior-OOS main-universe "
        "labels and requires pooled IR > %.2f. Scores are equal-weight causal "
        "within-name expanding percentile ranks. The threshold is never relaxed."
        % COMBO_IR_THRESHOLD,
        "- 2026-07 has no special role in definitions, selection, or reporting.",
        "",
        "The DSR-style score subtracts the expected best null IC IR among N "
        "independent Gaussian trials from observed IC IR. Bonferroni p-values "
        "multiply a two-sided normal approximation by N. ETF correlations make "
        "the independence assumption optimistic, so the separate universe is "
        "also required before any live recommendation.",
        "",
        "## Pass/fail and live recommendation",
        "",
        "- Main raw-IR passers: %s."
        % (", ".join("`%s`" % factor for factor in main_passers) or "none"),
        "- Separate four-asset raw-IR passers: %s."
        % (", ".join("`%s`" % factor for factor in separate_passers) or "none"),
        "- %s" % live_text,
        "",
        "## Walk-forward boundary and combo audit",
        "",
        _markdown_table(
            [
                "Test year",
                "Last train label",
                "Test start",
                "Test end",
                "Test weeks",
                "Factors selected before year",
            ],
            audit_rows,
        ),
        "",
        "## Main GROWTH universe: pooled OOS TS-IC",
        "",
        _markdown_table(
            [
                "Factor",
                "Names",
                "Mean IC",
                "IC IR",
                "Positive names",
                "N-test hurdle",
                "Deflated score",
                "Bonferroni p",
                "IR>0.30",
            ],
            _pooled_rows(main, main_multiple),
        ),
        "",
        "![High-dimensional TS-IC heatmap](plots/highdim_ts_ic_heatmap.png)",
        "",
        "## Separate four-asset test: pooled OOS TS-IC",
        "",
        _markdown_table(
            [
                "Factor",
                "Names",
                "Mean IC",
                "IC IR",
                "Positive names",
                "N-test hurdle",
                "Deflated score",
                "Bonferroni p",
                "IR>0.30",
            ],
            _pooled_rows(separate, separate_multiple),
        ),
        "",
        "With only four names, cross-name IR is unstable and the N-test null "
        "hurdle is deliberately severe. This test is confirmatory, not another "
        "source of factor selection.",
        "",
        "## Strictly lagged main-universe combo",
        "",
        _markdown_table(
            ["Year", "Prior-OOS factors", "Names", "Mean IC", "IC IR"], combo_rows
        ),
        "",
        "## A priori factor inventory",
        "",
        _markdown_table(["#", "Factor", "Definition"], definition_rows),
        "",
        "## Limitations",
        "",
        "- The current cache has survivorship bias: later ETFs enter after "
        "inception, while historical delisted funds may be absent.",
        "- These are signal diagnostics, not a portfolio backtest. Costs, "
        "turnover, capacity, and execution are not modeled.",
        "- 2026 is partial through the cache boundary; the unlabeled final week "
        "is excluded automatically.",
        "",
    ]
    return "\n".join(sections)


def run() -> Dict[str, object]:
    daily = load_daily_panel()
    panel = build_factor_panel(daily)
    results = run_walk_forward(panel)
    write_heatmap(results)
    REPORT_PATH.write_text(build_report(panel, results), encoding="utf-8")

    main = results["main_pooled"]
    separate = results["separate_pooled"]
    ranked = sorted(FACTORS, key=lambda factor: main[factor]["ir"], reverse=True)
    print("factors=%d panel_rows=%d growth=%d separate=%d" % (
        len(FACTORS), len(panel), len(GROWTH), len(SEPARATE_CODES)
    ))
    print("report=%s" % REPORT_PATH)
    print("heatmap=%s" % PLOT_PATH)
    print("top main-universe factors:")
    for factor in ranked[:10]:
        adjustment = results["main_multiple"][factor]
        print(
            "  %-23s IC=% .4f IR=% .3f deflated=% .3f bonf_p=%.4f separate_IR=% .3f"
            % (
                factor,
                main[factor]["mean"],
                main[factor]["ir"],
                adjustment["deflated_score"],
                adjustment["bonferroni_p"],
                separate[factor]["ir"],
            )
        )
    print(
        "main passers=%s"
        % [factor for factor in FACTORS if main[factor]["ir"] > COMBO_IR_THRESHOLD]
    )
    print(
        "separate passers=%s"
        % [
            factor
            for factor in FACTORS
            if separate[factor]["ir"] > COMBO_IR_THRESHOLD
        ]
    )
    return results


if __name__ == "__main__":
    run()
