# -*- coding: utf-8 -*-
"""Leakage-safe, small-grid GEM ETF knob ablation.

The grid is selected only on 2018-01-02 through 2021-12-31.  The selected
specification is frozen before this script calculates or prints any OOS or
stress-window metric.  Signals use the fixed 252-session lookback and
21-session skip from ``ptrade_gem_etf.py``.
"""
from __future__ import print_function

import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _import_scoring():
    """Import the live GEM module after making the repository importable."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import ptrade_gem_etf
    return ptrade_gem_etf


_scoring = _import_scoring()
GROWTH = _scoring.GROWTH
DIVERSIFIER = _scoring.DIVERSIFIER
GOLD = _scoring.GOLD
DIVIDEND = _scoring.DIVIDEND
BONDS = _scoring.BONDS
STATE_ON = _scoring.STATE_ON
STATE_LOCK = _scoring.STATE_LOCK
apply_hysteresis = _scoring.apply_hysteresis
classify_state = _scoring.classify_state
crash_triggered = _scoring.crash_triggered
crowding_points = _scoring.crowding_points
filter_correlated = _scoring.filter_correlated
gold_trend_on = _scoring.gold_trend_on
inverse_vol_weights = _scoring.inverse_vol_weights
log_returns = _scoring.log_returns
realized_vol = _scoring.realized_vol
scale_to_vol_target = _scoring.scale_to_vol_target
trailing_stop_hit = _scoring.trailing_stop_hit
ts_momentum = _scoring.ts_momentum

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "ablate_gem_knobs.md")

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
TRAIL_PCT = 0.22
LOCKDOWN_DAYS = 3
CORR_LIMIT = 0.70
STRESS_WINDOWS = (
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026-07", "2026-07-01", "2026-07-31"),
)

# Small, a-priori grid.  Lookback and skip deliberately do not appear here.
VOL_TARGETS = (0.12, 0.18, 0.22)
GROWTH_COUNTS = (1, 2)
OFFENSE_GROWTH_WEIGHTS = (0.70, 0.80)


def build_grid():
    grid = []
    for vol_target in VOL_TARGETS:
        for n_growth in GROWTH_COUNTS:
            for offense_growth in OFFENSE_GROWTH_WEIGHTS:
                grid.append(
                    {
                        "key": "VT%02d-N%d-G%02d"
                        % (
                            int(round(vol_target * 100)),
                            n_growth,
                            int(round(offense_growth * 100)),
                        ),
                        "vol_target": vol_target,
                        "n_growth": n_growth,
                        "offense_growth": offense_growth,
                    }
                )
    return tuple(grid)


VARIANTS = build_grid()


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
def load_panel():
    panel = {}
    for name in sorted(os.listdir(CACHE_DIR)):
        if not name.endswith(".parquet"):
            continue
        code = name[: -len(".parquet")]
        frame = pd.read_parquet(os.path.join(CACHE_DIR, name))
        frame = (
            frame.dropna(subset=["close"])
            .sort_values("date")
            .drop_duplicates("date")
        )
        close = frame["close"].to_numpy(dtype=float)
        volume = frame["volume"].to_numpy(dtype=float)
        amount = frame["amount"].to_numpy(dtype=float)
        amount = np.where(np.isfinite(amount), amount, close * volume)
        panel[code] = {
            "dates": frame["date"].to_numpy(dtype="datetime64[ns]"),
            "high": frame["high"].to_numpy(dtype=float),
            "low": frame["low"].to_numpy(dtype=float),
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    return panel


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
# GEM scoring and target construction
# ---------------------------------------------------------------------------
def dual_eligible_frozen(closes):
    """Apply GEM's dual gate with the explicitly frozen 252/21 signal."""
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) < 120:
        return False
    return bool(
        ts_momentum(closes, lookback=LOOKBACK, skip=SKIP) > 0
        and closes[-1] > float(np.mean(closes[-120:]))
    )


def build_snapshot(panel, counts, pool, index):
    scores = {}
    dual = {}
    vols = {}
    returns60 = {}
    crowding = {}
    closes = {}
    for code in pool:
        bars = panel[code]
        count = counts[code][index]
        close = bars["close"][:count]
        if len(close) < 61:
            continue
        closes[code] = close
        scores[code] = ts_momentum(close, lookback=LOOKBACK, skip=SKIP)
        dual[code] = dual_eligible_frozen(close)
        vols[code] = realized_vol(close, 20)
        returns60[code] = log_returns(close)[-60:]
        crowding[code] = crowding_points(
            close,
            bars["high"][:count],
            bars["low"][:count],
            bars["volume"][:count],
            bars["amount"][:count],
        )
    return {
        "scores": scores,
        "dual": dual,
        "vols": vols,
        "ret60": returns60,
        "crowd": crowding,
        "closes": closes,
        "market_close": closes.get(MARKET, np.array([])),
    }


def select_growth(snapshot, held):
    held = set(held or [])
    ranked = []
    for code in GROWTH:
        if not snapshot["dual"].get(code, False):
            continue
        if snapshot["crowd"].get(code, 0) >= 4 and code not in held:
            continue
        score = snapshot["scores"].get(code)
        if score is not None:
            ranked.append((code, float(score)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    ordered = [code for code, _score in ranked]
    return filter_correlated(ordered, snapshot["ret60"], CORR_LIMIT)


def _above_ma(closes, days):
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) < int(days):
        return False
    return bool(closes[-1] > float(np.mean(closes[-int(days):])))


def _rank_available(codes, snapshot):
    available = [code for code in codes if code in snapshot["scores"]]
    available.sort(
        key=lambda code: float(snapshot["scores"].get(code, -1e18)),
        reverse=True,
    )
    return available


def select_diversifiers(snapshot):
    gold_on = []
    for code in GOLD:
        closes = snapshot["closes"].get(code)
        if closes is not None and gold_trend_on(closes):
            gold_on.append(code)
    if gold_on:
        return _rank_available(gold_on, snapshot)[:2]

    dividend_on = []
    for code in DIVIDEND:
        closes = snapshot["closes"].get(code)
        if closes is not None and _above_ma(closes, 120):
            dividend_on.append(code)
    if dividend_on:
        return _rank_available(dividend_on, snapshot)[:2]
    return _rank_available(BONDS, snapshot)[:2]


def build_variant_targets(state, growth_ranked, div_ranked, vol_map, config):
    """Fork the live target builder only for n_growth and offense sleeve."""
    growth_weight, div_weight, cash_weight = _scoring.SLEEVE_WEIGHTS[state]
    if state == STATE_ON:
        growth_weight = config["offense_growth"]
        cash_weight = 0.05
        div_weight = 1.0 - growth_weight - cash_weight
    growth_ranked = list(growth_ranked or [])
    div_ranked = list(div_ranked or [])
    if state == STATE_LOCK:
        growth_ranked = []
        growth_weight = 0.0

    growth_pick = growth_ranked[: config["n_growth"]]
    div_pick = div_ranked[:2]
    weights = {}
    if growth_pick and growth_weight > 0:
        sleeve = inverse_vol_weights(growth_pick, vol_map, cap=1.0)
        for code, weight in sleeve.items():
            weights[code] = float(weight) * growth_weight
    if div_pick and div_weight > 0:
        sleeve = inverse_vol_weights(div_pick, vol_map, cap=1.0)
        for code, weight in sleeve.items():
            weights[code] = (
                weights.get(code, 0.0) + float(weight) * div_weight
            )
    scaled, _scale = scale_to_vol_target(
        weights, vol_map, target=config["vol_target"]
    )
    return scaled


def weekly_target(snapshot, holdings, lockdown, config):
    growth_available = [
        code for code in GROWTH if code in snapshot["dual"]
    ]
    if growth_available:
        positive = sum(
            1
            for code in growth_available
            if snapshot["dual"].get(code, False)
        )
        breadth = float(positive) / float(len(growth_available))
    else:
        breadth = 0.0
    market_close = snapshot["market_close"]
    vol300 = (
        0.0 if len(market_close) == 0 else realized_vol(market_close, 20)
    )
    state = classify_state(breadth, vol300, lockdown)

    current_held = list(holdings)
    growth_ranked = select_growth(snapshot, current_held)
    div_ranked = select_diversifiers(snapshot)
    current_growth = [
        code for code in current_held if code in growth_ranked
    ]
    current_div = [code for code in current_held if code in div_ranked]
    stable_growth = apply_hysteresis(
        current_growth,
        growth_ranked[: config["n_growth"]],
        snapshot["scores"],
        1.15,
    )
    stable_div = apply_hysteresis(
        current_div,
        div_ranked[:2],
        snapshot["scores"],
        1.15,
    )
    return build_variant_targets(
        state,
        stable_growth,
        stable_div,
        snapshot["vols"],
        config,
    )


def flatten_target(snapshot, config):
    return build_variant_targets(
        STATE_LOCK,
        [],
        select_diversifiers(snapshot),
        snapshot["vols"],
        config,
    )


# ---------------------------------------------------------------------------
# Portfolio mechanics: T close signal, T+1 close fill, 8bp one way
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target, high_water, panel, counts, index):
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False

    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    new_holdings = {
        code: weight for code, weight in target.items() if weight > 1e-6
    }
    for code in list(high_water):
        if code not in new_holdings:
            high_water.pop(code)
    for code in new_holdings:
        if code not in GROWTH:
            continue
        price = last_close(panel, counts, code, index)
        if price is not None:
            water = high_water.get(code)
            if water is None or price > water:
                high_water[code] = price
    return nav, new_holdings, True


def overlay_flatten_needed(holdings, high_water, panel, counts, index):
    market_hist = hist_close(panel, counts, MARKET, index)
    triggered = bool(
        len(market_hist) >= 2
        and crash_triggered(
            market_hist, single_day=0.06, three_day=0.08
        )
    )
    for code in list(holdings):
        if code not in GROWTH:
            continue
        closes = hist_close(panel, counts, code, index)
        if len(closes) == 0:
            continue
        price = float(closes[-1])
        water = high_water.get(code)
        if water is None or price > water:
            high_water[code] = price
        elif trailing_stop_hit(price, water, TRAIL_PCT):
            triggered = True
    return triggered


def iso_week(date64):
    iso = pd.Timestamp(date64).isocalendar()
    return int(iso[0]), int(iso[1])


# ---------------------------------------------------------------------------
# Metrics and anti-overfit selection
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
    """Select without accessing OOS or stress metrics."""
    return max(
        results,
        key=lambda result: (
            result["is"]["sharpe"],
            result["is"]["cagr"],
            result["is"]["mdd"],
            -result["config"]["vol_target"],
            -result["config"]["n_growth"],
            -result["config"]["offense_growth"],
        ),
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def run_variant(panel, counts, calendar, sim, pool, snapshot_cache, config):
    nav = 1.0
    holdings = {}
    pending = None
    high_water = {}
    lockdown_left = 0
    last_week = None
    equity = []
    fills = 0
    flattens = 0

    def snapshot(index):
        if index not in snapshot_cache:
            snapshot_cache[index] = build_snapshot(
                panel, counts, pool, index
            )
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
            nav, holdings, traded = apply_fill(
                nav,
                holdings,
                pending,
                high_water,
                panel,
                counts,
                index,
            )
            if traded:
                fills += 1
            pending = None

        # 3) Approximate GEM's intraday crash/trailing overlay at daily close.
        flatten = overlay_flatten_needed(
            holdings, high_water, panel, counts, index
        )

        # 4) Score only on flatten days and ISO-week changes.
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
                flatten_target(snap, config),
                high_water,
                panel,
                counts,
                index,
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
                holdings,
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
        "| Spec | vol target | growth names | offense G/D/C | "
        "IS CAGR | IS MDD | IS Sharpe | OOS CAGR | OOS MDD | OOS Sharpe | "
        "2024-02 Ret/MDD | 2026-07 Ret/MDD | Check |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | --- |",
    ]
    for result in results:
        config = result["config"]
        february = result["stress"]["2024-02"]
        july = result["stress"]["2026-07"]
        key = result["key"] + (" (frozen)" if result["selected"] else "")
        offense_div = 0.95 - config["offense_growth"]
        lines.append(
            "| %(key)s | %(vol)s | %(names)d | %(offense)s | "
            "%(is_cagr)s | %(is_mdd)s | %(is_sharpe).2f | "
            "%(oos_cagr)s | %(oos_mdd)s | %(oos_sharpe).2f | "
            "%(feb_ret)s / %(feb_mdd)s | %(jul_ret)s / %(jul_mdd)s | "
            "%(check)s |"
            % {
                "key": key,
                "vol": _pct(config["vol_target"]),
                "names": config["n_growth"],
                "offense": "%d/%d/5"
                % (
                    int(round(config["offense_growth"] * 100)),
                    int(round(offense_div * 100)),
                ),
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


def render_report(results, frozen):
    config = frozen["config"]
    recommendation = (
        "%s: vol target %.0f%%, %d growth name(s), offense G/D/C %.0f/%.0f/5"
        % (
            frozen["key"],
            config["vol_target"] * 100.0,
            config["n_growth"],
            config["offense_growth"] * 100.0,
            (0.95 - config["offense_growth"]) * 100.0,
        )
    )
    overfit_count = sum(1 for result in results if result["overfit"])
    if frozen["overfit"]:
        oos_verdict = (
            "%d/%d variants are flagged `OVERFIT`, including the frozen IS "
            "winner. The frozen spec remains the required IS-only choice, "
            "but this OOS test does not support deploying any grid variant."
            % (overfit_count, len(results))
        )
    else:
        oos_verdict = (
            "%d/%d variants are flagged `OVERFIT`; the frozen IS winner "
            "passes the specified OOS Sharpe-decay check."
            % (overfit_count, len(results))
        )
    return """# GEM knob ablation: IS selection, frozen OOS

Generated by `research/ablate_gem_knobs.py`.

- IS selection window: %(is_start)s through %(is_end)s
- OOS reporting window: %(oos_start)s through %(oos_end)s
- Frozen signal: 252-session lookback, 21-session skip
- Grid: vol target {12%%, 18%%, 22%%} x growth names {1, 2} x offense
  growth sleeve {70%%, 80%%}
- 70%% offense growth uses G/D/C 70/25/5; 80%% uses 80/15/5
- Execution: T close signal, T+1 close fill, 8bp one-way cost
- Selection rule fixed before OOS calculation: maximize IS Sharpe, then IS
  CAGR, then less-negative IS MDD, then lower vol/name/sleeve settings
- `OVERFIT`: OOS Sharpe < 0.5 x IS Sharpe
- Stress windows are reported only and never enter selection

## Frozen recommendation

**%(recommendation)s**. This recommendation is selected from IS metrics only;
the OOS and stress results do not re-rank it.

## IS vs OOS

%(table)s

## OOS diagnostic

%(oos_verdict)s
""" % {
        "is_start": IS_START,
        "is_end": IS_END,
        "oos_start": OOS_START,
        "oos_end": OOS_END,
        "recommendation": recommendation,
        "table": render_table(results),
        "oos_verdict": oos_verdict,
    }


def run():
    panel = load_panel()
    pool = [
        code
        for code in dict.fromkeys(list(GROWTH) + list(DIVERSIFIER))
        if code in panel
    ]
    if MARKET not in panel:
        raise RuntimeError("market data missing for %s" % MARKET)
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

    # Generate curves and inspect IS metrics only.
    snapshot_cache = {}
    results = []
    for config in VARIANTS:
        simulation = run_variant(
            panel,
            counts,
            calendar,
            sim,
            pool,
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

    # Freeze the winner before calculating any OOS or stress metric.
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
        "GEM ablation: IS %s..%s; frozen OOS %s..%s"
        % (IS_START, IS_END, OOS_START, OOS_END)
    )
    print(
        "fixed momentum lookback/skip=%d/%d; T+1 close fill; one-way cost %.0fbp"
        % (LOOKBACK, SKIP, COST_ONE_WAY * 1e4)
    )
    print(render_table(results))
    print("frozen recommendation: %s" % frozen["key"])
    print("wrote %s" % REPORT_PATH)
    return results, frozen


if __name__ == "__main__":
    run()
