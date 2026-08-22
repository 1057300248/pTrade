# -*- coding: utf-8 -*-
"""Offline research backtest for the GEM ETF rotation (ptrade_gem_etf).

Rules
-----
- Data: research/cache/etf_daily/*.parquet (date/open/high/low/close/volume/amount)
- Signal computed at T close, orders filled at T+1 close, one-way cost 8bp
- Weekly rebalance on ISO-week change; crash / 22% trailing stop flattens same day
- Full universe scoring runs only on weekly-rebalance days and flatten days
- Reports full sample 2018-01-01 .. 2026-08-21, IS 2018-2021, OOS 2022-01-01 ..,
  plus the 2024-02 and 2026-07 stress windows; benchmark 510300

Does not import PTrade builtins; live trading still requires PTrade.
"""
from __future__ import print_function

import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _import_strategy(retries=8, delay=15):
    """Import ptrade_gem_etf, waiting if another writer is mid-flight."""
    last_err = None
    for attempt in range(retries):
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        try:
            import ptrade_gem_etf
            return ptrade_gem_etf
        except Exception as exc:
            last_err = exc
            sys.modules.pop("ptrade_gem_etf", None)
            if attempt < retries - 1:
                print("import ptrade_gem_etf failed (%r); retry %d/%d in %ds"
                      % (exc, attempt + 1, retries - 1, delay))
                time.sleep(delay)
    raise ImportError("cannot import ptrade_gem_etf: %r" % (last_err,))


_strategy = _import_strategy()
GROWTH = _strategy.GROWTH
DIVERSIFIER = _strategy.DIVERSIFIER
GOLD = getattr(_strategy, "GOLD", ["518880.SS"])
DIVIDEND = getattr(_strategy, "DIVIDEND", ["512890.SS", "510880.SS"])
BONDS = getattr(_strategy, "BONDS", ["511010.SS", "511090.SS", "511260.SS"])
apply_hysteresis = _strategy.apply_hysteresis
build_targets = _strategy.build_targets
classify_state = _strategy.classify_state
crash_triggered = _strategy.crash_triggered
crowding_points = _strategy.crowding_points
dual_eligible = _strategy.dual_eligible
filter_correlated = _strategy.filter_correlated
gold_trend_on = _strategy.gold_trend_on
log_returns = _strategy.log_returns
period_return = _strategy.period_return
realized_vol = _strategy.realized_vol
trailing_stop_hit = _strategy.trailing_stop_hit
ts_momentum = _strategy.ts_momentum
# Tiny constants get fallbacks so a missing symbol never breaks the run.
STATE_LOCK = getattr(_strategy, "STATE_LOCK", "lockdown")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
START = "2018-01-01"
END = "2026-08-21"
IS_END = "2021-12-31"
OOS_START = "2022-01-01"
MARKET = "510300.SS"
COST_ONE_WAY = 0.0008
# Mirrors initialize() in ptrade_gem_etf.py (frozen live parameters).
CORR_LIMIT = 0.70
VOL_TARGET = 0.18
HYSTERESIS = 1.15
TRAIL_PCT = 0.22
LOCKDOWN_DAYS = 3
WINDOWS = (
    ("2024-02-01", "2024-02-29"),
    ("2026-07-01", "2026-07-31"),
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
    """Mirror _score_universe (ts_momentum scores + dual gate)."""
    scores, dual, vols, ret60, crowd, closes = {}, {}, {}, {}, {}, {}
    for code in pool:
        bars = panel[code]
        n = counts[code][i]
        close = bars["close"][:n]
        if len(close) < 61:
            continue
        closes[code] = close
        scores[code] = ts_momentum(close)
        dual[code] = dual_eligible(close)
        vols[code] = realized_vol(close, 20)
        ret60[code] = log_returns(close)[-60:]
        crowd[code] = crowding_points(
            close, bars["high"][:n], bars["low"][:n], bars["volume"][:n], bars["amount"][:n]
        )
    return {
        "scores": scores,
        "dual": dual,
        "vols": vols,
        "ret60": ret60,
        "crowd": crowd,
        "closes": closes,
        "mkt_close": hist_close(panel, counts, MARKET, i),
    }


def select_growth(snap, held):
    """Mirror _select_growth: dual gate, crowding-4 veto, corr filter."""
    held = set(held or [])
    ranked = []
    for code in GROWTH:
        if not snap["dual"].get(code, False):
            continue
        if snap["crowd"].get(code, 0) >= 4 and code not in held:
            continue
        score = snap["scores"].get(code)
        if score is not None:
            ranked.append((code, float(score)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    ordered = [code for code, _ in ranked]
    return filter_correlated(ordered, snap["ret60"], CORR_LIMIT)


def _above_ma(close, days):
    close = np.asarray(close, dtype=float)
    close = close[np.isfinite(close)]
    if len(close) < int(days):
        return False
    return bool(close[-1] > float(np.mean(close[-int(days):])))


def _rank_available(codes, snap):
    available = [code for code in codes if code in snap["scores"]]
    available.sort(key=lambda code: float(snap["scores"].get(code, -1e18)),
                   reverse=True)
    return available


def select_diversifiers(snap):
    """Mirror _select_diversifiers: gold trend, else dividend, else bonds."""
    gold_on = [code for code in GOLD
               if code in snap["closes"] and gold_trend_on(snap["closes"][code])]
    if gold_on:
        return _rank_available(gold_on, snap)[:2]
    dividend_on = [code for code in DIVIDEND
                   if code in snap["closes"] and _above_ma(snap["closes"][code], 120)]
    if dividend_on:
        return _rank_available(dividend_on, snap)[:2]
    return _rank_available(BONDS, snap)[:2]


def weekly_target(snap, crash_flag, held):
    """Mirror _compute_targets (dual breadth + per-sleeve hysteresis)."""
    growth_available = [code for code in GROWTH if code in snap["dual"]]
    if growth_available:
        positive = sum(1 for code in growth_available if snap["dual"].get(code, False))
        breadth = float(positive) / float(len(growth_available))
    else:
        breadth = 0.0
    vol300 = realized_vol(snap["mkt_close"], 20) if len(snap["mkt_close"]) else 0.0
    state = classify_state(breadth, vol300, crash_flag)
    growth_ranked = select_growth(snap, held)
    div_ranked = select_diversifiers(snap)
    current_growth = [c for c in held if c in growth_ranked]
    current_div = [c for c in held if c in div_ranked]
    stable_growth = apply_hysteresis(
        current_growth, growth_ranked[:2], snap["scores"], HYSTERESIS)
    stable_div = apply_hysteresis(
        current_div, div_ranked[:2], snap["scores"], HYSTERESIS)
    weights = build_targets(
        state, stable_growth, stable_div, snap["vols"], vol_target=VOL_TARGET)
    return {code: w for code, w in weights.items() if w > 0.0}


def flatten_target(snap):
    """Mirror crash_overlay: lockdown sleeve into the diversifier waterfall."""
    div_ranked = select_diversifiers(snap)
    return build_targets(
        STATE_LOCK, [], div_ranked, snap["vols"], vol_target=VOL_TARGET)


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
        if code not in GROWTH:
            continue
        px = last_close(panel, counts, code, i)
        if px is not None:
            water = high_water.get(code)
            if water is None or px > water:
                high_water[code] = px
    return nav, new_holdings, True


def overlay_flatten_needed(holdings, high_water, panel, counts, i):
    """Market crash + 22% growth trailing stop at the close of calendar[i]."""
    if not holdings:
        return False
    flatten = False
    mkt_hist = hist_close(panel, counts, MARKET, i)
    if len(mkt_hist) >= 4 and crash_triggered(mkt_hist, 0.06, 0.08):
        flatten = True
    for code in list(holdings):
        if code not in GROWTH:
            continue
        px = last_close(panel, counts, code, i)
        if px is None:
            continue
        water = high_water.get(code)
        if water is None or px > water:
            high_water[code] = px
        elif trailing_stop_hit(px, water, TRAIL_PCT):
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
    ret = float(sub[-1] / sub[0] - 1.0)
    peak = np.maximum.accumulate(sub)
    dd = float(np.min(sub / peak - 1.0))
    return ret, dd


def print_block(label, strat, bench):
    print("%s" % label)
    print("  strategy: CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f" % (
        strat[0] * 100.0, strat[1] * 100.0, strat[2]))
    print("  510300  : CAGR=%6.2f%%  MDD=%7.2f%%  Sharpe=%5.2f" % (
        bench[0] * 100.0, bench[1] * 100.0, bench[2]))


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

        # 3) daily overlay on today's close: crash / 22% trailing stop
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
            crash_flag = lockdown_left > 0
            if len(snap["mkt_close"]) >= 4 and crash_triggered(snap["mkt_close"], 0.06, 0.08):
                lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)
                crash_flag = True
            pending = weekly_target(snap, crash_flag, list(holdings))
            last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    eq_dates = pd.DatetimeIndex(calendar[sim])
    equity = np.asarray(equity, dtype=float)
    bench = np.asarray([last_close(panel, counts, MARKET, i) for i in sim], dtype=float)
    bench = bench / bench[0]

    print("GEM research backtest %s .. %s" % (eq_dates[0].date(), eq_dates[-1].date()))
    print("signal at T close, fill at T+1 close, one-way cost %.0fbp" % (COST_ONE_WAY * 1e4))
    print("fills=%d  flatten days=%d  final NAV=%.3f" % (n_fills, n_flattens, equity[-1]))
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
            start, end, strat[0] * 100.0, strat[1] * 100.0, mark[0] * 100.0, mark[1] * 100.0))

    if is_s is not None and oos_s is not None:
        if oos_s[2] < 0.5 * is_s[2]:
            print("OVERFIT WARNING: OOS Sharpe=%.2f < 0.5 * IS Sharpe=%.2f" % (
                oos_s[2], is_s[2]))
        else:
            print("overfit check: IS Sharpe=%.2f, OOS Sharpe=%.2f -> ok" % (is_s[2], oos_s[2]))

    return {
        "full": full_s,
        "is": is_s,
        "oos": oos_s,
        "nav": float(equity[-1]),
        "fills": n_fills,
        "flattens": n_flattens,
    }


if __name__ == '__main__':
    run()
