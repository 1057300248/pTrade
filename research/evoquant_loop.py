# -*- coding: utf-8 -*-
"""Local, research-only EvoQuant-style verifier for ADM.

This module searches a deliberately tiny, typed candidate set. It freezes one
winner using 2018-2021 metrics before calculating 2022-2026 and stress-window
metrics. It never imports or writes through PTrade lifecycle functions and
never modifies ptrade_adm_etf.py.
"""
from __future__ import print_function

import hashlib
import itertools
import json
import math
import os
import re
import sys

import numpy as np
import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ptrade_adm_etf as strategy
from research import ablate_adm_knobs as engine
from research.etf_panel import load_panel


HERE = os.path.dirname(__file__)
GENOME_PATH = os.path.join(HERE, "evoquant_genome_adm.json")
REPORT_PATH = os.path.join(HERE, "evoquant_candidates.md")
CONTROL_REPORT_PATH = os.path.join(HERE, "backtest_adm_report.md")
LIVE_PATH = os.path.join(ROOT, "ptrade_adm_etf.py")

IS_START = "2018-01-02"
IS_END = "2021-12-31"
OOS_START = "2022-01-04"
OOS_END = "2026-08-21"
STRESS_WINDOWS = (
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026-07", "2026-07-01", "2026-07-31"),
)
GOLD = "518880.SS"
MARKET = "510300.SS"
UNIVERSE = tuple(list(strategy.RISK) + [strategy.BOND])


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_genome(path=GENOME_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        genome = json.load(handle)
    if genome.get("strategy") != "ADM":
        raise ValueError("genome strategy must be ADM")
    return genome


def layer_map(genome):
    return {layer["name"]: layer for layer in genome["layers"]}


def build_candidates(genome):
    """Expand only the three explicitly mutable typed layers."""
    layers = layer_map(genome)
    vol_values = layers["allocation.vol_target"]["candidate_values"]
    month_values = layers["signal.month_gate"]["candidate_values"]
    gold_values = layers["universe.gold_overlay"]["candidate_values"]
    candidates = []
    for vol_target, month_gate, gold_overlay in itertools.product(
            vol_values, month_values, gold_values):
        key = "VT%02d-%s-%s" % (
            int(round(float(vol_target) * 100.0)),
            "MON" if month_gate else "NOMON",
            "GOLD" if gold_overlay else "NOGOLD",
        )
        candidates.append(
            {
                "key": key,
                "vol_target": float(vol_target),
                "month_gate": bool(month_gate),
                "gold_overlay": bool(gold_overlay),
            }
        )
    maximum = int(genome["search"]["maximum_candidates"])
    if len(candidates) > maximum:
        raise RuntimeError(
            "candidate count %d exceeds declared maximum %d"
            % (len(candidates), maximum)
        )
    if len(candidates) != int(genome["search"]["declared_trials"]):
        raise RuntimeError("expanded candidate count differs from declared N")
    return candidates


def weekly_target(snapshot, lockdown, config):
    if config["month_gate"]:
        gates = dict(snapshot["gates"])
    else:
        gates = {code: True for code in strategy.RISK}
    if not config["gold_overlay"]:
        gates[GOLD] = False
    winner = strategy.pick_risk_asset(
        snapshot["scores"],
        gates,
        snapshot["crowds"],
    )
    if lockdown:
        winner = None
    winner_vol = None if winner is None else snapshot["vols"].get(winner)
    return strategy.build_targets(
        winner,
        winner_vol,
        vol_target=config["vol_target"],
        bond=strategy.BOND,
    )


def run_candidate(panel, counts, calendar, sim, snapshot_cache, config):
    """Thin clone of the frozen ADM T+1 engine with typed layer switches."""
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
            snapshot_cache[index] = engine.build_snapshot(
                panel, counts, index)
        return snapshot_cache[index]

    for step, index in enumerate(sim):
        if step > 0 and holdings:
            previous_index = sim[step - 1]
            portfolio_return = 0.0
            grown = {}
            for code, weight in holdings.items():
                price0 = engine.last_close(
                    panel, counts, code, previous_index)
                price1 = engine.last_close(panel, counts, code, index)
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

        if pending is not None:
            nav, holdings, traded = engine.apply_fill(
                nav, holdings, pending)
            if traded:
                fills += 1
            pending = None

        flatten = engine.overlay_crash_needed(
            holdings, panel, counts, index)
        week = engine.iso_week(calendar[index])
        week_changed = week != last_week
        snap = None
        if flatten or week_changed:
            snap = snapshot(index)
        if flatten:
            lockdown_left = engine.LOCKDOWN_DAYS
            nav, holdings, traded = engine.apply_fill(
                nav,
                holdings,
                strategy.build_targets(
                    None, None, bond=strategy.BOND),
            )
            if traded:
                fills += 1
            flattens += 1
        if week_changed:
            market_close = snap["market_close"]
            market_crash = bool(
                len(market_close) >= 2
                and strategy.crash_triggered(
                    market_close,
                    single_day=0.06,
                    three_day=0.08,
                )
            )
            if market_crash:
                lockdown_left = max(
                    lockdown_left, engine.LOCKDOWN_DAYS)
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


def freeze_is_winner(results):
    """Select without reading any OOS or stress field."""
    incumbent_vol = 0.16
    return max(
        results,
        key=lambda result: (
            result["is"]["sharpe"],
            result["is"]["cagr"],
            result["is"]["mdd"],
            int(result["config"]["month_gate"]),
            int(result["config"]["gold_overlay"]),
            -abs(result["config"]["vol_target"] - incumbent_vol),
        ),
    )


def benchmark_curve(panel, counts, sim):
    closes = np.asarray(
        [
            engine.last_close(panel, counts, MARKET, index)
            for index in sim
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(closes)) or closes[0] <= 0:
        raise RuntimeError("invalid 510300 benchmark series")
    return closes / closes[0]


def parse_percent(value):
    value = value.strip().replace("%", "").replace("+", "")
    value = value.replace("−", "-")
    return float(value) / 100.0


def load_report_controls(path=CONTROL_REPORT_PATH):
    """Read RMDC controls from the split-adjusted consolidated report."""
    controls = {}
    if not os.path.isfile(path):
        return controls
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not cells:
                continue
            label = cells[0]
            if label not in ("RMDC", "510300 买入持有"):
                continue
            if len(cells) < 12:
                continue
            try:
                controls[label] = {
                    "full": {
                        "cagr": parse_percent(cells[1]),
                        "mdd": parse_percent(cells[2]),
                        "sharpe": float(cells[3]),
                    },
                    "is": {
                        "cagr": parse_percent(cells[4]),
                        "sharpe": float(cells[5]),
                    },
                    "oos": {
                        "cagr": parse_percent(cells[6]),
                        "mdd": parse_percent(cells[7]),
                        "sharpe": float(cells[8]),
                    },
                    "stress": {
                        "2024-02": parse_percent(cells[9]),
                        "2026-07": parse_percent(cells[10]),
                    },
                }
            except (ValueError, IndexError):
                continue
    return controls


def promotion_checks(result, benchmark_oos_cagr):
    checks = {
        "sharpe_decay": (
            result["oos"]["sharpe"]
            >= 0.5 * result["is"]["sharpe"]
        ),
        "2024-02": result["stress"]["2024-02"]["return"] > -0.08,
        "2026-07": result["stress"]["2026-07"]["return"] > -0.10,
        "benchmark": result["oos"]["cagr"] > benchmark_oos_cagr,
    }
    return checks


def rejection_reason(result):
    failed = [
        name for name, passed in result["checks"].items() if not passed
    ]
    if failed:
        return "failed " + ", ".join(failed)
    return "not IS winner"


def pct(value):
    return "%.2f%%" % (100.0 * float(value))


def candidate_table(results):
    lines = [
        "| Candidate | IS CAGR | IS Sharpe | OOS CAGR | OOS Sharpe | "
        "2024-02 | 2026-07 | Decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        lines.append(
            "| %(key)s | %(is_cagr)s | %(is_sharpe).2f | %(oos_cagr)s | "
            "%(oos_sharpe).2f | %(feb)s | %(jul)s | %(decision)s |"
            % {
                "key": result["key"],
                "is_cagr": pct(result["is"]["cagr"]),
                "is_sharpe": result["is"]["sharpe"],
                "oos_cagr": pct(result["oos"]["cagr"]),
                "oos_sharpe": result["oos"]["sharpe"],
                "feb": pct(result["stress"]["2024-02"]["return"]),
                "jul": pct(result["stress"]["2026-07"]["return"]),
                "decision": result["decision"],
            }
        )
    return "\n".join(lines)


def deflated_note(selected, trial_count, oos_observations):
    """Transparent trial-count haircut; not a formal dependent-trial DSR."""
    sharpe = float(selected["oos"]["sharpe"])
    z_score = sharpe * math.sqrt(float(oos_observations) / 252.0)
    one_sided_p = 0.5 * math.erfc(z_score / math.sqrt(2.0))
    adjusted_p = min(1.0, one_sided_p * float(trial_count))
    return (
        "N=%d declared trials. A simple one-sided normal Sharpe test gives "
        "z=%.2f, raw p=%.3f and Bonferroni p=%.3f for the frozen winner. "
        "This is a conservative trial-count note, not a formal Bailey DSR: "
        "the eight candidates are strongly dependent, so an iid DSR would "
        "be false precision."
        % (trial_count, z_score, one_sided_p, adjusted_p)
    )


def proposed_edit(selected, incumbent):
    dimensions = ("vol_target", "month_gate", "gold_overlay")
    if all(
            selected["config"][name] == incumbent[name]
            for name in dimensions):
        return (
            "None. The IS winner is the incumbent typed genome; no live "
            "strategy edit is proposed."
        )
    changes = []
    for name in dimensions:
        old = incumbent[name]
        new = selected["config"][name]
        if old != new:
            changes.append("%s: %s -> %s" % (name, old, new))
    return (
        "Research proposal only (not auto-applied): "
        + "; ".join(changes)
        + ". A human review is required before any live-file edit."
    )


def render_report(results, selected, controls, benchmark_metrics,
                  genome, dates):
    incumbent_config = {
        "vol_target": 0.16,
        "month_gate": True,
        "gold_overlay": True,
    }
    incumbent = next(
        result for result in results
        if all(
            result["config"][name] == incumbent_config[name]
            for name in incumbent_config)
    )
    rmdc = controls.get("RMDC")
    diagnoses = [
        "Incumbent ADM OOS CAGR is %s with Sharpe %.2f; 510300 OOS "
        "CAGR is %s with Sharpe %.2f."
        % (
            pct(incumbent["oos"]["cagr"]),
            incumbent["oos"]["sharpe"],
            pct(benchmark_metrics["cagr"]),
            benchmark_metrics["sharpe"],
        )
    ]
    if rmdc:
        diagnoses.append(
            "RMDC remains the defensive control: OOS CAGR %s, Sharpe %.2f "
            "and 2026-07 %s versus incumbent ADM %s, %.2f and %s."
            % (
                pct(rmdc["oos"]["cagr"]),
                rmdc["oos"]["sharpe"],
                pct(rmdc["stress"]["2026-07"]),
                pct(incumbent["oos"]["cagr"]),
                incumbent["oos"]["sharpe"],
                pct(incumbent["stress"]["2026-07"]["return"]),
            )
        )
    diagnoses.append(
        "Stress windows are pass/fail verification only; neither window "
        "participates in candidate generation or IS selection."
    )
    diagnoses.append(
        "No lookback, skip, crowding, crash, lockdown, cost, universe or "
        "execution parameter is searched."
    )
    diagnosis_text = "\n".join("- " + item for item in diagnoses)

    selected_failures = [
        key for key, passed in selected["checks"].items() if not passed
    ]
    if selected_failures:
        outcome = (
            "**REJECTED**: the IS winner `%s` fails frozen OOS gates: %s."
            % (selected["key"], ", ".join(selected_failures))
        )
    else:
        outcome = (
            "**PROMOTED (research verification only)**: `%s` wins IS and "
            "passes every frozen OOS gate." % selected["key"]
        )

    oos_count = int(
        (
            (dates >= pd.Timestamp(OOS_START))
            & (dates <= pd.Timestamp(OOS_END))
        ).sum()
    )
    note = deflated_note(
        selected,
        int(genome["search"]["declared_trials"]),
        oos_count,
    )
    return """# EvoQuant ADM controlled-candidate verification

Generated by `python3 research/evoquant_loop.py`.

- Data: split-adjusted bars from `research.etf_panel.load_panel`
- IS selection: %(is_start)s through %(is_end)s
- Frozen OOS: %(oos_start)s through %(oos_end)s
- Candidate count: **%(trials)d**
- Frozen signal: 252/21 TSMOM with 126/5 fallback
- Candidate dimensions only: vol {0.12, 0.16}, month gate {on, off},
  gold overlay {on, off}
- Explicit exclusion: no lookback grid and no targeting of 2026-07

## Diagnoses

%(diagnoses)s

## Frozen candidate verification

%(table)s

%(outcome)s

## Promotion gates

The frozen IS winner must satisfy all four: OOS Sharpe >= 0.5 x IS Sharpe,
2024-02 return > -8%%, 2026-07 return > -10%%, and OOS CAGR above 510300.
Any IS winner that fails one is rejected; OOS alternatives are never used to
re-pick.

## Deflated-Sharpe trial note

%(deflated)s

## Proposed live edit

%(proposal)s

This verifier never writes `ptrade_adm_etf.py`; the live-file SHA-256 is
checked before and after the run.
""" % {
        "is_start": IS_START,
        "is_end": IS_END,
        "oos_start": OOS_START,
        "oos_end": OOS_END,
        "trials": int(genome["search"]["declared_trials"]),
        "diagnoses": diagnosis_text,
        "table": candidate_table(results),
        "outcome": outcome,
        "deflated": note,
        "proposal": proposed_edit(selected, incumbent_config),
    }


def run():
    live_hash_before = file_sha256(LIVE_PATH)
    genome = load_genome()
    candidates = build_candidates(genome)
    panel = load_panel(codes=UNIVERSE)
    calendar = np.unique(
        np.concatenate([bars["dates"] for bars in panel.values()])
    )
    counts = engine.build_counts(panel, calendar)
    lower = np.datetime64(IS_START)
    upper = np.datetime64(OOS_END)
    sim = [
        index for index in range(len(calendar))
        if lower <= calendar[index] <= upper
    ]
    if not sim:
        raise RuntimeError("no observations in verifier range")
    dates = pd.DatetimeIndex(calendar[sim])
    snapshots = {}

    results = []
    for config in candidates:
        simulation = run_candidate(
            panel,
            counts,
            calendar,
            sim,
            snapshots,
            config,
        )
        results.append(
            {
                "key": config["key"],
                "config": config,
                "simulation": simulation,
                "is": engine.period_summary(
                    simulation["equity"],
                    dates,
                    IS_START,
                    IS_END,
                ),
            }
        )

    selected = freeze_is_winner(results)
    benchmark = benchmark_curve(panel, counts, sim)
    benchmark_oos = engine.period_summary(
        benchmark, dates, OOS_START, OOS_END)

    for result in results:
        equity = result["simulation"]["equity"]
        result["oos"] = engine.period_summary(
            equity, dates, OOS_START, OOS_END)
        result["stress"] = {
            label: engine.stress_summary(equity, dates, start, end)
            for label, start, end in STRESS_WINDOWS
        }
        result["checks"] = promotion_checks(
            result, benchmark_oos["cagr"])
        if result is selected and all(result["checks"].values()):
            result["decision"] = "PROMOTED"
        elif result is selected:
            result["decision"] = (
                "REJECTED: " + rejection_reason(result))
        else:
            result["decision"] = "REJECTED: not IS winner"

    controls = load_report_controls()
    report = render_report(
        results,
        selected,
        controls,
        benchmark_oos,
        genome,
        dates,
    )
    if file_sha256(LIVE_PATH) != live_hash_before:
        raise RuntimeError("live ADM file changed during verifier run")
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write(report)

    print("EvoQuant ADM verifier: %d controlled trials" % len(results))
    print(candidate_table(results))
    print("frozen IS winner: %s" % selected["key"])
    print("wrote %s" % REPORT_PATH)
    return results, selected


if __name__ == "__main__":
    run()
