# -*- coding: utf-8 -*-
"""
用仓库内历史行情，本地回测状态机 ETF 轮动。

不依赖 PTrade。信号在 T 日收盘计算，T+1 日收盘成交，避免用未来函数。
"""
from __future__ import print_function

import argparse
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from regime_etf_rotation import (
    DEFAULT_DEFENSIVE,
    combined_score,
    detect_regime,
    eligible_pool,
    select_holdings,
)


CODE_MAP = {
    "510300": "510300.SS",
    "510500": "510500.SS",
    "510880": "510880.SS",
    "159915": "159915.SZ",
    "513100": "513100.SS",
    "518880": "518880.SS",
}


def _normalize_code(code):
    code = str(code)
    if code.endswith(".SS") or code.endswith(".SZ"):
        return code
    if code in CODE_MAP:
        return CODE_MAP[code]
    if code.startswith("5") or code.startswith("6"):
        return code + ".SS"
    return code + ".SZ"


def load_wide_csv(path):
    df = pd.read_csv(path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.columns = [_normalize_code(c) for c in df.columns]
    return df.astype(float)


def load_market_panel(path):
    df = pd.read_csv(path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    wide = df.pivot_table(index=date_col, columns="code", values="close", aggfunc="last")
    wide = wide.sort_index()
    # 该文件混有分钟行，按日取最后一条
    wide = wide.groupby(wide.index.normalize()).last()
    return wide.astype(float)


def buy_and_hold(prices, cost=0.0):
    nav = prices / prices.iloc[0]
    return nav


def run_backtest(price_df, hold_num=2, cost_bps=5.0, gap=0.15, score_floor=0.02,
                 min_days=20, max_days=60, ma_window=60, defensive=None,
                 rebalance_days=1):
    if defensive is None:
        defensive = [c for c in DEFAULT_DEFENSIVE if c in price_df.columns]
    codes = list(price_df.columns)
    bench_col = "510300.SS" if "510300.SS" in codes else codes[0]
    cost = cost_bps / 10000.0
    dates = list(price_df.index)
    holdings = []
    nav = 1.0
    equity = []
    turns = 0
    regime_hist = []
    trade_log = []

    start = max(max_days + 5, ma_window + 1)
    last_holdings = []
    for i in range(start, len(dates) - 1):
        window = price_df.iloc[: i + 1]
        bench = window[bench_col].dropna().values
        regime = detect_regime(bench, ma_window=ma_window)
        pool = eligible_pool(regime, codes, defensive)
        score_map = {}
        for code in pool:
            series = window[code].dropna().values
            if len(series) < min_days:
                continue
            result = combined_score(
                series,
                opens=series,
                highs=series,
                lows=series,
                min_days=min_days,
                max_days=max_days,
            )
            score_map[code] = result["score"]
        due = (i - start) % rebalance_days == 0
        if due:
            target = select_holdings(score_map, last_holdings, hold_num, score_floor, gap)
        else:
            target = list(last_holdings)
        exec_date = dates[i + 1]
        px_now = price_df.loc[exec_date]
        ret = 0.0
        if last_holdings:
            legs = []
            for code in last_holdings:
                prev_px = price_df.iloc[i][code]
                now_px = px_now[code]
                if prev_px > 0 and np.isfinite(now_px) and np.isfinite(prev_px):
                    legs.append(now_px / prev_px - 1.0)
            if legs:
                ret = float(np.mean(legs))
        old_set = set(last_holdings)
        new_set = set(target)
        switched = old_set != new_set
        if switched:
            changed = len(old_set.symmetric_difference(new_set)) / float(max(hold_num, 1) * 2)
            ret -= cost * 2.0 * max(changed, 0.25)
            turns += 1
            trade_log.append((exec_date.date(), regime, list(target), dict(score_map)))
        nav *= (1.0 + ret)
        last_holdings = list(target)
        equity.append((exec_date, nav, regime, ",".join(last_holdings)))
        regime_hist.append(regime)

    eq = pd.DataFrame(equity, columns=["date", "nav", "regime", "holdings"]).set_index("date")
    return eq, turns, trade_log, bench_col


def summarize(nav, name, bench_nav=None):
    rets = nav.pct_change().dropna()
    if len(nav) < 2 or nav.iloc[0] <= 0:
        return {"name": name, "ann": 0, "maxdd": 0, "sharpe": 0, "calmar": 0, "total": 0}
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    total = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    ann = (1.0 + total) ** (1.0 / years) - 1.0 if years > 0 else total
    peak = nav.cummax()
    dd = nav / peak - 1.0
    maxdd = float(dd.min())
    vol = float(rets.std() * np.sqrt(252)) if len(rets) else 0.0
    sharpe = float(ann / vol) if vol > 1e-9 else 0.0
    calmar = float(ann / abs(maxdd)) if maxdd < 0 else 0.0
    out = {
        "name": name,
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "total": total,
        "ann": ann,
        "maxdd": maxdd,
        "sharpe": sharpe,
        "calmar": calmar,
    }
    if bench_nav is not None:
        aligned = pd.concat([nav.rename("s"), bench_nav.rename("b")], axis=1).dropna()
        if len(aligned) > 2:
            excess = aligned["s"].pct_change() - aligned["b"].pct_change()
            out["excess_total"] = float(aligned["s"].iloc[-1] / aligned["s"].iloc[0] - aligned["b"].iloc[-1] / aligned["b"].iloc[0])
            out["excess_ann"] = float(excess.mean() * 252)
    return out


def fmt(stats):
    line = "%s  %s~%s  收益=%.1f%%  年化=%.1f%%  回撤=%.1f%%  夏普=%.2f" % (
        stats["name"],
        stats.get("start", ""),
        stats.get("end", ""),
        stats["total"] * 100,
        stats["ann"] * 100,
        stats["maxdd"] * 100,
        stats["sharpe"],
    )
    if "excess_ann" in stats:
        line += "  超额年化=%.1f%%" % (stats["excess_ann"] * 100)
    return line


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.path.join(ROOT, "test", "data"))
    parser.add_argument("--hold-num", type=int, default=2)
    parser.add_argument("--cost-bps", type=float, default=5.0)
    args = parser.parse_args()

    reports = []
    datasets = [
        ("etf_data2_2015", os.path.join(args.data_dir, "etf_data2.csv"), "wide"),
        ("etf_data_2015", os.path.join(args.data_dir, "etf_data.csv"), "wide"),
        ("market19_2024", os.path.join(args.data_dir, "market_data20241013-20251013.csv"), "panel"),
    ]
    for name, path, kind in datasets:
        if not os.path.exists(path):
            continue
        prices = load_wide_csv(path) if kind == "wide" else load_market_panel(path)
        prices = prices.dropna(axis=1, how="all").ffill()
        variants = [
            ("strategy", dict(hold_num=args.hold_num)),
            ("top1_no_regime", dict(hold_num=1, gap=0.0, score_floor=0.0,
                                    defensive=list(prices.columns))),
        ]
        print("=" * 72)
        print("数据集 %s  标的=%s" % (name, ",".join(prices.columns)))
        bench_col = "510300.SS" if "510300.SS" in prices.columns else prices.columns[0]
        eq_main = None
        turns_main = 0
        for label, kwargs in variants:
            eq, turns, _trades, used_bench = run_backtest(
                prices, cost_bps=args.cost_bps, **kwargs
            )
            bench = prices[used_bench].reindex(eq.index)
            bench_nav = bench / bench.iloc[0]
            stats = summarize(eq["nav"], name + "_" + label, bench_nav)
            print("调仓次数=%d  %s" % (turns, fmt(stats)))
            if label == "strategy":
                eq_main, turns_main = eq, turns
        bench = prices[bench_col].reindex(eq_main.index)
        bench_nav = bench / bench.iloc[0]
        print(fmt(summarize(bench_nav, name + "_bench_" + bench_col.split(".")[0])))
        if "518880.SS" in prices.columns:
            gold = prices["518880.SS"].reindex(eq_main.index)
            print(fmt(summarize(gold / gold.iloc[0], name + "_bh_gold")))
        off_days = (eq_main["regime"] == "risk_off").mean()
        print("risk_off 占比=%.1f%%  末持仓=%s" % (off_days * 100, eq_main["holdings"].iloc[-1]))
        reports.append((eq_main, turns_main, prices.columns.tolist()))

    return reports


if __name__ == "__main__":
    main()
