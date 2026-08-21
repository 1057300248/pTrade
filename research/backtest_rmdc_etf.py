# -*- coding: utf-8 -*-
"""Research backtest for RMDC. T-day close signal, T+1 close fill, 8bp one way.

Does not import PTrade. Live trading still requires 国金 PTrade.
"""
from __future__ import print_function

import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ptrade_rmdc_etf import (
    DIVERSIFIER,
    GROWTH,
    STATE_LOCK,
    build_targets,
    classify_state,
    crash_triggered,
    crowding_points,
    filter_correlated,
    growth_breadth,
    log_returns,
    median_vol,
    mean_pairwise_corr,
    period_return,
    realized_vol,
    residual_momentum,
    trailing_stop_hit,
    trend_quality,
)

CACHE = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
COST = 0.0008


def load_panel():
    frames = {}
    for name in os.listdir(CACHE):
        if not name.endswith(".parquet"):
            continue
        code = name.replace(".parquet", "")
        df = pd.read_parquet(os.path.join(CACHE, name))
        df["date"] = pd.to_datetime(df["date"])
        frames[code] = df.sort_values("date").drop_duplicates("date").set_index("date")
    return frames


def _col(df, date, field):
    if df is None or date not in df.index:
        return None
    value = df.loc[date, field]
    if isinstance(value, pd.Series):
        value = value.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def _closes_to(df, date):
    if df is None:
        return np.array([])
    part = df.loc[:date, "close"].dropna().astype(float)
    return part.values


def _field_to(df, date, field):
    if df is None:
        return np.array([])
    if field not in df.columns:
        return np.array([])
    return df.loc[:date, field].dropna().astype(float).values


def snapshot_at(panel, date, market="510300.SS", size="510500.SS", bond="511010.SS"):
    mkt = panel.get(market)
    size_df = panel.get(size)
    bond_df = panel.get(bond)
    mkt_c = _closes_to(mkt, date)
    size_c = _closes_to(size_df, date)
    bond_c = _closes_to(bond_df, date)
    scores, tq, ret20, ret63, vols, ret60, crowd = {}, {}, {}, {}, {}, {}, {}
    for code, df in panel.items():
        close = _closes_to(df, date)
        if len(close) < 70 or len(mkt_c) < 70:
            continue
        scores[code] = residual_momentum(close, mkt_c, size_c)
        tq[code] = trend_quality(close)
        ret20[code] = period_return(close, 20)
        ret63[code] = period_return(close, 63)
        vols[code] = realized_vol(close, 20)
        ret60[code] = log_returns(close)[-60:]
        crowd[code] = crowding_points(
            close,
            _field_to(df, date, "high"),
            _field_to(df, date, "low"),
            _field_to(df, date, "volume"),
            _field_to(df, date, "amount"),
        )
    return {
        "scores": scores,
        "tq": tq,
        "ret20": ret20,
        "ret63": ret63,
        "vols": vols,
        "ret60": ret60,
        "crowd": crowd,
        "bond_ret": period_return(bond_c, 63) if len(bond_c) else 0.0,
        "mkt_close": mkt_c,
    }


def eligible(codes, snap, require_trend):
    ranked = []
    for code in codes:
        if code not in snap["scores"]:
            continue
        if snap["crowd"].get(code, 0) >= 3:
            continue
        if require_trend and snap["tq"].get(code, 0) < 0.90:
            continue
        if snap["ret63"].get(code, 0) <= 0:
            continue
        if snap["ret63"].get(code, 0) < snap["bond_ret"]:
            continue
        ranked.append((code, snap["scores"][code] * max(snap["tq"].get(code, 0.01), 0.01)))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked]


def make_weights(snap, lockdown):
    breadth = growth_breadth(snap["ret20"], GROWTH)
    med_vol = median_vol(snap["vols"], GROWTH)
    if snap["mkt_close"] is not None and crash_triggered(snap["mkt_close"], 0.06, 0.08):
        lockdown = True
    state = classify_state(breadth, med_vol, lockdown)
    growth_ranked = filter_correlated(eligible(GROWTH, snap, True), snap["ret60"], 0.65)
    div_ranked = filter_correlated(eligible(DIVERSIFIER, snap, False), snap["ret60"], 0.65)
    cluster = mean_pairwise_corr(snap["ret60"], growth_ranked[:5]) > 0.75
    div_all_neg = all(snap["ret63"].get(c, -1) <= 0 for c in DIVERSIFIER if c in snap["ret63"])
    weights = build_targets(state, growth_ranked, div_ranked, snap["vols"], cluster, div_all_neg, 0.12)
    return state, weights, breadth, med_vol


def window_stats(equity, dates, start, end):
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if mask.sum() < 5:
        return None
    series = equity[mask]
    ret = float(series[-1] / series[0] - 1.0)
    peak = np.maximum.accumulate(series)
    dd = float(np.min(series / peak - 1.0))
    return ret, dd


def run():
    panel = load_panel()
    market = panel["510300.SS"]
    dates = market.index
    dates = dates[(dates >= "2018-01-01") & (dates <= "2026-08-21")]
    nav = 1.0
    holdings = {}
    high_water = {}
    lockdown_left = 0
    last_week = None
    equity = []
    eq_dates = []
    turns = 0

    for i, date in enumerate(dates[:-1]):
        next_date = dates[i + 1]
        if lockdown_left > 0:
            lockdown_left -= 1
        week = (int(date.isocalendar()[0]), int(date.isocalendar()[1]))
        flatten = False
        for code in list(holdings):
            if code in DIVERSIFIER:
                continue
            close = _col(panel.get(code), date, "close")
            hist = _closes_to(panel.get(code), date)
            if hist is not None and crash_triggered(hist, 0.08, 0.08):
                flatten = True
            if close is not None:
                water = high_water.get(code)
                if water is None or close > water:
                    high_water[code] = close
                elif trailing_stop_hit(close, water, 0.20):
                    flatten = True
        if flatten:
            lockdown_left = 5

        if last_week != week or flatten:
            snap = snapshot_at(panel, date)
            state, target, breadth, med_vol = make_weights(snap, lockdown_left > 0)
            last_week = week
            traded = set(holdings) | set(target)
            turnover = 0.0
            for code in traded:
                old = holdings.get(code, 0.0)
                new = target.get(code, 0.0)
                turnover += abs(new - old)
            nav *= max(0.0, 1.0 - COST * turnover / 2.0)
            holdings = dict(target)
            turns += 1
            high_water = {c: _col(panel.get(c), date, "close") or high_water.get(c, 0) for c in holdings}

        day_ret = 0.0
        for code, weight in holdings.items():
            px0 = _col(panel.get(code), date, "close")
            px1 = _col(panel.get(code), next_date, "close")
            if px0 and px1:
                day_ret += weight * (px1 / px0 - 1.0)
        cash_w = max(0.0, 1.0 - sum(holdings.values()))
        nav *= (1.0 + day_ret)
        equity.append(nav)
        eq_dates.append(next_date)

    equity = np.asarray(equity, dtype=float)
    eq_dates = pd.to_datetime(eq_dates)
    years = (eq_dates[-1] - eq_dates[0]).days / 365.25
    cagr = float(equity[-1] ** (1.0 / max(years, 1e-6)) - 1.0)
    peak = np.maximum.accumulate(equity)
    mdd = float(np.min(equity / peak - 1.0))
    rets = np.diff(equity) / equity[:-1]
    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * math.sqrt(252)) if np.std(rets) > 0 else 0.0
    bench = panel["510300.SS"].loc[eq_dates, "close"]
    bench_nav = bench / bench.iloc[0]
    bench_cagr = float(bench_nav.iloc[-1] ** (1.0 / max(years, 1e-6)) - 1.0)
    bench_dd = float(np.min(bench_nav.values / np.maximum.accumulate(bench_nav.values) - 1.0))

    print("RMDC research backtest 2018-01 -> %s" % eq_dates[-1].date())
    print("  CAGR=%.2f%% MDD=%.2f%% Sharpe=%.2f trades=%d final_nav=%.3f" % (
        cagr * 100, mdd * 100, sharpe, turns, equity[-1],
    ))
    print("  510300 CAGR=%.2f%% MDD=%.2f%%" % (bench_cagr * 100, bench_dd * 100))
    for label, start, end in (
        ("2024-02 microcap", "2024-02-01", "2024-02-29"),
        ("2026-07 crowding", "2026-07-01", "2026-07-31"),
        ("2026-06 to 08", "2026-06-01", "2026-08-21"),
    ):
        stats = window_stats(equity, eq_dates, start, end)
        if stats:
            print("  %s ret=%.2f%% dd=%.2f%%" % (label, stats[0] * 100, stats[1] * 100))
    return {
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
        "nav": float(equity[-1]),
        "turns": turns,
    }


if __name__ == "__main__":
    run()
