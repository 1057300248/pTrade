# -*- coding: utf-8 -*-
"""Offline backtest for the HOT-LEADER-V1 manual-trading proxy.

Signal at T close, fill at T+1 open, buy cost 12bp, sell 12bp + 5bp stamp.
Universe: cached CSI 300 names. This is not Tonghuashun's hot-concept board.
"""
from __future__ import print_function

import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.etf_panel import _load_one
from research.hot_leader_v1 import (
    AMOUNT_TOP_N,
    MAX_HOLDINGS,
    MAX_NEW_PER_DAY,
    MIN_AMOUNT_MA,
    MOM_WINDOW,
    STOP_LOSS,
    TIME_STOP_DAYS,
    fib_ok,
    is_limit_open,
    limit_threshold,
    macd_hist,
    market_up,
    mean_amount,
    outflow_proxy,
    pick_amount_top,
    pick_hot_industries,
    pick_leaders,
    trailing_return,
)
from research.oos_protocol import max_drawdown, overfit_warning, split_is_oos

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "hot_leader_daily")
START = "2018-01-02"
END = "2026-08-21"
IS_END = "2021-12-31"
BUY_COST = 0.0012
SELL_COST = 0.0012 + 0.0005
WINDOWS = (("2024-02-01", "2024-02-29"), ("2026-07-01", "2026-07-31"))


def _align(bars, calendar):
    frame = pd.DataFrame(
        {
            "open": bars["open"],
            "high": bars["high"],
            "low": bars["low"],
            "close": bars["close"],
            "amount": bars["amount"],
        },
        index=pd.to_datetime(bars["dates"]),
    )
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.reindex(calendar)
    return {key: frame[key].to_numpy(dtype=float) for key in frame.columns}


def load_universe(cache_dir=CACHE_DIR):
    universe_path = os.path.join(cache_dir, "universe.txt")
    if os.path.isfile(universe_path):
        with open(universe_path) as handle:
            codes = [line.strip() for line in handle if line.strip() and not line.startswith("000300")]
    else:
        codes = [
            name[:-8]
            for name in sorted(os.listdir(cache_dir))
            if name.endswith(".parquet") and not name.startswith("000300")
        ]
    market_path = os.path.join(cache_dir, "000300.SS.parquet")
    if not os.path.isfile(market_path):
        raise FileNotFoundError("missing 000300 cache at %s" % market_path)
    market = _load_one(market_path)
    calendar = pd.DatetimeIndex(pd.to_datetime(market["dates"]))
    calendar = calendar[(calendar >= START) & (calendar <= END)]
    panel = {}
    for code in codes:
        path = os.path.join(cache_dir, code + ".parquet")
        if not os.path.isfile(path):
            continue
        panel[code] = _align(_load_one(path), calendar)
    market_aligned = _align(market, calendar)
    return calendar, market_aligned, panel


def _window_return(nav, dates, start, end):
    mask = (dates >= np.datetime64(start)) & (dates <= np.datetime64(end))
    if mask.sum() < 2:
        return float("nan")
    values = nav[mask]
    if values[0] == 0:
        return float("nan")
    return float(values[-1] / values[0] - 1.0)


def run_backtest(calendar, market, panel, use_industry=False, industries=None,
                 require_macd=True, require_fib=True):
    dates = calendar.to_numpy(dtype="datetime64[ns]")
    n_days = dates.size
    codes = list(panel.keys())
    n_names = len(codes)
    opens = np.vstack([panel[code]["open"] for code in codes])
    highs = np.vstack([panel[code]["high"] for code in codes])
    lows = np.vstack([panel[code]["low"] for code in codes])
    closes = np.vstack([panel[code]["close"] for code in codes])
    amounts = np.vstack([panel[code]["amount"] for code in codes])
    code_to_j = {code: j for j, code in enumerate(codes)}
    industry_list = [None] * n_names
    if use_industry and industries:
        industry_list = [industries.get(code) for code in codes]

    macd_pass = np.zeros((n_names, n_days), dtype=bool)
    for j in range(n_names):
        dif, dea, hist = macd_hist(closes[j])
        for t in range(1, n_days):
            if not (np.isfinite(hist[t]) and np.isfinite(hist[t - 1])):
                continue
            if not (np.isfinite(dif[t]) and np.isfinite(dea[t])):
                continue
            macd_pass[j, t] = hist[t] > hist[t - 1] and dif[t] > dea[t]

    cash = 1.0
    shares = {}
    entry_px = {}
    entry_i = {}
    nav = np.ones(n_days, dtype=float)
    turns = 0.0
    skipped_limit = 0
    buys = 0
    sells = 0
    warmup = max(MOM_WINDOW, 60, 26 + 9) + 5

    def _down_limit(fill, prev, code):
        if not (np.isfinite(fill) and np.isfinite(prev)) or prev <= 0:
            return True
        return bool((prev - fill) / prev >= limit_threshold(code))

    for t in range(n_days):
        equity = cash
        for code, qty in list(shares.items()):
            j = code_to_j[code]
            px = closes[j, t]
            if not np.isfinite(px):
                px = entry_px.get(code, 0.0)
            equity += qty * px
        nav[t] = equity if equity > 0 else nav[t - 1] if t else 1.0

        if t < warmup or t >= n_days - 1:
            continue

        to_sell = []
        for code in list(shares):
            j = code_to_j[code]
            last = closes[j, t]
            if not np.isfinite(last) or last <= 0:
                continue
            stop = last <= entry_px[code] * (1.0 - STOP_LOSS)
            timed = (t - entry_i[code]) >= TIME_STOP_DAYS
            flow = outflow_proxy(closes[j], amounts[j], t)
            if stop or timed or flow:
                to_sell.append(j)

        for j in to_sell:
            code = codes[j]
            fill = opens[j, t + 1]
            prev = closes[j, t]
            qty = shares.get(code, 0.0)
            if qty <= 0 or not np.isfinite(fill) or fill <= 0:
                continue
            if _down_limit(fill, prev, code):
                continue
            cash += qty * fill * (1.0 - SELL_COST)
            turns += abs(qty * fill)
            sells += 1
            shares.pop(code, None)
            entry_px.pop(code, None)
            entry_i.pop(code, None)

        if len(shares) >= MAX_HOLDINGS:
            continue
        if not market_up(market["close"], t):
            continue

        tradable = []
        rets = np.full(n_names, np.nan)
        amt_ma = np.full(n_names, np.nan)
        for j, code in enumerate(codes):
            if code in shares:
                continue
            rets[j] = trailing_return(closes[j], t)
            amt_ma[j] = mean_amount(amounts[j], t)
            if not np.isfinite(rets[j]) or not np.isfinite(amt_ma[j]):
                continue
            if amt_ma[j] < MIN_AMOUNT_MA:
                continue
            if np.sum(np.isfinite(closes[j, : t + 1])) < warmup:
                continue
            tradable.append(j)

        if not tradable:
            continue

        if use_industry and any(industry_list[j] for j in tradable):
            hot = pick_hot_industries(rets, industry_list)
            leader_idx = pick_leaders(rets, industry_list, hot)
        else:
            ranked = sorted(tradable, key=lambda j: rets[j], reverse=True)
            leader_idx = ranked[:20]
        amount_idx = pick_amount_top(amounts[:, t], AMOUNT_TOP_N)
        union = []
        seen = set()
        for j in leader_idx + amount_idx:
            if j in seen or j not in tradable:
                continue
            seen.add(j)
            union.append(j)

        passed = []
        for j in union:
            if require_macd and not macd_pass[j, t]:
                continue
            if require_fib and not fib_ok(highs[j], lows[j], closes[j], t):
                continue
            passed.append(j)
        passed.sort(key=lambda j: rets[j], reverse=True)

        slots = min(MAX_NEW_PER_DAY, MAX_HOLDINGS - len(shares))
        equity = cash
        for code, qty in shares.items():
            j = code_to_j[code]
            px = closes[j, t]
            if np.isfinite(px):
                equity += qty * px
        if equity <= 0:
            continue
        ticket = 0.10 * equity
        added = 0
        for j in passed:
            if added >= slots:
                break
            code = codes[j]
            fill = opens[j, t + 1]
            prev = closes[j, t]
            if not np.isfinite(fill) or fill <= 0:
                continue
            if is_limit_open(fill, prev, code):
                skipped_limit += 1
                continue
            cost = ticket * (1.0 + BUY_COST)
            if cash < cost:
                continue
            qty = ticket / fill
            cash -= cost
            shares[code] = qty
            entry_px[code] = fill
            entry_i[code] = t + 1
            turns += ticket
            buys += 1
            added += 1

    if shares:
        last = n_days - 1
        for code, qty in list(shares.items()):
            j = code_to_j[code]
            px = closes[j, last]
            if np.isfinite(px) and px > 0:
                cash += qty * px * (1.0 - SELL_COST)
                turns += abs(qty * px)
                sells += 1
        shares = {}
        nav[-1] = cash

    dates_ts = pd.to_datetime(dates)
    split = split_is_oos(dates_ts, nav, is_end=IS_END)
    full_mdd = max_drawdown(nav)
    elapsed_years = (dates_ts[-1] - dates_ts[0]).days / 365.25
    full_cagr = float(nav[-1] ** (1.0 / elapsed_years) - 1.0) if elapsed_years > 0 else float("nan")
    rets = nav[1:] / nav[:-1] - 1.0
    rets = rets[np.isfinite(rets)]
    full_sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * math.sqrt(252.0)) if rets.size > 2 and np.std(rets, ddof=1) > 0 else float("nan")
    bench = market["close"]
    bench_nav = bench / bench[np.isfinite(bench)][0]
    bench_nav = np.where(np.isfinite(bench_nav), bench_nav, np.nan)
    # fill bench nans with previous
    for i in range(1, bench_nav.size):
        if not np.isfinite(bench_nav[i]):
            bench_nav[i] = bench_nav[i - 1]
    bench_split = split_is_oos(dates_ts, bench_nav, is_end=IS_END)
    turnover = float(turns / max(n_days / 252.0, 1e-9))
    result = {
        "n_names": n_names,
        "n_days": int(n_days),
        "buys": buys,
        "sells": sells,
        "skipped_limit": skipped_limit,
        "full_cagr": full_cagr,
        "full_mdd": full_mdd,
        "full_sharpe": full_sharpe,
        "is": split["is"],
        "oos": split["oos"],
        "bench_is": bench_split["is"],
        "bench_oos": bench_split["oos"],
        "overfit_warning": bool(
            overfit_warning(split["is"]["sharpe"], split["oos"]["sharpe"])
            if np.isfinite(split["is"]["sharpe"]) and np.isfinite(split["oos"]["sharpe"])
            else True
        ),
        "stress": {name: _window_return(nav, dates, a, b) for name, (a, b) in (("2024-02", WINDOWS[0]), ("2026-07", WINDOWS[1]))},
        "bench_stress": {
            name: _window_return(bench_nav, dates, a, b) for name, (a, b) in (("2024-02", WINDOWS[0]), ("2026-07", WINDOWS[1]))
        },
        "one_way_turnover_notional_per_year": turnover,
        "use_industry": bool(use_industry),
        "require_macd": bool(require_macd),
        "require_fib": bool(require_fib),
    }
    return result, dates_ts, nav, bench_nav


def _fmt_pct(value):
    if value is None or not np.isfinite(value):
        return "nan"
    return "%.2f%%" % (100.0 * value)


def print_report(result):
    print("HOT-LEADER-V1 proxy  names=%d days=%d industry=%s" % (
        result["n_names"], result["n_days"], result["use_industry"]))
    print("trades buy=%d sell=%d skip_limit=%d" % (
        result["buys"], result["sells"], result["skipped_limit"]))
    print("full CAGR %s MDD %s Sharpe %.3f" % (
        _fmt_pct(result["full_cagr"]), _fmt_pct(result["full_mdd"]), result["full_sharpe"]))
    print("IS  CAGR %s MDD %s Sharpe %.3f" % (
        _fmt_pct(result["is"]["cagr"]), _fmt_pct(result["is"]["mdd"]), result["is"]["sharpe"]))
    print("OOS CAGR %s MDD %s Sharpe %.3f" % (
        _fmt_pct(result["oos"]["cagr"]), _fmt_pct(result["oos"]["mdd"]), result["oos"]["sharpe"]))
    print("OOS 000300 CAGR %s MDD %s Sharpe %.3f" % (
        _fmt_pct(result["bench_oos"]["cagr"]), _fmt_pct(result["bench_oos"]["mdd"]), result["bench_oos"]["sharpe"]))
    print("overfit_warning", result["overfit_warning"])
    print("stress 2024-02 strat %s bench %s" % (
        _fmt_pct(result["stress"]["2024-02"]), _fmt_pct(result["bench_stress"]["2024-02"])))
    print("stress 2026-07 strat %s bench %s" % (
        _fmt_pct(result["stress"]["2026-07"]), _fmt_pct(result["bench_stress"]["2026-07"])))


def main():
    calendar, market, panel = load_universe()
    variants = [
        ("V1", True, True),
        ("MACD-only", True, False),
        ("no-tech", False, False),
    ]
    out_dir = os.path.join(os.path.dirname(__file__), "cache", "hot_leader_daily")
    os.makedirs(out_dir, exist_ok=True)
    all_results = {}
    official_nav = None
    dates = None
    bench = None
    for name, require_macd, require_fib in variants:
        print("==== %s macd=%s fib=%s ====" % (name, require_macd, require_fib))
        result, dates, nav, bench = run_backtest(
            calendar, market, panel,
            use_industry=False,
            require_macd=require_macd,
            require_fib=require_fib,
        )
        print_report(result)
        all_results[name] = result
        if name == "V1":
            official_nav = nav
            pd.DataFrame({"date": dates, "nav": nav, "bench": bench}).to_csv(
                os.path.join(out_dir, "nav.csv"), index=False
            )
    with open(os.path.join(out_dir, "backtest_result.json"), "w") as handle:
        json.dump(all_results, handle, indent=2)
    return all_results


if __name__ == "__main__":
    main()
