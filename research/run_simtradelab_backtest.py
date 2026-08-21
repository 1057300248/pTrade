# -*- coding: utf-8 -*-
"""
用 SimTradeLab 对 regime_etf_rotation 做国金 PTrade 之前的第一道过滤。

注意：SimTradeLab 没有独立的「国金」broker_profile。国金 Python 已到 3.11，
不要误用 guosheng（那是国盛，会强制 Python 3.5 检查）。这里用 auto。
"""
from __future__ import print_function

import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIMTRADE = os.path.abspath(os.path.join(ROOT, "..", "SimTradeLab"))
if os.path.isdir(os.path.join(SIMTRADE, "src")):
    sys.path.insert(0, os.path.join(SIMTRADE, "src"))

from simtradelab.backtest.config import BacktestConfig
from simtradelab.backtest.runner import BacktestRunner


def _copy_strategy():
    src = os.path.join(ROOT, "regime_etf_rotation.py")
    dest_dir = os.path.join(ROOT, "strategies", "regime_etf_rotation")
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy(src, os.path.join(dest_dir, "backtest.py"))
    return dest_dir


def main():
    _copy_strategy()
    data_path = os.path.join(ROOT, "research", "simtradelab_data")
    config = BacktestConfig(
        strategy_name="regime_etf_rotation",
        start_date="2025-02-03",
        end_date="2025-10-13",
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
    keys = ["total_return", "annual_return", "max_drawdown", "sharpe_ratio", "total_trades"]
    print("SimTradeLab first-filter report")
    for key in keys:
        if key in report:
            print("  %s=%s" % (key, report[key]))
    for key, value in sorted(report.items()):
        if key not in keys and not hasattr(value, "shape"):
            text = str(value)
            if len(text) < 120:
                print("  %s=%s" % (key, text))
    return report


if __name__ == "__main__":
    main()
