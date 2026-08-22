# -*- coding: utf-8 -*-
"""SimTradeLab first-filter runner for the under-test ptrade_adm_etf.py."""
from __future__ import print_function

import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIMTRADE = os.path.abspath(os.path.join(ROOT, "..", "SimTradeLab"))
SIMTRADE_SRC = os.path.join(SIMTRADE, "src")
sys.path.insert(0, SIMTRADE_SRC)

from simtradelab.backtest.config import BacktestConfig
from simtradelab.backtest.runner import BacktestRunner

REPORT_KEYS = ("total_return", "annual_return", "max_drawdown", "sharpe_ratio")


def _copy_strategy():
    src = os.path.join(ROOT, "ptrade_adm_etf.py")
    dest_dir = os.path.join(ROOT, "strategies", "ptrade_adm_etf")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "backtest.py")
    shutil.copy(src, dest)
    # SimTradeLab requires handle_data; ADM has no intraday logic (its crash
    # overlay runs via run_daily at 14:45), so append a no-op stub.
    with open(src, "r", encoding="utf-8") as handle:
        source = handle.read()
    if "def handle_data(" not in source:
        with open(dest, "a", encoding="utf-8") as handle:
            handle.write("\n\ndef handle_data(context, data):\n    pass\n")
    return dest_dir


def main():
    _copy_strategy()
    data_path = os.path.join(ROOT, "research", "simtradelab_data")
    config = BacktestConfig(
        strategy_name="ptrade_adm_etf",
        start_date="2024-01-02",
        end_date="2026-08-21",
        initial_capital=200000.0,
        market="CN",
        broker_profile="auto",
        t_plus_1=True,
        frequency="1d",
        data_path=data_path,
        strategies_path=os.path.join(ROOT, "strategies"),
        enable_multiprocessing=False,
        use_data_server=False,
        enable_charts=True,
        enable_logging=True,
        enable_export=False,
        locale="zh",
        strategy_file="backtest.py",
        benchmark_code="000300.SS",
    )
    runner = BacktestRunner()
    report = runner.run(config=config)
    if not report:
        raise SystemExit("SimTradeLab 回测没有返回报告")
    print("SimTradeLab ADM first-filter report")
    for key in REPORT_KEYS:
        print("  %s=%s" % (key, report.get(key)))
    return report


if __name__ == "__main__":
    main()
