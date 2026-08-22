# pTrade 量化策略仓库

个人/小资金用券商 **国金 PTrade** 做 A 股量化。2026 年约束见
[`docs/2026_a_share_quant_and_ptrade.md`](docs/2026_a_share_quant_and_ptrade.md)。

## 实盘粘贴文件（两份）

整文件粘贴进国金 PTrade，业务类型 ETF，建议分钟周期（14:45 风控 / 14:50 周频调仓 / 14:54 买入）。
国金为 Python 3.11，文件避免 f-string。

- **保守仓：[`ptrade_rmdc_etf.py`](ptrade_rmdc_etf.py)**（残差动量 + 拥挤否决 + 相关过滤 + 成长/防御袖仓）。
  回撤控制最好，2026-07 压力窗口表现最优（-0.71%；复权后全样本 6.40% / MDD -14.01%，OOS 6.44%，
  全对照见 [`research/compare_strategies.md`](research/compare_strategies.md)）。
  设计与验证流程见 [`docs/rmdc_etf_design.md`](docs/rmdc_etf_design.md)。
- **进取仓：[`ptrade_adm_etf.py`](ptrade_adm_etf.py)**（Antonacci 双动量，4 资产类 + 债底，
  实盘 `vol_target` = 0.16，即复权网格确认的 IS 胜者 VT16-MON）。
  复权后冻结 OOS CAGR **8.17% 对 RMDC 6.44%**，过拟合与压力关卡通过
  （[`docs/anti_overfit.md`](docs/anti_overfit.md)；明细见
  [`research/backtest_adm_report.md`](research/backtest_adm_report.md)）。代价是回撤更深：
  全样本 MDD -21.51%、2026-07 为 -3.90%。
  **12.03% 只是 ADM 的 IS（样本内）数字，禁止把"约 12%"当作实盘收益承诺**；可引用的实盘预期只有 OOS 8.17%。

状态表（状态不是收益承诺；数字均为拆分复权后口径，来源 `research/compare_strategies.md`）：

| 文件 / 方案 | 状态 | 说明 |
|---|---|---|
| `ptrade_combo_etf.py` | REJECTED | 复权后 OOS 仍 ≈0（-0.03%）且过拟合检查不通过，仅保留为研究对照 |
| `ptrade_gem_etf.py` | UNDER TEST（重启研究） | 当初的否决数字是**未复权拆分的伪影**；复权后全样本 10.22% / OOS 10.41% / 2026-07 -3.24%。待复权数据上的 IS 网格与完整冻结验证，**不得静默转正为主实盘** |
| 双层动量（dual-layer，[`docs/alpha_etf_design.md`](docs/alpha_etf_design.md)） | UNREPRODUCED | 共享引擎复现 OOS 5.54%，对设计宣称的 11.1% 未复现；仅研究，无实盘文件 |

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
