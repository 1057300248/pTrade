# pTrade 量化策略仓库

个人/小资金用券商 **国金 PTrade** 做 A 股量化。2026 年约束见
[`docs/2026_a_share_quant_and_ptrade.md`](docs/2026_a_share_quant_and_ptrade.md)。

## 实盘粘贴文件（两份）

整文件粘贴进国金 PTrade，业务类型 ETF，建议分钟周期（14:45 风控 / 14:50 周频调仓 / 14:54 买入）。
国金为 Python 3.11，文件避免 f-string。

- **保守仓：[`ptrade_rmdc_etf.py`](ptrade_rmdc_etf.py)**（残差动量 + 拥挤否决 + 相关过滤 + 成长/防御袖仓）。
  回撤控制最好，2026-07 压力窗口表现最优（-0.71%，全对照见
  [`research/backtest_adm_report.md`](research/backtest_adm_report.md)）。
  设计与验证流程见 [`docs/rmdc_etf_design.md`](docs/rmdc_etf_design.md)。
- **进取仓候选：[`ptrade_adm_etf.py`](ptrade_adm_etf.py)**（Antonacci 双动量，4 资产类 + 债底）。
  仅当**拆分修复后数据**的冻结 OOS CAGR 仍高于 RMDC 的 OOS CAGR，且通过
  [`docs/anti_overfit.md`](docs/anti_overfit.md) 的过拟合与压力测试关卡时，才作为进取仓实盘。
  当前报告口径（`research/backtest_adm_report.md`）：ADM OOS 7.54% 对 RMDC 6.21%，过拟合检查通过。
  **收益一律以报告数字为准，不得宣称"约 12%"等报告未支持的数字。**

已否决 / 仅研究（状态不是收益承诺）：

| 文件 / 方案 | 状态 | 说明 |
|---|---|---|
| `ptrade_combo_etf.py` | REJECTED | 残差动量组合已否决，仅保留为研究对照 |
| `ptrade_gem_etf.py` | REJECTED | 17 行业池 12-1 动量方案已否决，仅保留复现 |
| 双层动量（dual-layer，[`docs/alpha_etf_design.md`](docs/alpha_etf_design.md)） | 仅研究 | 只进 `research/` 对比，无实盘文件 |

## 数据口径：复权

- 研究端缓存（`research/cache/etf_daily`）来自免费新浪/腾讯日 K，**不含 ETF 份额拆分/合并复权**。
  装载层必须先做拆分回调（|单日收益| > 22% 视为公司行为）后才允许进回测，未修复数据上的数字不可引用。
- 实盘 PTrade `get_history(fq='pre')` 的复权由**券商端**处理，与研究缓存是两条不同序列，
  不得静默混用（见 `docs/anti_overfit.md` 规则 16）。

## 本地验证

```bash
pip install numpy pandas pytest pyarrow
python3 -m pytest tests -q                  # 单元测试
python3 research/fetch_free_etf_bars.py     # 抓免费日 K（新浪，腾讯兜底）
python3 research/backtest_rmdc_etf.py       # RMDC 研究回测（含 2024-02 / 2026-07 窗口）
python3 research/backtest_adm_etf.py        # ADM 研究回测（同协议，对照 GEM / RMDC）
python3 research/compare_strategies.py      # 三策略 + 基准汇总表
```

SimTradeLab 只作第一道过滤（国金没有独立 broker 口径，用 `auto`，不要填 `guosheng`）：

```bash
PYTHONPATH=../SimTradeLab/src python3 research/run_simtradelab_rmdc.py
PYTHONPATH=../SimTradeLab/src python3 research/run_simtradelab_gem.py
PYTHONPATH=../SimTradeLab/src python3 research/run_simtradelab_adm.py
```

SimTradeLab 不能替代国金分钟回测和仿真，也不要为此去开 QMT。

## 旧策略

`regime_etf_rotation.py` 以及 RSI / MACD / 小市值 / 旧 ETF 轮动文件只作对照，不作为 2026 主实盘。
