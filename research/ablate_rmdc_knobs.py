# -*- coding: utf-8 -*-
"""Small RMDC parameter ablation using the research backtest mechanics.

Data and execution assumptions match ``research/backtest_rmdc_etf.py``:
signals are computed at T close, targets fill at T+1 close, and each
one-way trade costs 8bp.  Pure scoring functions are imported from
``ptrade_rmdc_etf.py``; variant-only gates and target construction live
in this research file.
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
STATE_OFF = _scoring.STATE_OFF
STATE_LOCK = _scoring.STATE_LOCK
build_targets = _scoring.build_targets
classify_state = _scoring.classify_state
crash_triggered = _scoring.crash_triggered
crowding_points = _scoring.crowding_points
filter_correlated = _scoring.filter_correlated
growth_breadth = _scoring.growth_breadth
inverse_vol_weights = _scoring.inverse_vol_weights
log_returns = _scoring.log_returns
median_vol = _scoring.median_vol
mean_pairwise_corr = _scoring.mean_pairwise_corr
period_return = _scoring.period_return
realized_vol = _scoring.realized_vol
residual_momentum = _scoring.residual_momentum
scale_to_vol_target = _scoring.scale_to_vol_target
trailing_stop_hit = _scoring.trailing_stop_hit
trend_quality = _scoring.trend_quality

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "etf_daily")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "ablate_rmdc_knobs.md")
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
WINDOWS = (
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026-07", "2026-07-01", "2026-07-31"),
)


def _variant(key, description, **overrides):
    config = {
        "key": key,
        "description": description,
        "vol_target": 0.12,
        "diversifier_floor": 0.25,
        "bond_gate": True,
        "tq_floor": 0.90,
        "offense_weights": None,
        "offense_weights_exact": False,
        "growth_count": 2,
    }
    config.update(overrides)
    return config


VARIANTS = (
    _variant("Baseline", "Baseline RMDC"),
    _variant("A", "Vol target 0.18", vol_target=0.18),
    _variant("B", "Diversifier floor 0.10", diversifier_floor=0.10),
    _variant("C", "Drop 63d > bond gate", bond_gate=False),
    _variant("D", "Trend-quality floor 0.80", tq_floor=0.80),
    _variant(
        "E",
        "Offense weights 0.85/0.10/0.05",
        offense_weights=(0.85, 0.10, 0.05),
        offense_weights_exact=True,
    ),
    _variant("F", "Hold 3 growth names", growth_count=3),
    _variant(
        "G",
        "A+C+E aggressive combo",
        vol_target=0.18,
        bond_gate=False,
        offense_weights=(0.85, 0.10, 0.05),
        offense_weights_exact=True,
    ),
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
# Scoring and variant-only gates
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
            close,
            bars["high"][:n],
            bars["low"][:n],
            bars["volume"][:n],
            bars["amount"][:n],
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


def eligible(codes, snap, require_trend, config):
    ranked = []
    for code in codes:
        score = snap["scores"].get(code)
        if score is None:
            continue
        if snap["crowd"].get(code, 0) >= 3:
            continue
        if require_trend and snap["tq"].get(code, 0.0) < config["tq_floor"]:
            continue
        if snap["ret63"].get(code, 0.0) <= 0.0:
            continue
        if config["bond_gate"] and snap["ret63"].get(code, 0.0) < snap["bond_ret"]:
            continue
        ranked.append((code, score * max(snap["tq"].get(code, 0.0), 0.01)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [code for code, _ in ranked]


def _needs_custom_targets(config):
    return (
        config["diversifier_floor"] != 0.25
        or config["offense_weights"] is not None
        or config["growth_count"] != 2
    )


def build_variant_targets(
    state,
    growth_ranked,
    div_ranked,
    vol_map,
    growth_corr_high,
    div_all_negative,
    config,
):
    """Fork only target knobs that the frozen live function cannot accept."""
    if not _needs_custom_targets(config):
        return build_targets(
            state,
            growth_ranked,
            div_ranked,
            vol_map,
            growth_corr_high,
            div_all_negative,
            config["vol_target"],
        )

    g_w, d_w, c_w = _scoring.SLEEVE_WEIGHTS[state]
    exact_offense = (
        state == _scoring.STATE_ON
        and config["offense_weights"] is not None
        and config["offense_weights_exact"]
    )
    if state == _scoring.STATE_ON and config["offense_weights"] is not None:
        g_w, d_w, c_w = config["offense_weights"]
    growth_ranked = list(growth_ranked or [])
    div_ranked = list(div_ranked or [])
    if state in (STATE_OFF, STATE_LOCK):
        growth_ranked = []
        g_w = 0.0
    if growth_corr_high and g_w > 0:
        freed = g_w * 0.5
        g_w -= freed
        d_w = min(0.80, d_w + freed)
        c_w = max(0.0, 1.0 - g_w - d_w)
        growth_ranked = growth_ranked[:1]
    if not growth_ranked and g_w > 0:
        d_w = min(0.80, d_w + g_w * 0.5)
        g_w = 0.0
        c_w = max(0.0, 1.0 - d_w)
    if div_all_negative:
        d_w = 0.0
        c_w = max(0.0, 1.0 - g_w)
    elif not exact_offense and d_w < config["diversifier_floor"] and g_w > 0:
        take = min(config["diversifier_floor"] - d_w, g_w)
        g_w -= take
        d_w += take

    g_n = config["growth_count"] if g_w >= 0.50 else (1 if g_w > 0 else 0)
    d_n = 3 if d_w >= 0.60 else (2 if d_w > 0 else 0)
    g_pick = growth_ranked[:g_n]
    d_pick = div_ranked[:d_n]

    weights = {}
    if g_pick and g_w > 0:
        for code, weight in inverse_vol_weights(g_pick, vol_map).items():
            weights[code] = weight * g_w
    if d_pick and d_w > 0:
        for code, weight in inverse_vol_weights(d_pick, vol_map).items():
            weights[code] = weights.get(code, 0.0) + weight * d_w
    weights, _scale = scale_to_vol_target(
        weights, vol_map, target=config["vol_target"]
    )
    return weights


def weekly_target(snap, lockdown, config):
    breadth = growth_breadth(snap["ret20"], GROWTH)
    med_vol = median_vol(snap["vols"], GROWTH)
    state = classify_state(breadth, med_vol, lockdown)
    growth_ranked = filter_correlated(
        eligible(GROWTH, snap, True, config), snap["ret60"], CORR_LIMIT
    )
    div_ranked = filter_correlated(
        eligible(DIVERSIFIER, snap, False, config), snap["ret60"], CORR_LIMIT
    )
    cluster = mean_pairwise_corr(snap["ret60"], growth_ranked[:5]) > CORR_CLUSTER
    div_all_neg = True
    for code in DIVERSIFIER:
        if snap["ret63"].get(code, -1.0) > 0.0:
            div_all_neg = False
            break
    weights = build_variant_targets(
        state,
        growth_ranked,
        div_ranked,
        snap["vols"],
        cluster,
        div_all_neg,
        config,
    )
    return {code: weight for code, weight in weights.items() if weight >= 0.01}


def flatten_target(snap, config):
    div_ranked = filter_correlated(
        eligible(DIVERSIFIER, snap, False, config), snap["ret60"], CORR_LIMIT
    )
    if div_ranked:
        return {div_ranked[0]: 0.60}
    return {}


# ---------------------------------------------------------------------------
# Portfolio mechanics copied from research/backtest_rmdc_etf.py
# ---------------------------------------------------------------------------
def apply_fill(nav, holdings, target, high_water, panel, counts, i):
    """Trade to target weights at the close of calendar[i]; 8bp per side."""
    turnover = 0.0
    for code in set(list(holdings) + list(target)):
        turnover += abs(target.get(code, 0.0) - holdings.get(code, 0.0))
    if turnover <= 1e-9:
        return nav, dict(holdings), False
    nav = nav * max(0.0, 1.0 - COST_ONE_WAY * turnover)
    new_holdings = {code: weight for code, weight in target.items() if weight > 1e-6}
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
    drawdown = float(np.min(sub / peak - 1.0))
    return ret, drawdown


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
    n_fills = 0
    n_flattens = 0

    def snapshot(i):
        if i not in snapshot_cache:
            snapshot_cache[i] = build_snapshot(panel, counts, pool, i)
        return snapshot_cache[i]

    for step, i in enumerate(sim):
        # 1) accrue previous close -> today's close with current holdings
        if step > 0 and holdings:
            prev_i = sim[step - 1]
            port_ret = 0.0
            grown = {}
            for code, weight in holdings.items():
                px0 = last_close(panel, counts, code, prev_i)
                px1 = last_close(panel, counts, code, i)
                daily_return = 0.0
                if px0 and px1 and px0 > 0:
                    daily_return = px1 / px0 - 1.0
                port_ret += weight * daily_return
                grown[code] = weight * (1.0 + daily_return)
            nav = nav * (1.0 + port_ret)
            if 1.0 + port_ret > 1e-9:
                holdings = {
                    code: weight / (1.0 + port_ret)
                    for code, weight in grown.items()
                }

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
            snap = snapshot(i)
        if flatten:
            lockdown_left = LOCKDOWN_DAYS
            nav, holdings, traded = apply_fill(
                nav,
                holdings,
                flatten_target(snap, config),
                high_water,
                panel,
                counts,
                i,
            )
            if traded:
                n_fills += 1
            n_flattens += 1
        if week_changed:
            lockdown = lockdown_left > 0
            if len(snap["mkt_close"]) >= 4 and crash_triggered(
                snap["mkt_close"], 0.06, 0.08
            ):
                lockdown_left = max(lockdown_left, LOCKDOWN_DAYS)
                lockdown = True
            pending = weekly_target(snap, lockdown, config)
            last_week = week

        equity.append(nav)
        if lockdown_left > 0:
            lockdown_left -= 1

    eq_dates = pd.DatetimeIndex(calendar[sim])
    equity = np.asarray(equity, dtype=float)
    cagr, mdd, sharpe = perf_summary(equity, eq_dates)
    result = {
        "key": config["key"],
        "description": config["description"],
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
        "nav": float(equity[-1]),
        "fills": n_fills,
        "flattens": n_flattens,
        "windows": {},
    }
    for label, start, end in WINDOWS:
        result["windows"][label] = window_summary(equity, eq_dates, start, end)
    return result


def _pct(value):
    return "%.2f%%" % (value * 100.0)


def render_table(results):
    lines = [
        "| Variant | Change | CAGR | MDD | Sharpe | "
        "2024-02 Ret | 2024-02 MDD | 2026-07 Ret | 2026-07 MDD | "
        "Final NAV | Fills | Flatten days |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: |",
    ]
    for result in results:
        feb = result["windows"]["2024-02"]
        jul = result["windows"]["2026-07"]
        lines.append(
            "| %(key)s | %(description)s | %(cagr)s | %(mdd)s | %(sharpe).2f | "
            "%(feb_ret)s | %(feb_mdd)s | %(jul_ret)s | %(jul_mdd)s | "
            "%(nav).3f | %(fills)d | %(flattens)d |"
            % {
                "key": result["key"],
                "description": result["description"],
                "cagr": _pct(result["cagr"]),
                "mdd": _pct(result["mdd"]),
                "sharpe": result["sharpe"],
                "feb_ret": _pct(feb[0]),
                "feb_mdd": _pct(feb[1]),
                "jul_ret": _pct(jul[0]),
                "jul_mdd": _pct(jul[1]),
                "nav": result["nav"],
                "fills": result["fills"],
                "flattens": result["flattens"],
            }
        )
    return "\n".join(lines)


def render_report(results, first_date, last_date):
    return """# RMDC knob ablation

Generated by `research/ablate_rmdc_knobs.py`.

- Data: cached ETF daily bars, %(first)s through %(last)s
- Signal/execution: T close signal, T+1 close fill
- Trading cost: 8bp one way
- Overall metrics: CAGR, maximum drawdown (MDD), daily Sharpe (252 sessions)
- Event windows: window return and within-window MDD
- Scoring: imported from `ptrade_rmdc_etf.py`

Variant E's explicit offense weights are treated as an exact offense-state
override; otherwise the standard 25%% floor would turn 0.85/0.10/0.05 back
into the baseline 0.70/0.25/0.05. Variant B changes only the generic floor,
which is non-binding when baseline offense already allocates 25%% to the
diversifier sleeve.

## Results

%(table)s
""" % {
        "first": first_date,
        "last": last_date,
        "table": render_table(results),
    }


def run():
    panel = load_panel()
    pool = [
        code
        for code in dict.fromkeys(list(GROWTH) + list(DIVERSIFIER))
        if code in panel
    ]
    calendar = np.unique(
        np.concatenate([bars["dates"] for bars in panel.values()])
    )
    counts = build_counts(panel, calendar)
    lo = np.datetime64(START)
    hi = np.datetime64(END)
    sim = [i for i in range(len(calendar)) if lo <= calendar[i] <= hi]
    if not sim:
        raise RuntimeError("no cached bars in %s .. %s" % (START, END))

    snapshot_cache = {}
    results = []
    for config in VARIANTS:
        results.append(
            run_variant(
                panel,
                counts,
                calendar,
                sim,
                pool,
                snapshot_cache,
                config,
            )
        )

    first_date = pd.Timestamp(calendar[sim[0]]).date()
    last_date = pd.Timestamp(calendar[sim[-1]]).date()
    report = render_report(results, first_date, last_date)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write(report)

    print("RMDC knob ablation %s .. %s" % (first_date, last_date))
    print(
        "signal at T close, fill at T+1 close, one-way cost %.0fbp"
        % (COST_ONE_WAY * 1e4)
    )
    print(render_table(results))
    print("wrote %s" % REPORT_PATH)
    return results


if __name__ == "__main__":
    run()
