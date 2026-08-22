#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAlphas "risk-parity + momentum resonance" weekly rotator, CN-15 pool.

RESEARCH ONLY -- blog reproduction, NOT a live candidate.  Never promote any
number printed here into ptrade_*.py or into account targets.

Rules reproduced (both variants share the same weekly signal):
- Pool: frozen CN-15 (see POOL below).  No cherry-picking after results.
- Eligibility: a name needs >= max(vol_window, corr_window, momentum_window)
  = max(250, 500, 20) = 500 finite cached bars.
- Weekly signal on the last trading session of each ISO week (usually Friday).
- Volatility: std (ddof=1) of trailing 250 daily returns * sqrt(252).
  Survivors must fall inside [0.08, 0.28] annualised.
- Skip the week entirely (hold current positions) if < 5 vol-survivors.
- Correlation: trailing 500 daily returns, pairwise Pearson among survivors;
  keep the 5 names with the LOWEST mean ABSOLUTE correlation to the other
  survivors (shared formula in openalphas_rp_mom.mean_absolute_correlation).
- Momentum: OLS slope b of ln(close) over the last 20 bars;
  score = (exp(b * 252) - 1) * R^2 (classic annualised-slope-times-R2 used by
  the OpenAlphas / JoinQuant rotation posts).  Keep top 2 of the corr-5.
- Weights: inverse 250d vol, normalised to 1.0 (fully invested, cash 0%).
- Variant A (article-faithful): fill at the SAME Friday close as the signal,
  one-way cost 10bp (0.001).
- Variant B (book-faithful): signal at T close, fill at T+1 close (next
  session), one-way cost 8bp (0.0008) -- the repo's live-book convention.
- Benchmark: 510300 buy-and-hold entered at the variant's first possible fill
  with the same one-way cost.

Formulas (vol, |corr| ranking, momentum score, inverse-vol weights) are
imported from research/openalphas_rp_mom.py so both reproductions share one
source of truth.  That module's article engine is NOT reused here because its
_clean_prices drops every date on which any pool member lacks a bar -- with
513180 (listed 2021-05-25) in the pool that would truncate the whole CN panel
to 2021+.  This runner keeps a per-name eligibility calendar instead.

Run:  python3 research/openalphas_cn_backtest.py
"""
from __future__ import print_function

import math
import os

import numpy as np
import pandas as pd

from etf_panel import load_panel
from openalphas_rp_mom import (
    annualized_volatility,
    filter_by_volatility,
    inverse_volatility_weights,
    mean_absolute_correlation,
    momentum_score,
)


HERE = os.path.abspath(os.path.dirname(__file__))

POOL = (
    "510300.SS",  # CSI 300
    "159915.SZ",  # ChiNext
    "512660.SS",  # defense
    "512010.SS",  # pharma
    "512480.SS",  # semiconductor
    "511010.SS",  # treasury bond
    "518880.SS",  # gold
    "513100.SS",  # NASDAQ 100 QDII
    "513180.SS",  # Hang Seng Tech (listed 2021-05-25)
    "510500.SS",  # CSI 500
    "512800.SS",  # banks
    "512880.SS",  # brokers
    "511260.SS",  # 10y treasury
    "510880.SS",  # dividend
    "513500.SS",  # S&P 500 QDII
)

START = "2018-01-02"
END = "2026-08-21"
IS_END = "2021-12-31"
OOS_START = "2022-01-01"
ARTICLE_START = "2018-01-01"
ARTICLE_END = "2024-03-31"
STRESS_MONTHS = (("2024-02-01", "2024-02-29"), ("2026-07-01", "2026-07-31"))

VOL_WINDOW = 250
CORR_WINDOW = 500
MOM_WINDOW = 20
ELIG_BARS = max(VOL_WINDOW, CORR_WINDOW, MOM_WINDOW)
VOL_LO = 0.08
VOL_HI = 0.28
N_CORR = 5
N_HOLD = 2

COST_A = 0.001   # article: 10bp one-way, same-close fill
COST_B = 0.0008  # book:     8bp one-way, T+1 close fill

MARKET = "510300.SS"
EPS_TRADE = 1e-9


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def build_frames():
    panel = load_panel(codes=POOL)
    calendar = sorted(
        set().union(*(pd.DatetimeIndex(panel[c]["dates"]) for c in POOL))
    )
    calendar = pd.DatetimeIndex([d for d in calendar if d <= pd.Timestamp(END)])

    raw = pd.DataFrame(index=calendar, columns=list(POOL), dtype=float)
    for code in POOL:
        series = pd.Series(
            panel[code]["close"], index=pd.DatetimeIndex(panel[code]["dates"])
        )
        raw[code] = series.reindex(calendar)

    filled = raw.ffill()
    bar_counts = raw.notna().cumsum()

    stats_rets = filled.pct_change()
    stats_rets = stats_rets.where(raw.ffill().notna())
    nav_rets = stats_rets.fillna(0.0)
    return calendar, raw, filled, bar_counts, stats_rets, nav_rets


# ---------------------------------------------------------------------------
# Weekly signal (formulas come from openalphas_rp_mom)
# ---------------------------------------------------------------------------
def weekly_signal_indices(calendar, start_ts):
    """Index of the last trading session of each ISO week, on/after start."""
    iso = [(d.isocalendar()[0], d.isocalendar()[1]) for d in calendar]
    signals = []
    for i in range(len(calendar)):
        is_last = i + 1 == len(calendar) or iso[i + 1] != iso[i]
        if is_last and calendar[i] >= start_ts:
            signals.append(i)
    return signals


def compute_target(i, bar_counts, stats_rets, filled):
    """Return (target_weights_or_None, n_survivors) for signal index i."""
    eligible = [
        c for c in POOL if int(bar_counts[c].iloc[i]) >= ELIG_BARS
    ]
    if not eligible:
        return None, 0

    vol_block = stats_rets[eligible].iloc[max(0, i - VOL_WINDOW + 1): i + 1]
    vol = annualized_volatility(vol_block)
    complete = vol_block.notna().sum() >= VOL_WINDOW
    vol = vol[complete[complete].index].dropna()

    survivors_vol = filter_by_volatility(vol, (VOL_LO, VOL_HI))
    survivors = list(survivors_vol.index)
    if len(survivors) < N_CORR:
        return None, len(survivors)

    corr_block = stats_rets[survivors].iloc[max(0, i - CORR_WINDOW + 1): i + 1]
    correlations = mean_absolute_correlation(corr_block).dropna()
    if len(correlations) < N_CORR:
        return None, len(survivors)
    corr5 = correlations.nsmallest(N_CORR, keep="first").index.tolist()

    scores = {}
    for code in corr5:
        closes = filled[code].iloc[i - MOM_WINDOW + 1: i + 1]
        score, _r2 = momentum_score(closes.to_numpy(dtype=float))
        if np.isfinite(score):
            scores[code] = score
    if len(scores) < N_HOLD:
        return None, len(survivors)
    ranked = pd.Series(scores, dtype=float).nlargest(N_HOLD, keep="first")
    weights = inverse_volatility_weights(survivors_vol.loc[ranked.index])
    return {code: float(w) for code, w in weights.items()}, len(survivors)


# ---------------------------------------------------------------------------
# Daily NAV engine
# ---------------------------------------------------------------------------
def run_nav(calendar, nav_rets, start_idx, fills, cost):
    """fills: {calendar index -> target weight dict}.  Returns nav, fill log."""
    n = len(calendar)
    navs = np.ones(n - start_idx, dtype=float)
    holdings = {}
    cash = 1.0
    fill_dates = []
    total_turnover = 0.0

    for i in range(start_idx, n):
        if i > start_idx:
            for code in list(holdings):
                holdings[code] *= 1.0 + float(nav_rets[code].iloc[i])
        nav_i = cash + sum(holdings.values())

        target = fills.get(i)
        if target is not None:
            traded = 0.0
            for code in set(list(target) + list(holdings)):
                traded += abs(target.get(code, 0.0) * nav_i
                              - holdings.get(code, 0.0))
            if traded > EPS_TRADE:
                nav_i -= cost * traded
                total_turnover += traded / nav_i
                holdings = {c: w * nav_i for c, w in target.items()}
                cash = nav_i - sum(holdings.values())
                fill_dates.append(calendar[i])
        navs[i - start_idx] = nav_i

    return navs, fill_dates, total_turnover


# ---------------------------------------------------------------------------
# Metrics (repo conventions: 365.25d CAGR, daily Sharpe * sqrt(252), ddof=1)
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


def window_return(navs, dates, start, end):
    navs = np.asarray(navs, dtype=float)
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        return None
    sub = navs[mask]
    return float(sub[-1] / sub[0] - 1.0)


def count_fills(fill_dates, start, end):
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    return sum(1 for d in fill_dates if lo <= d <= hi)


def pct(value):
    return "n/a" if value is None else "%7.2f%%" % (value * 100.0)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_variant(tag, navs, dates, fill_dates, turnover, bench):
    bench_navs, bench_dates, bench_fills = bench
    print("")
    print("=" * 78)
    print(tag)
    print("=" * 78)
    rows = (
        ("Full    %s .. %s" % (START, END), START, END),
        ("IS      %s .. %s" % (START, IS_END), START, IS_END),
        ("OOS     %s .. %s" % (OOS_START, END), OOS_START, END),
        ("Article %s .. %s" % (ARTICLE_START, ARTICLE_END),
         ARTICLE_START, ARTICLE_END),
    )
    header = ("%-34s | %8s %8s %7s %6s | %8s %8s %7s"
              % ("window", "CAGR", "MDD", "Sharpe", "fills",
                 "benCAGR", "benMDD", "benShp"))
    print(header)
    print("-" * len(header))
    for label, lo, hi in rows:
        strat = sub_perf(navs, dates, lo, hi)
        ben = sub_perf(bench_navs, bench_dates, lo, hi)
        fills = count_fills(fill_dates, lo, hi)
        print("%-34s | %s %s %7.2f %6d | %s %s %7.2f"
              % (label, pct(strat[0]), pct(strat[1]), strat[2], fills,
                 pct(ben[0]), pct(ben[1]), ben[2]))
    print("")
    for lo, hi in STRESS_MONTHS:
        month = lo[:7]
        s_ret = window_return(navs, dates, lo, hi)
        b_ret = window_return(bench_navs, bench_dates, lo, hi)
        print("stress %s : strategy ret=%s   510300 ret=%s"
              % (month, pct(s_ret), pct(b_ret)))
    print("")
    print("fills total=%d   one-way turnover sum=%.1fx   final NAV=%.4f"
          % (len(fill_dates), turnover, float(navs[-1])))
    print("benchmark fills=%d (buy-and-hold entry)" % len(bench_fills))


def save_plot(dates, nav_a, nav_b, bench_a, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # matplotlib genuinely absent on some VMs
        print("plot skipped: %s" % exc)
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(dates, nav_a, label="A article-faithful (Fri close, 10bp)",
            linewidth=1.2)
    ax.plot(dates, nav_b, label="B book-faithful (T+1 close, 8bp)",
            linewidth=1.2)
    ax.plot(dates, bench_a, label="510300 buy-and-hold (A conv.)",
            linewidth=1.0, alpha=0.7)
    ax.set_yscale("log")
    ax.set_title("OpenAlphas RP+Momentum weekly rotator, CN-15 pool "
                 "(RESEARCH ONLY)")
    ax.set_ylabel("NAV (log scale)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print("NAV plot saved to %s" % path)


# ---------------------------------------------------------------------------
def main():
    print("OpenAlphas RP+Momentum CN-15 reproduction -- RESEARCH ONLY")
    print("pool=%d names  eligibility >= %d finite bars  vol band [%.2f, %.2f]"
          % (len(POOL), ELIG_BARS, VOL_LO, VOL_HI))
    print("corr window=%dd  vol window=%dd  momentum=%dd slope*R2  "
          "top%d corr -> top%d mom, inverse-vol weights"
          % (CORR_WINDOW, VOL_WINDOW, MOM_WINDOW, N_CORR, N_HOLD))

    calendar, raw, filled, bar_counts, stats_rets, nav_rets = build_frames()
    start_idx = int(np.searchsorted(calendar.values,
                                    pd.Timestamp(START).to_datetime64()))
    dates = calendar[start_idx:]

    print("")
    print("Data coverage / eligibility onsets (cache truncates at 2500 rows):")
    for code in POOL:
        first_bar = raw[code].first_valid_index()
        reached = bar_counts[code] >= ELIG_BARS
        onset = calendar[int(np.argmax(reached.values))] if reached.any() \
            else None
        print("  %-11s first bar %s   eligible from %s"
              % (code, first_bar.date(),
                 "never (<%d bars)" % ELIG_BARS if onset is None
                 else onset.date()))

    signals = weekly_signal_indices(calendar, pd.Timestamp(START))
    targets = {}
    skips = []
    survivor_counts = []
    for i in signals:
        target, n_surv = compute_target(i, bar_counts, stats_rets, filled)
        survivor_counts.append(n_surv)
        if target is None:
            skips.append((calendar[i].date(), n_surv))
        else:
            targets[i] = target

    print("")
    print("weekly signals=%d   skipped (<%d vol-survivors)=%d   "
          "median survivors=%.0f"
          % (len(signals), N_CORR, len(skips),
             float(np.median(survivor_counts))))
    warmup = [s for s in skips if s[1] == 0]
    true_skips = [s for s in skips if s[1] > 0]
    print("  of which cache warm-up (0 eligible names): %d" % len(warmup))
    print("  of which genuine <%d vol-survivor weeks : %d  %s"
          % (N_CORR, len(true_skips),
             " ".join("%s(n=%d)" % (d, n) for d, n in true_skips)))
    first_trade = min(targets) if targets else None
    if first_trade is not None:
        print("first tradeable signal: %s" % calendar[first_trade].date())

    # Variant A: same-close fill on the signal day.
    fills_a = dict(targets)
    # Variant B: fill at the next session's close.
    fills_b = {i + 1: t for i, t in targets.items() if i + 1 < len(calendar)}

    nav_a, fill_dates_a, turn_a = run_nav(
        calendar, nav_rets, start_idx, fills_a, COST_A)
    nav_b, fill_dates_b, turn_b = run_nav(
        calendar, nav_rets, start_idx, fills_b, COST_B)

    # Benchmarks: 510300 bought at the variant's first possible fill.
    first_signal = signals[0]
    bench_a = run_nav(calendar, nav_rets, start_idx,
                      {first_signal: {MARKET: 1.0}}, COST_A)
    bench_b_idx = first_signal + 1 if first_signal + 1 < len(calendar) \
        else first_signal
    bench_b = run_nav(calendar, nav_rets, start_idx,
                      {bench_b_idx: {MARKET: 1.0}}, COST_B)

    print_variant(
        "Variant A -- article-faithful: Friday same-close fill, 10bp one-way",
        nav_a, dates, fill_dates_a, turn_a,
        (bench_a[0], dates, bench_a[1]))
    print_variant(
        "Variant B -- book-faithful: signal T close, fill T+1 close, "
        "8bp one-way",
        nav_b, dates, fill_dates_b, turn_b,
        (bench_b[0], dates, bench_b[1]))

    print("")
    print("REMINDERS: blog reproduction only; the 52.3 percent blog claim is "
          "NOT a target for this book; the 20d slope is not the frozen 12-1 "
          "momentum; the 15-name pool has no IS charter -- nothing here may "
          "enter ptrade_*.py.")

    plot_dir = "/opt/cursor/artifacts"
    if not os.path.isdir(plot_dir) or not os.access(plot_dir, os.W_OK):
        plot_dir = os.path.join(HERE, "plots")
        if not os.path.isdir(plot_dir):
            os.makedirs(plot_dir)
    save_plot(dates, nav_a, nav_b, bench_a[0],
              os.path.join(plot_dir, "openalphas_cn_nav.png"))

    return {
        "nav_a": nav_a, "nav_b": nav_b, "dates": dates,
        "fills_a": fill_dates_a, "fills_b": fill_dates_b,
    }


if __name__ == "__main__":
    main()
