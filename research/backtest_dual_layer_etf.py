# -*- coding: utf-8 -*-
"""Research-only prototype of docs/alpha_etf_design.md section 5 (dual layer).

THIS IS NOT A LIVE STRATEGY. It exists to check whether the design doc's
prototype numbers (OOS 2022-2026 CAGR ~11.1%) can be reproduced on the
split-adjusted panel with the frozen section-6 parameters. No retuning.

Spec implemented (docs/alpha_etf_design.md section 5, frozen table section 6):
- Layer 1: breadth = share of growth names (>=250 bars) with close > MA50;
  >=0.55 risk-on, <0.35 risk-off, hysteresis in between, initial risk-off.
- Layer 2: mom63/mom126 skip-5 dual momentum gate (both > 0); composite
  0.35*rankpct(mom63) + 0.35*rankpct(mom126) + 0.15*rankpct(residmom, RMDC
  frozen formula) + 0.15*rankpct(inv_vol); crowding >=3 blocks new opens;
  risk-on merges growth+div pools, top 4; risk-off div only, top 3;
  incumbents stay while eligible, challenger needs +0.10 composite.
- Weights: inverse vol (vol floor 0.10), single cap 0.35, x0.99 budget,
  12% diversifier floor (risk-on only), 18% vol target on the 60d sample
  covariance (scale down only). Idle weight = cash at zero return.
- Layer 3: single-name crash exit (-8%/1d or -8%/3d) sells that name same
  day; market lockdown (510300 -6%/1d or -8%/3d, or >=2 growth crashes the
  same day) sells all growth into <=2 eligible div names at 25% each
  (vol-scaled) for 5 sessions. No portfolio trailing stop, no corr filter.
- Engine: signal at T close, fill at T+1 close, 8bp one-way (overlay fills
  same day), weekly on ISO-week change; benchmark 510300.
"""
from __future__ import print_function

import math
import os
import sys

import numpy as np
import pandas as pd

from etf_panel import load_panel

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# RMDC frozen formulas, reused verbatim per the design doc.
from ptrade_rmdc_etf import crash_triggered, crowding_points, log_returns, \
    residual_momentum

START = "2018-01-01"
END = "2026-08-21"
IS_END = "2021-12-31"
OOS_START = "2022-01-01"
MARKET = "510300.SS"
SIZE = "510500.SS"
COST_ONE_WAY = 0.0008
DESIGN_OOS_CAGR = 0.111  # section 1 of the design doc

GROWTH = [
    "510300.SS", "510500.SS", "512100.SS", "159915.SZ", "588000.SS",
    "512480.SS", "515880.SS", "515980.SS", "512660.SS", "512010.SS",
    "159928.SZ", "512690.SS", "512800.SS", "512880.SS", "512400.SS",
    "515030.SS", "516160.SS", "515220.SS",
]
DIV = [
    "518880.SS", "510880.SS", "512890.SS", "511010.SS", "511090.SS",
    "511260.SS", "513500.SS", "513100.SS", "513030.SS", "513520.SS",
]

# Frozen parameters (section 6). Do not tune.
MIN_BARS = 250
BREADTH_ON = 0.55
BREADTH_OFF = 0.35
MOM_SKIP = 5
N_ON = 4
N_OFF = 3
HYSTERESIS_GAP = 0.10
VOL_FLOOR = 0.10
SINGLE_CAP = 0.35
BUDGET = 0.99
DIV_FLOOR = 0.12
VOL_TARGET = 0.18
COV_WINDOW = 60
LOCKDOWN_DAYS = 5
WINDOWS = (
    ("2024-02-01", "2024-02-29"),
    ("2026-07-01", "2026-07-31"),
)


def build_counts(panel, calendar):
    return {code: np.searchsorted(bars["dates"], calendar, side="right")
            for code, bars in panel.items()}


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


def mom_skip(close, days, skip=MOM_SKIP):
    """close[-1-skip] / close[-1-skip-days] - 1 (doc: close[-6]/close[-69])."""
    close = np.asarray(close, dtype=float)
    need = days + skip + 1
    if len(close) < need:
        return None
    start = float(close[-need])
    end = float(close[-(skip + 1)])
    if start <= 0:
        return None
    return end / start - 1.0


def realized_vol(close, days=20):
    rets = log_returns(close)
    if len(rets) < 5:
        return 0.0
    return float(np.std(rets[-int(days):], ddof=1) * math.sqrt(252.0))


def rankpct(values):
    """values: dict code -> float. Returns dict code -> percentile [0, 1]."""
    codes = list(values)
    if len(codes) == 1:
        return {codes[0]: 0.5}
    arr = np.asarray([values[c] for c in codes], dtype=float)
    order = np.argsort(np.argsort(arr))
    denom = float(len(codes) - 1)
    return {codes[k]: float(order[k]) / denom for k in range(len(codes))}


# ---------------------------------------------------------------------------
# Weekly snapshot and selection
# ---------------------------------------------------------------------------
def build_snapshot(panel, counts, i):
    mkt_c = hist_close(panel, counts, MARKET, i)
    size_c = hist_close(panel, counts, SIZE, i)
    snap = {"mom63": {}, "mom126": {}, "resid": {}, "vol20": {}, "crowd": {},
            "ret": {}, "mkt_close": mkt_c, "breadth": 0.0}
    listed = []
    above = 0
    for code in GROWTH + DIV:
        bars = panel.get(code)
        if bars is None:
            continue
        n = counts[code][i]
        close = bars["close"][:n]
        if len(close) < MIN_BARS:
            continue
        m63 = mom_skip(close, 63)
        m126 = mom_skip(close, 126)
        if m63 is None or m126 is None:
            continue
        snap["mom63"][code] = m63
        snap["mom126"][code] = m126
        snap["resid"][code] = residual_momentum(close, mkt_c, size_c)
        snap["vol20"][code] = realized_vol(close, 20)
        snap["crowd"][code] = crowding_points(
            close, bars["high"][:n], bars["low"][:n],
            bars["volume"][:n], bars["amount"][:n])
        snap["ret"][code] = log_returns(close)
        if code in GROWTH:
            listed.append(code)
            if len(close) >= 50 and close[-1] > float(np.mean(close[-50:])):
                above += 1
    if listed:
        snap["breadth"] = float(above) / float(len(listed))
    return snap


def eligible_codes(snap, pool, held):
    """Dual momentum gate; crowding >=3 blocks new opens (incumbents exempt)."""
    held = set(held or [])
    out = []
    for code in pool:
        if code not in snap["mom63"]:
            continue
        if snap["mom63"][code] <= 0.0 or snap["mom126"][code] <= 0.0:
            continue
        if snap["crowd"].get(code, 0) >= 3 and code not in held:
            continue
        out.append(code)
    return out


def composite_scores(snap, codes):
    if not codes:
        return {}
    p63 = rankpct({c: snap["mom63"][c] for c in codes})
    p126 = rankpct({c: snap["mom126"][c] for c in codes})
    pres = rankpct({c: snap["resid"][c] for c in codes})
    pinv = rankpct({c: 1.0 / max(snap["vol20"][c], 0.01) for c in codes})
    return {c: 0.35 * p63[c] + 0.35 * p126[c] + 0.15 * pres[c] + 0.15 * pinv[c]
            for c in codes}


def pick_with_hysteresis(comp, incumbents, n):
    """Incumbents stay while eligible; challenger needs +0.10 composite."""
    ranked = sorted(comp, key=lambda c: comp[c], reverse=True)
    kept = [c for c in incumbents if c in comp]
    kept.sort(key=lambda c: comp[c], reverse=True)
    kept = kept[:n]
    challengers = [c for c in ranked if c not in kept]
    while len(kept) < n and challengers:
        kept.append(challengers.pop(0))
    while challengers:
        weakest = min(kept, key=lambda c: comp[c])
        best = challengers[0]
        if comp[best] > comp[weakest] + HYSTERESIS_GAP:
            kept.remove(weakest)
            kept.append(challengers.pop(0))
        else:
            break
    kept.sort(key=lambda c: comp[c], reverse=True)
    return kept


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
def inverse_vol_weights(codes, vol_map):
    """Inverse vol with 0.10 vol floor and iterative 0.35 single cap."""
    if not codes:
        return {}
    inv = {c: 1.0 / max(float(vol_map.get(c, 0.20)), VOL_FLOOR) for c in codes}
    total = sum(inv.values())
    weights = {c: inv[c] / total for c in codes}
    capped = set()
    while True:
        over = [c for c in codes if c not in capped and weights[c] > SINGLE_CAP]
        if not over:
            break
        for c in over:
            weights[c] = SINGLE_CAP
            capped.add(c)
        rest = [c for c in codes if c not in capped]
        room = 1.0 - SINGLE_CAP * len(capped)
        if not rest or room <= 0:
            break
        rest_total = sum(inv[c] for c in rest)
        for c in rest:
            weights[c] = room * inv[c] / rest_total
    return weights


def cov_vol_scale(weights, snap):
    """Scale down (never up) to the 18% target using the 60d covariance."""
    codes = [c for c in weights if weights[c] > 0]
    if not codes:
        return dict(weights)
    rets = []
    n_min = COV_WINDOW
    for c in codes:
        r = snap["ret"].get(c, np.array([]))[-COV_WINDOW:]
        n_min = min(n_min, len(r))
        rets.append(r)
    if n_min >= 20 and len(codes) > 1:
        matrix = np.vstack([r[-n_min:] for r in rets])
        cov = np.cov(matrix, ddof=1) * 252.0
        w = np.asarray([weights[c] for c in codes], dtype=float)
        var = float(w.dot(cov).dot(w))
    else:
        var = sum((weights[c] * max(snap["vol20"].get(c, 0.20), 1e-4)) ** 2
                  for c in codes)
    port_vol = math.sqrt(max(var, 0.0))
    if port_vol <= 1e-9:
        return dict(weights)
    scale = min(1.0, VOL_TARGET / port_vol)
    return {c: weights[c] * scale for c in weights}


def weekly_target(snap, state_on, held):
    if state_on:
        pool = GROWTH + DIV
        n_pick = N_ON
    else:
        pool = DIV
        n_pick = N_OFF
    codes = eligible_codes(snap, pool, held)
    comp = composite_scores(snap, codes)
    if not comp:
        return {}
    picks = pick_with_hysteresis(comp, [c for c in held if c in comp], n_pick)
    weights = inverse_vol_weights(picks, snap["vol20"])
    weights = {c: w * BUDGET for c, w in weights.items()}
    if state_on:
        div_sum = sum(w for c, w in weights.items() if c in DIV)
        if div_sum < DIV_FLOOR:
            div_eligible = eligible_codes(snap, DIV, held)
            div_comp = composite_scores(snap, div_eligible)
            if div_comp:
                top_div = max(div_comp, key=div_comp.get)
                shortfall = DIV_FLOOR - div_sum
                growth_sum = sum(w for c, w in weights.items() if c in GROWTH)
                if growth_sum > shortfall:
                    factor = (growth_sum - shortfall) / growth_sum
                    for c in list(weights):
                        if c in GROWTH:
                            weights[c] *= factor
                    weights[top_div] = weights.get(top_div, 0.0) + shortfall
    return cov_vol_scale(weights, snap)


def lockdown_target(snap, held):
    """<=2 eligible div names at 25% each, vol-target scaled."""
    codes = eligible_codes(snap, DIV, held)
    comp = composite_scores(snap, codes)
    picks = sorted(comp, key=lambda c: comp[c], reverse=True)[:2]
    if not picks:
        return {}
    return cov_vol_scale({c: 0.25 for c in picks}, snap)


# ---------------------------------------------------------------------------
# Portfolio mechanics and metrics
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target):
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False
    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    return nav, {c: w for c, w in target.items() if w > 1e-6}, True


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


def sub_perf(navs, dates, start, end):
    navs = np.asarray(navs, dtype=float)
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        return None
    sub = navs[mask]
    return perf_summary(sub / sub[0], dates[mask])


def window_summary(navs, dates, start, end):
    navs = np.asarray(navs, dtype=float)
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        return None
    sub = navs[mask]
    peak = np.maximum.accumulate(sub)
    return float(sub[-1] / sub[0] - 1.0), float(np.min(sub / peak - 1.0))


def print_block(label, strat, bench):
    print("%s" % label)
    print("  strategy: CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f" % (
        strat[0] * 100.0, strat[1] * 100.0, strat[2]))
    print("  510300  : CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f" % (
        bench[0] * 100.0, bench[1] * 100.0, bench[2]))


def iso_week(date64):
    iso = pd.Timestamp(date64).isocalendar()
    return (int(iso[0]), int(iso[1]))


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def run():
    panel = load_panel()
    calendar = np.unique(np.concatenate(
        [panel[c]["dates"] for c in GROWTH + DIV if c in panel]))
    counts = build_counts(panel, calendar)
    lo, hi = np.datetime64(START), np.datetime64(END)
    sim = [i for i in range(len(calendar)) if lo <= calendar[i] <= hi]

    nav = 1.0
    holdings = {}
    pending = None
    state_on = False  # initial risk-off per spec
    lockdown_left = 0
    last_week = None
    equity = []
    n_fills = 0
    n_lockdowns = 0

    for step, i in enumerate(sim):
        # 1) accrue previous close -> today's close
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

        # 2) T+1 fill of last close's pending target
        if pending is not None:
            nav, holdings, traded = apply_fill(nav, holdings, pending)
            if traded:
                n_fills += 1
            pending = None

        # 3) daily overlay at today's close
        growth_crashed = []
        for code in [c for c in holdings if c in GROWTH]:
            hist = hist_close(panel, counts, code, i)
            if len(hist) >= 2 and crash_triggered(hist, 0.08, 0.08):
                growth_crashed.append(code)
        mkt_hist = hist_close(panel, counts, MARKET, i)
        market_crash = len(mkt_hist) >= 2 and crash_triggered(mkt_hist, 0.06, 0.08)
        if market_crash or len(growth_crashed) >= 2:
            lockdown_left = LOCKDOWN_DAYS
            snap = build_snapshot(panel, counts, i)
            nav, holdings, traded = apply_fill(
                nav, holdings, lockdown_target(snap, list(holdings)))
            if traded:
                n_fills += 1
            n_lockdowns += 1
        elif growth_crashed:
            target = {c: w for c, w in holdings.items() if c not in growth_crashed}
            nav, holdings, traded = apply_fill(nav, holdings, target)
            if traded:
                n_fills += 1

        # 4) weekly scoring on ISO-week change
        week = iso_week(calendar[i])
        if week != last_week:
            snap = build_snapshot(panel, counts, i)
            if snap["breadth"] >= BREADTH_ON:
                state_on = True
            elif snap["breadth"] < BREADTH_OFF:
                state_on = False
            if lockdown_left > 0:
                pending = lockdown_target(snap, list(holdings))
            else:
                pending = weekly_target(snap, state_on, list(holdings))
            last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    eq_dates = pd.DatetimeIndex(calendar[sim])
    equity = np.asarray(equity, dtype=float)
    bench = np.asarray([last_close(panel, counts, MARKET, i) for i in sim],
                       dtype=float)
    bench = bench / bench[0]

    print("Dual-layer research prototype (NOT LIVE) %s .. %s" % (
        eq_dates[0].date(), eq_dates[-1].date()))
    print("signal at T close, fill at T+1 close, one-way cost %.0fbp, cash return 0" % (
        COST_ONE_WAY * 1e4))
    print("fills=%d  lockdowns=%d  final NAV=%.3f" % (n_fills, n_lockdowns, equity[-1]))
    print("")

    full_s = perf_summary(equity, eq_dates)
    full_b = perf_summary(bench, eq_dates)
    print_block("FULL SAMPLE %s .. %s" % (START, END), full_s, full_b)

    is_s = sub_perf(equity, eq_dates, START, IS_END)
    is_b = sub_perf(bench, eq_dates, START, IS_END)
    print_block("IS %s .. %s (diagnostics only)" % (START, IS_END), is_s, is_b)

    oos_s = sub_perf(equity, eq_dates, OOS_START, END)
    oos_b = sub_perf(bench, eq_dates, OOS_START, END)
    print_block("OOS %s .. %s" % (OOS_START, END), oos_s, oos_b)

    for start, end in WINDOWS:
        strat = window_summary(equity, eq_dates, start, end)
        mark = window_summary(bench, eq_dates, start, end)
        if strat is None or mark is None:
            print("window %s..%s: not enough data" % (start, end))
            continue
        print("window %s..%s: strategy ret=%6.2f%% dd=%6.2f%% | 510300 ret=%6.2f%% dd=%6.2f%%" % (
            start, end, strat[0] * 100.0, strat[1] * 100.0,
            mark[0] * 100.0, mark[1] * 100.0))

    if is_s is not None and oos_s is not None:
        if oos_s[2] < 0.5 * is_s[2]:
            print("OVERFIT WARNING: OOS Sharpe=%.2f < 0.5 * IS Sharpe=%.2f" % (
                oos_s[2], is_s[2]))
        else:
            print("overfit check: IS Sharpe=%.2f, OOS Sharpe=%.2f -> ok" % (
                is_s[2], oos_s[2]))
    if oos_s is not None:
        gap = oos_s[0] - DESIGN_OOS_CAGR
        if abs(gap) <= 0.02:
            print("reproduction check: OOS CAGR=%.2f%% vs design %.1f%% -> close" % (
                oos_s[0] * 100.0, DESIGN_OOS_CAGR * 100.0))
        else:
            print("UNREPRODUCED: OOS CAGR=%.2f%% vs design %.1f%% (gap %+.2fpp)" % (
                oos_s[0] * 100.0, DESIGN_OOS_CAGR * 100.0, gap * 100.0))

    return {
        "full": full_s,
        "is": is_s,
        "oos": oos_s,
        "nav": float(equity[-1]),
        "fills": n_fills,
        "lockdowns": n_lockdowns,
    }


if __name__ == '__main__':
    run()
