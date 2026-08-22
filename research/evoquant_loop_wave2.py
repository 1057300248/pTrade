# -*- coding: utf-8 -*-
"""Research-only Wave 2 verifier for ADM.

The three candidate families are evaluated one field at a time.  Each family
winner is frozen on 2018-2021 data before any OOS or stress metric is
calculated.  This module never edits the live strategy.
"""
from __future__ import print_function

import json
import os
import sys

import numpy as np
import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ptrade_adm_etf as strategy
from research.ablate_adm_knobs import (
    LOCKDOWN_DAYS,
    apply_fill,
    build_counts,
    build_snapshot,
    iso_week,
    last_close,
    overlay_crash_needed,
    period_summary,
    stress_summary,
)
from research.etf_panel import load_panel
from research.evoquant_loop import file_sha256


_MODULE_IMPORT_ERRORS = {}
try:
    from research.wave2_crowd import crowd_map_for_index
except ImportError as exc:
    crowd_map_for_index = None
    _MODULE_IMPORT_ERRORS["research.wave2_crowd"] = exc

try:
    from research.wave2_tranche import TrancheBook
except ImportError as exc:
    TrancheBook = None
    _MODULE_IMPORT_ERRORS["research.wave2_tranche"] = exc

try:
    from research.wave2_breadth import apply_breadth_cut
except ImportError as exc:
    apply_breadth_cut = None
    _MODULE_IMPORT_ERRORS["research.wave2_breadth"] = exc


HERE = os.path.dirname(__file__)
GENOME_PATH = os.path.join(HERE, "evoquant_genome_wave2.json")
REPORT_PATH = os.path.join(HERE, "evoquant_candidates_wave2.md")
LIVE_PATH = os.path.join(ROOT, "ptrade_adm_etf.py")

IS_START = "2018-01-02"
IS_END = "2021-12-31"
OOS_START = "2022-01-04"
OOS_END = "2026-08-21"
STRESS_WINDOWS = (
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026-07", "2026-07-01", "2026-07-31"),
)
MARKET = "510300.SS"
UNIVERSE = tuple(list(strategy.RISK) + [strategy.BOND])
VOL_TARGET = 0.16
AUTO_APPLY_LIVE_EDITS = False

FAMILY_FIELDS = {
    "W2-CROWD": "crowding_percentile",
    "W2-TRANCHE": "n_tranches",
    "W2-BREADTH": "breadth_cut",
}
FAMILY_GRIDS = {
    "W2-CROWD": (0.90, 0.95),
    "W2-TRANCHE": (2, 3, 4),
    "W2-BREADTH": (0.25, 0.50, 0.75),
}
FAMILY_ORDER = ("W2-CROWD", "W2-TRANCHE", "W2-BREADTH")


def modules_ready():
    """Return whether all separately-owned Wave 2 modules imported."""
    return not _MODULE_IMPORT_ERRORS


def _require_modules():
    if modules_ready():
        return
    missing = ", ".join(sorted(_MODULE_IMPORT_ERRORS))
    raise ImportError(
        "Wave 2 verifier cannot run; missing Wave 2 modules: %s" % missing
    )


def load_genome(path=GENOME_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        genome = json.load(handle)
    if genome.get("strategy") != "ADM" or int(genome.get("wave", 0)) != 2:
        raise ValueError("Wave 2 genome must declare strategy ADM and wave 2")
    if genome.get("auto_apply_live_edits") is not False:
        raise ValueError("Wave 2 must set auto_apply_live_edits to false")
    return genome


def _candidate_key(family, value):
    if family == "W2-CROWD":
        return "%s-P%02d" % (family, int(round(float(value) * 100.0)))
    if family == "W2-TRANCHE":
        return "%s-N%d" % (family, int(value))
    if family == "W2-BREADTH":
        return "%s-C%02d" % (family, int(round(float(value) * 100.0)))
    raise ValueError("unknown Wave 2 family: %s" % family)


def build_candidates(genome=None):
    """Expand three independent one-field families, never a cross-product."""
    if genome is None:
        genome = load_genome()

    declarations = {
        item["candidate_id"]: item for item in genome["proposed_fields"]
    }
    if set(declarations) != set(FAMILY_ORDER):
        raise ValueError("Wave 2 genome must declare exactly three families")

    candidates = []
    for family in FAMILY_ORDER:
        declaration = declarations[family]
        field = FAMILY_FIELDS[family]
        values = tuple(declaration["is_grid"])
        expected = FAMILY_GRIDS[family]
        if declaration["name"] != field or values != expected:
            raise ValueError("%s grid differs from the frozen protocol" % family)
        if int(declaration["is_grid_size"]) != len(expected):
            raise ValueError("%s grid size differs from the frozen protocol" % family)
        for value in values:
            candidates.append(
                {
                    "family": family,
                    "field": field,
                    "value": value,
                    "key": _candidate_key(family, value),
                }
            )

    declared = int(
        genome["trial_accounting"]["wave2_declared_trials"]
    )
    if declared != 8:
        raise ValueError("Wave 2 genome must declare exactly 8 trials")
    assert len(candidates) == 8
    return candidates


def _validate_config(config):
    required = {"family", "field", "value", "key"}
    if set(config) != required:
        raise ValueError(
            "candidate config must contain only family, field, value, and key"
        )
    family = config["family"]
    if family not in FAMILY_FIELDS:
        raise ValueError("unknown Wave 2 family: %s" % family)
    if config["field"] != FAMILY_FIELDS[family]:
        raise ValueError("candidate field does not match its family")
    if config["value"] not in FAMILY_GRIDS[family]:
        raise ValueError("candidate value is outside its frozen family grid")
    if config["key"] != _candidate_key(family, config["value"]):
        raise ValueError("candidate key does not match family and value")


def freeze_family_winner(results, family=None):
    """Freeze one family's winner using IS fields only."""
    if family is not None:
        eligible = [
            result for result in results
            if result["config"]["family"] == family
        ]
    else:
        eligible = list(results)
        families = {
            result["config"]["family"] for result in eligible
        }
        if len(families) > 1:
            raise ValueError("freeze_family_winner accepts one family at a time")
    if not eligible:
        raise ValueError("cannot freeze a winner from an empty family")
    return max(
        eligible,
        key=lambda result: (
            result["is"]["sharpe"],
            result["is"]["cagr"],
            result["is"]["mdd"],
            -float(result["config"]["value"]),
        ),
    )


def assert_live_file_unchanged(expected_hash, path=LIVE_PATH):
    """Raise if the live ADM source no longer has its initial SHA-256."""
    actual_hash = file_sha256(path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            "live ADM file changed during Wave 2 verifier run: %s" % path
        )
    return actual_hash


def proposed_live_edit(_winners=None):
    """Wave 2 is verification-only and never proposes an automatic edit."""
    return None


def _incumbent_weekly_target(snapshot, lockdown):
    winner = strategy.pick_risk_asset(
        snapshot["scores"],
        snapshot["gates"],
        snapshot["crowds"],
    )
    if lockdown:
        winner = None
    winner_vol = None if winner is None else snapshot["vols"].get(winner)
    return strategy.build_targets(
        winner,
        winner_vol,
        vol_target=VOL_TARGET,
        bond=strategy.BOND,
    )


def _weekly_target(panel, counts, index, snapshot, lockdown, config):
    candidate_snapshot = snapshot
    if config["family"] == "W2-CROWD":
        candidate_snapshot = dict(snapshot)
        candidate_snapshot["crowds"] = crowd_map_for_index(
            panel,
            counts,
            list(strategy.RISK),
            index,
            float(config["value"]),
        )

    if lockdown:
        return strategy.build_targets(
            None, None, vol_target=VOL_TARGET, bond=strategy.BOND
        )

    if config["family"] == "W2-BREADTH":
        breadth_target = apply_breadth_cut(
            candidate_snapshot["gates"],
            float(config["value"]),
        )
        if breadth_target is not None:
            return breadth_target

    return _incumbent_weekly_target(candidate_snapshot, False)


def _load_default_context():
    panel = load_panel(codes=UNIVERSE)
    calendar = np.unique(
        np.concatenate([bars["dates"] for bars in panel.values()])
    )
    counts = build_counts(panel, calendar)
    lower = np.datetime64(IS_START)
    upper = np.datetime64(OOS_END)
    sim = [
        index for index in range(len(calendar))
        if lower <= calendar[index] <= upper
    ]
    if not sim:
        raise RuntimeError("no observations in Wave 2 verifier range")
    return panel, counts, calendar, sim, {}


def run_candidate(
        config,
        panel=None,
        counts=None,
        calendar=None,
        sim=None,
        snapshot_cache=None):
    """Run one and only one Wave 2 family setting."""
    _require_modules()
    _validate_config(config)

    supplied = (panel, counts, calendar, sim)
    if all(value is None for value in supplied):
        panel, counts, calendar, sim, snapshot_cache = _load_default_context()
    elif any(value is None for value in supplied):
        raise ValueError("panel, counts, calendar, and sim must be supplied together")
    elif snapshot_cache is None:
        snapshot_cache = {}

    nav = 1.0
    holdings = {}
    pending = None
    lockdown_left = 0
    last_week = None
    equity = []
    fills = 0
    flattens = 0
    tranche_book = (
        TrancheBook(int(config["value"]))
        if config["family"] == "W2-TRANCHE"
        else None
    )

    def snapshot_for(index):
        if index not in snapshot_cache:
            snapshot_cache[index] = build_snapshot(panel, counts, index)
        return snapshot_cache[index]

    for step, index in enumerate(sim):
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
            nav *= 1.0 + portfolio_return
            if 1.0 + portfolio_return > 1e-9:
                holdings = {
                    code: weight / (1.0 + portfolio_return)
                    for code, weight in grown.items()
                }

        if pending is not None:
            nav, holdings, traded = apply_fill(nav, holdings, pending)
            if traded:
                fills += 1
            pending = None

        flatten = overlay_crash_needed(
            holdings, panel, counts, index
        )
        week = iso_week(calendar[index])
        week_changed = week != last_week
        snap = None
        if flatten or week_changed:
            snap = snapshot_for(index)

        if flatten:
            lockdown_left = LOCKDOWN_DAYS
            defensive_target = strategy.build_targets(
                None, None, vol_target=VOL_TARGET, bond=strategy.BOND
            )
            if tranche_book is not None:
                pending = tranche_book.crash_target(defensive_target)
            else:
                pending = defensive_target
            nav, holdings, traded = apply_fill(nav, holdings, pending)
            if traded:
                fills += 1
            pending = None
            flattens += 1

        if week_changed:
            if tranche_book is not None:
                pending = None
                tranche_book.cancel()

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
                lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)

            target = _weekly_target(
                panel,
                counts,
                index,
                snap,
                lockdown_left > 0,
                config,
            )
            if tranche_book is not None:
                tranche_book.set_weekly_target(holdings, target)
            else:
                pending = target
            last_week = week

        if tranche_book is not None and tranche_book.active():
            pending = tranche_book.next_target()

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    return {
        "equity": np.asarray(equity, dtype=float),
        "fills": fills,
        "flattens": flattens,
    }


def _benchmark_curve(panel, counts, sim):
    closes = np.asarray(
        [
            last_close(panel, counts, MARKET, index)
            for index in sim
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(closes)) or closes[0] <= 0:
        raise RuntimeError("invalid 510300 benchmark series")
    return closes / closes[0]


def promotion_checks(result, benchmark_oos_cagr):
    return {
        "sharpe_decay": (
            result["oos"]["sharpe"]
            >= 0.5 * result["is"]["sharpe"]
        ),
        "2024-02": result["stress"]["2024-02"]["return"] > -0.08,
        "2026-07": result["stress"]["2026-07"]["return"] > -0.10,
        "benchmark": result["oos"]["cagr"] > benchmark_oos_cagr,
    }


def _pct(value):
    return "%.2f%%" % (100.0 * float(value))


def _candidate_table(results):
    lines = [
        "| Candidate | Family field | Value | IS CAGR | IS Sharpe | IS MDD | "
        "OOS CAGR | OOS Sharpe | 2024-02 | 2026-07 | Decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | --- |",
    ]
    for result in results:
        oos = result.get("oos")
        stress = result.get("stress")
        lines.append(
            "| %(key)s | %(field)s | %(value)s | %(is_cagr)s | "
            "%(is_sharpe).2f | %(is_mdd)s | %(oos_cagr)s | "
            "%(oos_sharpe)s | %(feb)s | %(jul)s | %(decision)s |"
            % {
                "key": result["key"],
                "field": result["config"]["field"],
                "value": result["config"]["value"],
                "is_cagr": _pct(result["is"]["cagr"]),
                "is_sharpe": result["is"]["sharpe"],
                "is_mdd": _pct(result["is"]["mdd"]),
                "oos_cagr": _pct(oos["cagr"]) if oos else "—",
                "oos_sharpe": "%.2f" % oos["sharpe"] if oos else "—",
                "feb": _pct(stress["2024-02"]["return"]) if stress else "—",
                "jul": _pct(stress["2026-07"]["return"]) if stress else "—",
                "decision": result["decision"],
            }
        )
    return "\n".join(lines)


def render_report(results, winners, benchmark_oos):
    winner_lines = []
    for family in FAMILY_ORDER:
        result = winners[family]
        failed = [
            name for name, passed in result["checks"].items() if not passed
        ]
        if failed:
            outcome = "REJECTED (failed %s)" % ", ".join(failed)
        else:
            outcome = "PASSED (research verification only)"
        winner_lines.append(
            "- `%s`: `%s` — %s"
            % (family, result["key"], outcome)
        )

    return """# EvoQuant ADM Wave 2 controlled-candidate verification

Generated by `python3 research/evoquant_loop_wave2.py`.

- IS selection: %(is_start)s through %(is_end)s
- Frozen OOS: %(oos_start)s through %(oos_end)s
- Wave 2 declared trials: **N=8**
- Cumulative declared trials: **Wave 1 N=8 + Wave 2 N=8 = N=16**
- Search structure: three independent one-field families; no Cartesian product
- Incumbent controls: vol target 0.16, month gate on, gold overlay on

## Frozen candidate verification

%(table)s

Only each IS-frozen family winner receives OOS and stress metrics. OOS never
re-picks a grid value.

## Family outcomes

%(winners)s

The frozen gates are OOS Sharpe >= 0.5 x IS Sharpe, 2024-02 > -8%%,
2026-07 > -10%%, and OOS CAGR > 510300 OOS CAGR (%(benchmark)s).

## Proposed live edit

None. `auto_apply_live_edits = false`; Wave 2 is research-only.

The verifier never writes `ptrade_adm_etf.py`. Its SHA-256 is checked before
and after the run.
""" % {
        "is_start": IS_START,
        "is_end": IS_END,
        "oos_start": OOS_START,
        "oos_end": OOS_END,
        "table": _candidate_table(results),
        "winners": "\n".join(winner_lines),
        "benchmark": _pct(benchmark_oos["cagr"]),
    }


def run():
    _require_modules()
    live_hash_before = file_sha256(LIVE_PATH)
    genome = load_genome()
    candidates = build_candidates(genome)

    panel = load_panel(codes=UNIVERSE)
    calendar = np.unique(
        np.concatenate([bars["dates"] for bars in panel.values()])
    )
    counts = build_counts(panel, calendar)
    is_lower = np.datetime64(IS_START)
    is_upper = np.datetime64(IS_END)
    oos_upper = np.datetime64(OOS_END)
    is_sim = [
        index for index in range(len(calendar))
        if is_lower <= calendar[index] <= is_upper
    ]
    full_sim = [
        index for index in range(len(calendar))
        if is_lower <= calendar[index] <= oos_upper
    ]
    if not is_sim or not full_sim:
        raise RuntimeError("no observations in Wave 2 verifier range")

    is_dates = pd.DatetimeIndex(calendar[is_sim])
    is_snapshots = {}
    results = []
    for config in candidates:
        simulation = run_candidate(
            config,
            panel,
            counts,
            calendar,
            is_sim,
            is_snapshots,
        )
        results.append(
            {
                "key": config["key"],
                "config": config,
                "is": period_summary(
                    simulation["equity"],
                    is_dates,
                    IS_START,
                    IS_END,
                ),
                "decision": "REJECTED: not IS family winner",
            }
        )

    winners = {
        family: freeze_family_winner(results, family)
        for family in FAMILY_ORDER
    }

    full_dates = pd.DatetimeIndex(calendar[full_sim])
    benchmark = _benchmark_curve(panel, counts, full_sim)
    benchmark_oos = period_summary(
        benchmark, full_dates, OOS_START, OOS_END
    )
    full_snapshots = {}
    for family in FAMILY_ORDER:
        result = winners[family]
        simulation = run_candidate(
            result["config"],
            panel,
            counts,
            calendar,
            full_sim,
            full_snapshots,
        )
        equity = simulation["equity"]
        result["oos"] = period_summary(
            equity, full_dates, OOS_START, OOS_END
        )
        result["stress"] = {
            label: stress_summary(equity, full_dates, start, end)
            for label, start, end in STRESS_WINDOWS
        }
        result["checks"] = promotion_checks(
            result, benchmark_oos["cagr"]
        )
        if all(result["checks"].values()):
            result["decision"] = "PASSED: research verification only"
        else:
            failed = [
                name for name, passed in result["checks"].items()
                if not passed
            ]
            result["decision"] = "REJECTED: failed " + ", ".join(failed)

    report = render_report(results, winners, benchmark_oos)
    assert proposed_live_edit(winners) is None
    assert AUTO_APPLY_LIVE_EDITS is False
    assert_live_file_unchanged(live_hash_before)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write(report)
    assert_live_file_unchanged(live_hash_before)

    print("EvoQuant ADM Wave 2 verifier: %d controlled trials" % len(results))
    print(_candidate_table(results))
    print("wrote %s" % REPORT_PATH)
    return results, winners


if __name__ == "__main__":
    run()
