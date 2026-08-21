# -*- coding: utf-8 -*-
"""Offline research backtest for the RMDC ETF rotation (ptrade_rmdc_etf).

Rules
-----
- Data: research/cache/etf_daily/*.parquet (date/open/high/low/close/volume/amount)
- Signal computed at T close, orders filled at T+1 close, one-way cost 8bp
- Weekly rebalance on ISO-week change; crash / 20% trailing stop flattens same day
- Full universe scoring runs only on weekly-rebalance days and flatten days
- Range 2018-01-01 .. 2026-08-21, benchmark 510300

Does not import PTrade builtins; live trading still requires PTrade.
"""
from __future__ import print_function

import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _import_scoring():
    """Import ptrade_rmdc_etf, retrying after fixing sys.path if needed."""
    last_err = None
    for _attempt in range(3):
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        try:
            import ptrade_rmdc_etf
            return ptrade_rmdc_etf
        except Exception as exc:
            last_err = exc
    raise ImportError("cannot import ptrade_rmdc_etf: %r" % (last_err,))


_scoring = _import_scoring()
GROWTH = _scoring.GROWTH
DIVERSIFIER = _scoring.DIVERSIFIER
build_targets = _scoring.build_targets
classify_state = _scoring.classify_state
crash_triggered = _scoring.crash_triggered
crowding_points = _scoring.crowding_points
filter_correlated = _scoring.filter_correlated
growth_breadth = _scoring.growth_breadth
log_returns = _scoring.log_returns
median_vol = _scoring.median_vol
mean_pairwise_corr = _scoring.mean_pairwise_corr
period_return = _scoring.period_return
realized_vol = _scoring.realized_vol
residual_momentum = _scoring.residual_momentum
trailing_stop_hit = _scoring.trailing_stop_hit
trend_quality = _scoring.trend_quality

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
START = "2018-01-01"
END = "2026-08-21"
MARKET = "510300.SS"
SIZE = "510500.SS"
BOND = "511010.SS"
COST_ONE_WAY = 0.0008
TRAIL_PCT = 0.20
LOCKDOWN_DAYS = 5
CORR_LIMIT = 0.65
CORR_CLUSTER = 0.75
VOL_TARGET = 0.12
WINDOWS = (
    ("2024-02-01", "2024-02-29"),
    ("2026-07-01", "2026-07-31"),
    ("2026-06-01", "2026-08-21"),
)


# ---------------------------------------------------------------------------
# Data layer: per-code numpy arrays + O(1) "bars up to date" indexing
# ---------------------------------------------------------------------------
def load_panel():
    panel = {}
    for name in sorted(os.listdir(CACHE_DIR)):
        if not name.endswith(".parquet"):
            continue
        code = name[: -len(".parquet")]
        df = pd.read_parquet(os.path.join(CACHE_DIR, name))
        df = df.dropna(subset=["close"]).sort_values("date").drop_duplicates("date")
        close = df["close"].to_numpy(dtype=float)
        volume = df["volume"].to_numpy(dtype=float)
        amount = df["amount"].to_numpy(dtype=float)
        amount = np.where(np.isfinite(amount), amount, close * volume)
        panel[code] = {
            "dates": df["date"].to_numpy(dtype="datetime64[ns]"),
            "high": df["high"].to_numpy(dtype=float),
            "low": df["low"].to_numpy(dtype=float),
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    return panel


def build_counts(panel, calendar):
    """counts[code][i] = number of bars of code with date <= calendar[i]."""
    counts = {}
    for code, bars in panel.items():
        counts[code] = np.searchsorted(bars["dates"], calendar, side="right")
    return counts


def hist_close(panel, counts, code, i):
    bars = panel.get(code)
    if bars is None:
        return np.array([])
    return bars["close"][: counts[code][i]]


def last_close(panel, counts, code, i):
    bars = panel.get(code)
    if bars is None:
        return None
    n = counts[code][i]
    if n <= 0:
        return None
    return float(bars["close"][n - 1])


# ---------------------------------------------------------------------------
# Scoring (only called on weekly-rebalance days and flatten days)
# ---------------------------------------------------------------------------
def build_snapshot(panel, counts, pool, i):
    mkt_c = hist_close(panel, counts, MARKET, i)
    size_c = hist_close(panel, counts, SIZE, i)
    bond_c = hist_close(panel, counts, BOND, i)
    scores, tq, ret20, ret63, vols, ret60, crowd = {}, {}, {}, {}, {}, {}, {}
    for code in pool:
        bars = panel[code]
        n = counts[code][i]
        close = bars["close"][:n]
        if len(close) < 70 or len(mkt_c) < 70:
            continue
        scores[code] = residual_momentum(close, mkt_c, size_c)
        tq[code] = trend_quality(close)
        ret20[code] = period_return(close, 20)
        ret63[code] = period_return(close, 63)
        vols[code] = realized_vol(close, 20)
        ret60[code] = log_returns(close)[-60:]
        crowd[code] = crowding_points(
            close, bars["high"][:n], bars["low"][:n], bars["volume"][:n], bars["amount"][:n]
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
        score = snap["scores"].get(code)
        if score is None:
            continue
        if snap["crowd"].get(code, 0) >= 3:
            continue
        if require_trend and snap["tq"].get(code, 0.0) < 0.90:
            continue
        if snap["ret63"].get(code, 0.0) <= 0.0:
            continue
        if snap["ret63"].get(code, 0.0) < snap["bond_ret"]:
            continue
        ranked.append((code, score * max(snap["tq"].get(code, 0.0), 0.01)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [code for code, _ in ranked]


def weekly_target(snap, lockdown):
    breadth = growth_breadth(snap["ret20"], GROWTH)
    med_vol = median_vol(snap["vols"], GROWTH)
    state = classify_state(breadth, med_vol, lockdown)
    growth_ranked = filter_correlated(eligible(GROWTH, snap, True), snap["ret60"], CORR_LIMIT)
    div_ranked = filter_correlated(eligible(DIVERSIFIER, snap, False), snap["ret60"], CORR_LIMIT)
    cluster = mean_pairwise_corr(snap["ret60"], growth_ranked[:5]) > CORR_CLUSTER
    div_all_neg = True
    for code in DIVERSIFIER:
        if snap["ret63"].get(code, -1.0) > 0.0:
            div_all_neg = False
            break
    weights = build_targets(
        state, growth_ranked, div_ranked, snap["vols"], cluster, div_all_neg, VOL_TARGET
    )
    return {code: w for code, w in weights.items() if w >= 0.01}


def flatten_target(snap):
    div_ranked = filter_correlated(eligible(DIVERSIFIER, snap, False), snap["ret60"], CORR_LIMIT)
    if div_ranked:
        return {div_ranked[0]: 0.60}
    return {}


# ---------------------------------------------------------------------------
# Portfolio mechanics
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target, high_water, panel, counts, i):
    """Trade to target weights at the close of calendar[i]; 8bp per side."""
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False
    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    new_holdings = {code: w for code, w in target.items() if w > 1e-6}
    for code in list(high_water):
        if code not in new_holdings:
            high_water.pop(code)
    for code in new_holdings:
        if code in DIVERSIFIER:
            continue
        px = last_close(panel, counts, code, i)
        if px is not None:
            water = high_water.get(code)
            if water is None or px > water:
                high_water[code] = px
    return nav, new_holdings, True


def overlay_flatten_needed(holdings, high_water, panel, counts, i):
    """Crash / trailing-stop check at the close of calendar[i]."""
    if not holdings:
        return False
    flatten = False
    for code in list(holdings):
        if code in DIVERSIFIER:
            continue
        hist = hist_close(panel, counts, code, i)
        if len(hist) >= 4 and crash_triggered(hist, 0.08, 0.08):
            flatten = True
        px = None if len(hist) == 0 else float(hist[-1])
        if px is not None:
            water = high_water.get(code)
            if water is None or px > water:
                high_water[code] = px
            elif trailing_stop_hit(px, water, TRAIL_PCT):
                flatten = True
    mkt_hist = hist_close(panel, counts, MARKET, i)
    if len(mkt_hist) >= 4 and crash_triggered(mkt_hist, 0.06, 0.08):
        flatten = True
    return flatten


def iso_week(date64):
    iso = pd.Timestamp(date64).isocalendar()
    return (int(iso[0]), int(iso[1]))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def perf_summary(navs, dates):
    navs = np.asarray(navs, dtype=float)
    n_years = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    cagr = float((navs[-1] / navs[0]) ** (1.0 / n_years) - 1.0)
    peak = np.maximum.accumulate(navs)
    mdd = float(np.min(navs / peak - 1.0))
    rets = np.diff(navs) / navs[:-1]
    sd = float(np.std(rets, ddof=1)) if len(rets) > 2 else 0.0
    sharpe = float(np.mean(rets) / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    return cagr, mdd, sharpe


def window_summary(navs, dates, start, end):
    navs = np.asarray(navs, dtype=float)
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        return None
    sub = navs[mask]
    ret = float(sub[-1] / sub[0] - 1.0)
    peak = np.maximum.accumulate(sub)
    dd = float(np.min(sub / peak - 1.0))
    return ret, dd


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def run():
    panel = load_panel()
    pool = [c for c in dict.fromkeys(list(GROWTH) + list(DIVERSIFIER)) if c in panel]
    calendar = np.unique(np.concatenate([bars["dates"] for bars in panel.values()]))
    counts = build_counts(panel, calendar)
    lo = np.datetime64(START)
    hi = np.datetime64(END)
    sim = [i for i in range(len(calendar)) if lo <= calendar[i] <= hi]

    nav = 1.0
    holdings = {}
    pending = None
    high_water = {}
    lockdown_left = 0
    last_week = None
    equity = []
    n_fills = 0
    n_flattens = 0

    for step, i in enumerate(sim):
        # 1) accrue previous close -> today's close with current holdings
        if step > 0 and holdings:
            prev_i = sim[step - 1]
            port_ret = 0.0
            grown = {}
            for code, w in holdings.items():
                px0 = last_close(panel, counts, code, prev_i)
                px1 = last_close(panel, counts, code, i)
                r = 0.0
                if px0 and px1 and px0 > 0:
                    r = px1 / px0 - 1.0
                port_ret += w * r
                grown[code] = w * (1.0 + r)
            nav = nav * (1.0 + port_ret)
            if 1.0 + port_ret > 1e-9:
                holdings = {c: w / (1.0 + port_ret) for c, w in grown.items()}

        # 2) fill last close's pending target at today's close (T+1 fill)
        if pending is not None:
            nav, holdings, traded = apply_fill(
                nav, holdings, pending, high_water, panel, counts, i
            )
            if traded:
                n_fills += 1
            pending = None

        # 3) daily overlay on today's close: crash / 20% trailing stop
        flatten = overlay_flatten_needed(holdings, high_water, panel, counts, i)

        # 4) full scoring only on flatten days or ISO-week change
        week = iso_week(calendar[i])
        week_changed = week != last_week
        snap = None
        if flatten or week_changed:
            snap = build_snapshot(panel, counts, pool, i)
        if flatten:
            lockdown_left = LOCKDOWN_DAYS
            nav, holdings, traded = apply_fill(
                nav, holdings, flatten_target(snap), high_water, panel, counts, i
            )
            if traded:
                n_fills += 1
            n_flattens += 1
        if week_changed:
            lockdown = lockdown_left > 0
            if len(snap["mkt_close"]) >= 4 and crash_triggered(snap["mkt_close"], 0.06, 0.08):
                lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)
                lockdown = True
            pending = weekly_target(snap, lockdown)
            last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    eq_dates = pd.DatetimeIndex(calendar[sim])
    equity = np.asarray(equity, dtype=float)
    bench = np.asarray([last_close(panel, counts, MARKET, i) for i in sim], dtype=float)
    bench = bench / bench[0]

    s_cagr, s_mdd, s_sharpe = perf_summary(equity, eq_dates)
    b_cagr, b_mdd, b_sharpe = perf_summary(bench, eq_dates)

    print("RMDC research backtest %s .. %s" % (eq_dates[0].date(), eq_dates[-1].date()))
    print("signal at T close, fill at T+1 close, one-way cost %.0fbp" % (COST_ONE_WAY * 1e4))
    print("strategy: CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f  final NAV=%.3f" % (
        s_cagr * 100.0, s_mdd * 100.0, s_sharpe, equity[-1]))
    print("510300  : CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f" % (
        b_cagr * 100.0, b_mdd * 100.0, b_sharpe))
    print("fills=%d  flatten days=%d" % (n_fills, n_flattens))
    for start, end in WINDOWS:
        strat = window_summary(equity, eq_dates, start, end)
        mark = window_summary(bench, eq_dates, start, end)
        if strat is None or mark is None:
            print("window %s..%s: not enough data" % (start, end))
            continue
        print("window %s..%s: strategy ret=%6.2f%% dd=%6.2f%% | 510300 ret=%6.2f%% dd=%6.2f%%" % (
            start, end, strat[0] * 100.0, strat[1] * 100.0, mark[0] * 100.0, mark[1] * 100.0))
    return {
        "cagr": s_cagr,
        "mdd": s_mdd,
        "sharpe": s_sharpe,
        "nav": float(equity[-1]),
        "fills": n_fills,
        "flattens": n_flattens,
    }


if __name__ == '__main__':
    run()
