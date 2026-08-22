# SimTradeLab 第一道过滤结果（RMDC / ADM / GEM）

运行时间 2026-08-22 03:44 UTC。**SimTradeLab 只是第一道过滤**（验证生命周期、
T+1、语法、执行管线），**不是国金 PTrade 分钟回测**：日线模式把 14:45/14:50/14:54
压成同一根日 K，费率/滑点为模拟配置。最终裁判仍是国金分钟回测 + ≥4 周仿真。

- 配置：2024-01-02..2026-08-21，本金 20 万，`broker_profile="auto"`（国金无独立
  口径，**禁止填 `guosheng`**），`t_plus_1=True`，日频，基准 000300.SS。
- **窗口警告**：下表是 2024-2026 单窗口结果，**不得当作 2018-2026 OOS 年化引用**；
  与研究回测（2022-2026 OOS）比较时只看方向与量级。
- 完整日志：`/opt/cursor/artifacts/simtradelab_desktop.log`（仓库内另存于各
  `strategies/*/stats/`）。

## 结果（打印原文换算为百分比）

| 策略 | 总收益 | 年化 | 最大回撤 | Sharpe | vs 000300 超额 | 数据卫生 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| RMDC | +8.38% | +3.22% | -18.22% | 0.295 | -26.24% | **被拆分污染**（见下） |
| ADM | +59.99% | +20.36% | -15.26% | 1.166 | +25.37% | 干净 |
| GEM | -34.19% | -15.21% | -56.36% | -0.512 | -68.80% | **被拆分污染**（见下） |

原始打印行：

```
SimTradeLab RMDC first-filter report: total_return=0.0838  annual_return=0.0322  max_drawdown=-0.1822  sharpe_ratio=0.295
SimTradeLab ADM  first-filter report: total_return=0.5999  annual_return=0.2036  max_drawdown=-0.1526  sharpe_ratio=1.166
SimTradeLab GEM  first-filter report: total_return=-0.3419 annual_return=-0.1521 max_drawdown=-0.5636  sharpe_ratio=-0.512
```

## 数据卫生警告：RMDC 与 GEM 的数字不可用于裁决

`research/simtradelab_data/cn/stocks/*.parquet` 仍是**未做拆分复权的原始数据**
（实测 515880 在 2026-02-03 收盘 3.160→1.084，假 -65.7%）。窗口内的假跳变——
516160 2024-09 合并（+221%）、512800 2025-07 拆分（-49.7%）、515880 2026-02 与
2026-07 两次拆分（-65.7% / -52.1%）——全部落在 RMDC 与 GEM 的成长池内，会伪造
崩盘触发、动量分数与回撤统计（同一污染曾把 GEM 研究回测从 OOS +10.4% 伪装成
-9.3%，见 `research/backtest_adm_report.md`）。**ADM 的五标的池（510300/159915/
513100/518880/511010）在本窗口内无任何公司行为，其结果干净**（513100 的 1 拆 5
在 2022-01，窗口之外）。

结论：在 `prepare_simtradelab_data.py` 接入 `research/etf_panel.py` 的复权逻辑
之前，本表只有 ADM 一行可用于第一道过滤判断；RMDC/GEM 两行仅证明其执行管线
（下单、回调、T+1、周频时点）在 SimTradeLab 下能完整跑通。数据修复不属于
runner glue，留给数据管线维护方处理。

## 图表

- `/opt/cursor/artifacts/simtradelab_rmdc_2024_2026_first_filter.png`
- `/opt/cursor/artifacts/simtradelab_adm_2024_2026_first_filter.png`
- `/opt/cursor/artifacts/simtradelab_gem_2024_2026_first_filter.png`

## 复现

```bash
PYTHONPATH=/agent/repos/SimTradeLab/src python3 research/run_simtradelab_rmdc.py
PYTHONPATH=/agent/repos/SimTradeLab/src python3 research/run_simtradelab_adm.py
PYTHONPATH=/agent/repos/SimTradeLab/src python3 research/run_simtradelab_gem.py
```
