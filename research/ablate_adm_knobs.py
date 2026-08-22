# -*- coding: utf-8 -*-
"""Leakage-safe, tiny-grid ADM ETF knob ablation.

Selection uses only 2018-01-02 through 2021-12-31.  The winner is frozen
before OOS and stress metrics are calculated.  The live strategy's
252-session lookback, 21-session skip, and five-asset universe remain fixed.
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

from research.etf_panel import load_panel


def _import_scoring():
    import ptrade_adm_etf
    return ptrade_adm_etf


_scoring = _import_scoring()
RISK = _scoring.RISK
BOND = _scoring.BOND
build_targets = _scoring.build_targets
crash_triggered = _scoring.crash_triggered
crowding_points = _scoring.crowding_points
log_returns = _scoring.log_returns
month_gate = _scoring.month_gate
pick_risk_asset = _scoring.pick_risk_asset
realized_vol = _scoring.realized_vol
ts_momentum = _scoring.ts_momentum

REPORT_PATH = os.path.join(os.path.dirname(__file__), "ablate_adm_knobs.md")

IS_START = "2018-01-02"
IS_END = "2021-12-31"
OOS_START = "2022-01-04"
OOS_END = "2026-08-21"
FULL_START = IS_START
FULL_END = OOS_END

LOOKBACK = 252
SKIP = 21
MARKET = "510300.SS"
COST_ONE_WAY = 0.0008
LOCKDOWN_DAYS = 3
STRESS_WINDOWS = (
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026-07", "2026-07-01", "2026-07-31"),
)

# Tiny, a-priori grid.  No lookback or universe knob is permitted.
VOL_TARGETS = (0.10, 0.12, 0.16)
MONTH_GATE_SETTINGS = (True, False)


def build_grid():
    variants = []
    for vol_target in VOL_TARGETS:
        for use_month_gate in MONTH_GATE_SETTINGS:
            variants.append(
                {
                    "key": "VT%02d-%s"
                    % (
                        int(round(vol_target * 100)),
                        "MON" if use_month_gate else "NOMON",
                    ),
                    "vol_target": vol_target,
                    "month_gate": use_month_gate,
                }
            )
    return tuple(variants)


VARIANTS = build_grid()
UNIVERSE = tuple(list(RISK) + [BOND])


def build_counts(panel, calendar):
    counts = {}
    for code, bars in panel.items():
        counts[code] = np.searchsorted(bars["dates"], calendar, side="right")
    return counts


def hist_close(panel, counts, code, index):
    bars = panel.get(code)
    if bars is None:
        return np.array([])
    return bars["close"][: counts[code][index]]


def last_close(panel, counts, code, index):
    bars = panel.get(code)
    if bars is None:
        return None
    count = counts[code][index]
    if count <= 0:
        return None
    return float(bars["close"][count - 1])


# ---------------------------------------------------------------------------
# Frozen ADM scoring; only the month gate can be ablated
# ---------------------------------------------------------------------------
def build_snapshot(panel, counts, index):
    scores = {}
    gates = {}
    crowds = {}
    vols = {}
    closes = {}
    for code in RISK:
        bars = panel[code]
        count = counts[code][index]
        close = bars["close"][:count]
        closes[code] = close
        scores[code] = ts_momentum(
            close, lookback=LOOKBACK, skip=SKIP
        )
        gates[code] = month_gate(close)
        crowds[code] = crowding_points(
            close,
            bars["high"][:count],
            bars["low"][:count],
            bars["volume"][:count],
            bars["amount"][:count],
        )
        vols[code] = realized_vol(close, 20)
    return {
        "scores": scores,
        "gates": gates,
        "crowds": crowds,
        "vols": vols,
        "closes": closes,
        "market_close": closes.get(MARKET, np.array([])),
    }


def weekly_target(snapshot, lockdown, config):
    if config["month_gate"]:
        gates = snapshot["gates"]
    else:
        gates = {code: True for code in RISK}
    winner = pick_risk_asset(
        snapshot["scores"],
        gates,
        snapshot["crowds"],
    )
    if lockdown:
        winner = None
    winner_vol = None if winner is None else snapshot["vols"].get(winner)
    return build_targets(
        winner,
        winner_vol,
        vol_target=config["vol_target"],
        bond=BOND,
    )


# ---------------------------------------------------------------------------
# Portfolio mechanics: T close signal, T+1 close fill, 8bp one way
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target):
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False
    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    new_holdings = {
        code: weight for code, weight in target.items() if weight > 1e-6
    }
    return nav, new_holdings, True


def overlay_crash_needed(holdings, panel, counts, index):
    codes = [MARKET]
    codes.extend(code for code in holdings if code in RISK and code != MARKET)
    for code in codes:
        closes = hist_close(panel, counts, code, index)
        if len(closes) >= 2 and crash_triggered(
            closes, single_day=0.06, three_day=0.08
        ):
            return True
    return False


def iso_week(date64):
    iso = pd.Timestamp(date64).isocalendar()
    return int(iso[0]), int(iso[1])


# ---------------------------------------------------------------------------
# Metrics and IS-only selection
# ---------------------------------------------------------------------------
def perf_summary(navs, dates):
    navs = np.asarray(navs, dtype=float)
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    cagr = float((navs[-1] / navs[0]) ** (1.0 / years) - 1.0)
    peak = np.maximum.accumulate(navs)
    mdd = float(np.min(navs / peak - 1.0))
    returns = np.diff(navs) / navs[:-1]
    std = float(np.std(returns, ddof=1)) if len(returns) > 2 else 0.0
    sharpe = (
        float(np.mean(returns) / std * math.sqrt(252.0))
        if std > 0
        else 0.0
    )
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def period_summary(navs, dates, start, end):
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        raise RuntimeError("not enough observations for %s .. %s" % (start, end))
    return perf_summary(np.asarray(navs)[mask], dates[mask])


def stress_summary(navs, dates, start, end):
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    if int(mask.sum()) < 2:
        raise RuntimeError("not enough observations for %s .. %s" % (start, end))
    selected = np.asarray(navs, dtype=float)[mask]
    total_return = float(selected[-1] / selected[0] - 1.0)
    peak = np.maximum.accumulate(selected)
    mdd = float(np.min(selected / peak - 1.0))
    return {"return": total_return, "mdd": mdd}


def freeze_is_choice(results):
    """Pick the IS Sharpe winner without reading any OOS field."""
    return max(
        results,
        key=lambda result: (
            result["is"]["sharpe"],
            result["is"]["cagr"],
            result["is"]["mdd"],
            int(result["config"]["month_gate"]),
            -result["config"]["vol_target"],
        ),
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def run_variant(panel, counts, calendar, sim, snapshot_cache, config):
    nav = 1.0
    holdings = {}
    pending = None
    lockdown_left = 0
    last_week = None
    equity = []
    fills = 0
    flattens = 0

    def snapshot(index):
        if index not in snapshot_cache:
            snapshot_cache[index] = build_snapshot(panel, counts, index)
        return snapshot_cache[index]

    for step, index in enumerate(sim):
        # 1) Accrue previous close to today's close.
        if step > 0 and holdings:
            previous_index = sim[step - 1]
            portfolio_return = 0.0
            grown = {}
            for code, weight in holdings.items():
                price0 = last_close(panel, counts, code, previous_index)
                price1 = last_close(panel, counts, code, index)
                daily_return = 0.0
                if price0 and price1 and price0 > 0:
                    daily_return = price1 / price0 - 1.0
                portfolio_return += weight * daily_return
                grown[code] = weight * (1.0 + daily_return)
            nav = nav * (1.0 + portfolio_return)
            if 1.0 + portfolio_return > 1e-9:
                holdings = {
                    code: weight / (1.0 + portfolio_return)
                    for code, weight in grown.items()
                }

        # 2) Fill the target generated at the prior close.
        if pending is not None:
            nav, holdings, traded = apply_fill(nav, holdings, pending)
            if traded:
                fills += 1
            pending = None

        # 3) Approximate ADM's intraday crash overlay at the daily close.
        flatten = overlay_crash_needed(
            holdings, panel, counts, index
        )

        # 4) Score only on crash days and ISO-week changes.
        week = iso_week(calendar[index])
        week_changed = week != last_week
        snap = None
        if flatten or week_changed:
            snap = snapshot(index)
        if flatten:
            lockdown_left = LOCKDOWN_DAYS
            nav, holdings, traded = apply_fill(
                nav,
                holdings,
                build_targets(None, None, bond=BOND),
            )
            if traded:
                fills += 1
            flattens += 1
        if week_changed:
            market_close = snap["market_close"]
            market_crash = bool(
                len(market_close) >= 2
                and crash_triggered(
                    market_close, single_day=0.06, three_day=0.08
                )
            )
            if market_crash:
                lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)
            pending = weekly_target(
                snap,
                lockdown_left > 0,
                config,
            )
            last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    return {
        "equity": np.asarray(equity, dtype=float),
        "fills": fills,
        "flattens": flattens,
    }


def _pct(value):
    return "%.2f%%" % (100.0 * value)


def render_table(results):
    lines = [
        "| Spec | vol target | month gate | IS CAGR | IS MDD | IS Sharpe | "
        "OOS CAGR | OOS MDD | OOS Sharpe | 2024-02 Ret/MDD | "
        "2026-07 Ret/MDD | Check |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | --- |",
    ]
    for result in results:
        config = result["config"]
        february = result["stress"]["2024-02"]
        july = result["stress"]["2026-07"]
        key = result["key"] + (" (frozen)" if result["selected"] else "")
        lines.append(
            "| %(key)s | %(vol)s | %(gate)s | %(is_cagr)s | %(is_mdd)s | "
            "%(is_sharpe).2f | %(oos_cagr)s | %(oos_mdd)s | "
            "%(oos_sharpe).2f | %(feb_ret)s / %(feb_mdd)s | "
            "%(jul_ret)s / %(jul_mdd)s | %(check)s |"
            % {
                "key": key,
                "vol": _pct(config["vol_target"]),
                "gate": "ON" if config["month_gate"] else "OFF",
                "is_cagr": _pct(result["is"]["cagr"]),
                "is_mdd": _pct(result["is"]["mdd"]),
                "is_sharpe": result["is"]["sharpe"],
                "oos_cagr": _pct(result["oos"]["cagr"]),
                "oos_mdd": _pct(result["oos"]["mdd"]),
                "oos_sharpe": result["oos"]["sharpe"],
                "feb_ret": _pct(february["return"]),
                "feb_mdd": _pct(february["mdd"]),
                "jul_ret": _pct(july["return"]),
                "jul_mdd": _pct(july["mdd"]),
                "check": "OVERFIT" if result["overfit"] else "OK",
            }
        )
    return "\n".join(lines)


def deployment_verdict(results, frozen):
    failures = sum(1 for result in results if result["overfit"])
    if failures == len(results):
        return (
            "NO DEPLOY: all %d/%d variants fail the OOS Sharpe-decay rule. "
            "ADM is not deployable and RMDC stays primary."
            % (failures, len(results))
        )
    if frozen["overfit"]:
        return (
            "NO DEPLOY: the frozen IS winner fails the OOS Sharpe-decay "
            "rule. OOS alternatives are not used to re-pick; RMDC stays "
            "primary."
        )
    return (
        "DEPLOY: the frozen IS winner passes the specified OOS "
        "Sharpe-decay rule."
    )


def render_report(results, frozen):
    config = frozen["config"]
    recommendation = (
        "%s: vol target %.0f%%, month gate %s"
        % (
            frozen["key"],
            config["vol_target"] * 100.0,
            "ON" if config["month_gate"] else "OFF",
        )
    )
    return """# ADM knob ablation: IS selection, frozen OOS

Generated by `research/ablate_adm_knobs.py`.

- IS selection window: %(is_start)s through %(is_end)s
- OOS reporting window: %(oos_start)s through %(oos_end)s
- Frozen signal: 252-session lookback, 21-session skip
- Frozen universe: 510300, 159915, 513100, 518880, and bond 511010
- Grid: vol target {10%%, 12%%, 16%%} x month gate {ON, OFF}
- Execution: T close signal, T+1 close fill, 8bp one-way cost
- Selection rule fixed before OOS calculation: maximize IS Sharpe; exact
  ties use IS CAGR, less-negative MDD, live-default gate ON, then lower vol
- `OVERFIT`: OOS Sharpe < 0.5 x IS Sharpe
- Stress windows are reported only and never enter selection

## Frozen recommendation

**%(recommendation)s**. This recommendation is selected from IS metrics only;
OOS and stress metrics do not re-rank it.

## IS vs OOS

%(table)s

## Deployment verdict

**%(verdict)s**
""" % {
        "is_start": IS_START,
        "is_end": IS_END,
        "oos_start": OOS_START,
        "oos_end": OOS_END,
        "recommendation": recommendation,
        "table": render_table(results),
        "verdict": deployment_verdict(results, frozen),
    }


def run():
    panel = load_panel(codes=UNIVERSE)
    calendar = np.unique(
        np.concatenate([bars["dates"] for bars in panel.values()])
    )
    counts = build_counts(panel, calendar)
    lower = np.datetime64(FULL_START)
    upper = np.datetime64(FULL_END)
    sim = [
        index
        for index in range(len(calendar))
        if lower <= calendar[index] <= upper
    ]
    if not sim:
        raise RuntimeError("no cached bars in requested research range")
    dates = pd.DatetimeIndex(calendar[sim])

    # Generate all curves and inspect IS metrics only.
    snapshot_cache = {}
    results = []
    for config in VARIANTS:
        simulation = run_variant(
            panel,
            counts,
            calendar,
            sim,
            snapshot_cache,
            config,
        )
        results.append(
            {
                "key": config["key"],
                "config": config,
                "simulation": simulation,
                "is": period_summary(
                    simulation["equity"],
                    dates,
                    IS_START,
                    IS_END,
                ),
            }
        )

    # Freeze the IS Sharpe winner before calculating OOS or stress.
    frozen = freeze_is_choice(results)
    for result in results:
        equity = result["simulation"]["equity"]
        result["selected"] = result is frozen
        result["oos"] = period_summary(
            equity,
            dates,
            OOS_START,
            OOS_END,
        )
        result["stress"] = {}
        for label, start, end in STRESS_WINDOWS:
            result["stress"][label] = stress_summary(
                equity, dates, start, end
            )
        result["overfit"] = (
            result["oos"]["sharpe"] < 0.5 * result["is"]["sharpe"]
        )

    report = render_report(results, frozen)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write(report)

    print(
        "ADM ablation: IS %s..%s; frozen OOS %s..%s"
        % (IS_START, IS_END, OOS_START, OOS_END)
    )
    print(
        "fixed momentum lookback/skip=%d/%d; T+1 close fill; one-way cost %.0fbp"
        % (LOOKBACK, SKIP, COST_ONE_WAY * 1e4)
    )
    print(render_table(results))
    print("frozen recommendation: %s" % frozen["key"])
    print(deployment_verdict(results, frozen))
    print("wrote %s" % REPORT_PATH)
    return results, frozen


if __name__ == "__main__":
    run()
