# -*- coding: utf-8 -*-
"""Offline research backtest for the ADM dual-momentum rotation (ptrade_adm_etf).

Rules
-----
- Data: research/cache/etf_daily/*.parquet (date/open/high/low/close/volume/amount)
- Signal computed at T close, orders filled at T+1 close, one-way cost 8bp
- Weekly rebalance on ISO-week change; market / held risk-asset crash flattens
  to bonds the same day with a 3-session lockdown (no trailing stop in ADM)
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


def _import_strategy(retries=33, delay=15):
    """Import ptrade_adm_etf, waiting up to ~8 minutes for the live file."""
    last_err = None
    for attempt in range(retries):
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        try:
            import ptrade_adm_etf
            return ptrade_adm_etf
        except Exception as exc:
            last_err = exc
            sys.modules.pop("ptrade_adm_etf", None)
            if attempt < retries - 1:
                print("import ptrade_adm_etf failed (%r); retry %d/%d in %ds"
                      % (exc, attempt + 1, retries - 1, delay))
                time.sleep(delay)
    raise ImportError("cannot import ptrade_adm_etf: %r" % (last_err,))


_strategy = _import_strategy()
RISK = _strategy.RISK
# Tiny constants get fallbacks so a missing symbol never breaks the run.
BOND = getattr(_strategy, "BOND", "511010.SS")
build_targets = _strategy.build_targets
crash_triggered = _strategy.crash_triggered
crowding_points = _strategy.crowding_points
month_gate = _strategy.month_gate
period_return = _strategy.period_return
pick_risk_asset = _strategy.pick_risk_asset
realized_vol = _strategy.realized_vol
ts_momentum = _strategy.ts_momentum

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
START = "2018-01-01"
END = "2026-08-21"
IS_END = "2021-12-31"
OOS_START = "2022-01-01"
MARKET = "510300.SS"
COST_ONE_WAY = 0.0008
# Mirrors initialize() in ptrade_adm_etf.py (frozen live parameters).
VOL_TARGET = 0.12
LOCKDOWN_DAYS = 3
WINDOWS = (
    ("2024-02-01", "2024-02-29"),
    ("2026-07-01", "2026-07-31"),
)
UNIVERSE = list(dict.fromkeys(list(RISK) + [BOND]))


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
def score_risk(panel, counts, i):
    """Mirror _score_risk over the RISK sleeve."""
    scores, gates, crowds, vols = {}, {}, {}, {}
    for code in RISK:
        bars = panel.get(code)
        if bars is None:
            continue
        n = counts[code][i]
        if n <= 0:
            continue
        close = bars["close"][:n]
        scores[code] = ts_momentum(close)
        gates[code] = month_gate(close)
        crowds[code] = crowding_points(
            close, bars["high"][:n], bars["low"][:n], bars["volume"][:n], bars["amount"][:n]
        )
        vols[code] = realized_vol(close, 20)
    return scores, gates, crowds, vols


def weekly_target(panel, counts, i, lockdown):
    """Mirror _compute_targets: winner-take-all with bond remainder."""
    scores, gates, crowds, vols = score_risk(panel, counts, i)
    winner = pick_risk_asset(scores, gates, crowds)
    if lockdown:
        winner = None
    winner_vol = None if winner is None else vols.get(winner)
    return build_targets(winner, winner_vol, vol_target=VOL_TARGET, bond=BOND)


def overlay_flatten_needed(holdings, panel, counts, i):
    """Mirror crash_overlay: crash on the market or any held risk asset."""
    held_risk = [code for code in holdings if code in RISK]
    for code in dict.fromkeys([MARKET] + held_risk):
        hist = hist_close(panel, counts, code, i)
        if len(hist) >= 2 and crash_triggered(hist, 0.06, 0.08):
            return True
    return False


def iso_week(date64):
    iso = pd.Timestamp(date64).isocalendar()
    return (int(iso[0]), int(iso[1]))


# ---------------------------------------------------------------------------
# Portfolio mechanics
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target):
    """Trade to target weights at the close of calendar[i]; 8bp per side."""
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False
    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    new_holdings = {code: w for code, w in target.items() if w > 1e-6}
    return nav, new_holdings, True


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
    missing = [code for code in UNIVERSE if code not in panel]
    if missing:
        raise SystemExit("missing cached bars for %s" % ", ".join(missing))
    calendar = np.unique(np.concatenate([panel[c]["dates"] for c in UNIVERSE]))
    counts = build_counts(panel, calendar)
    lo = np.datetime64(START)
    hi = np.datetime64(END)
    sim = [i for i in range(len(calendar)) if lo <= calendar[i] <= hi]

    nav = 1.0
    holdings = {}
    pending = None
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
            nav, holdings, traded = apply_fill(nav, holdings, pending)
            if traded:
                n_fills += 1
            pending = None

        # 3) daily overlay on today's close: crash -> bonds, 3-day lockdown
        if overlay_flatten_needed(holdings, panel, counts, i):
            lockdown_left = LOCKDOWN_DAYS
            nav, holdings, traded = apply_fill(
                nav, holdings, build_targets(None, None, bond=BOND))
            if traded:
                n_fills += 1
            n_flattens += 1

        # 4) weekly scoring on ISO-week change (skip if any history missing,
        #    mirroring the live len(histories) < len(universe) guard)
        week = iso_week(calendar[i])
        if week != last_week:
            if all(counts[code][i] > 0 for code in UNIVERSE):
                lockdown = lockdown_left > 0
                mkt_hist = hist_close(panel, counts, MARKET, i)
                if len(mkt_hist) >= 2 and crash_triggered(mkt_hist, 0.06, 0.08):
                    lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)
                    lockdown = True
                pending = weekly_target(panel, counts, i, lockdown)
                last_week = week
            else:
                last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    eq_dates = pd.DatetimeIndex(calendar[sim])
    equity = np.asarray(equity, dtype=float)
    bench = np.asarray([last_close(panel, counts, MARKET, i) for i in sim], dtype=float)
    bench = bench / bench[0]

    print("ADM research backtest %s .. %s" % (eq_dates[0].date(), eq_dates[-1].date()))
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
