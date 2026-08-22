# pTrade 量化策略仓库

个人/小资金用券商 **国金 PTrade** 做 A 股量化。2026 年约束见
[`docs/2026_a_share_quant_and_ptrade.md`](docs/2026_a_share_quant_and_ptrade.md)。

## 当前主策略

主策略是 [`ptrade_rmdc_etf.py`](ptrade_rmdc_etf.py)（残差动量 + 拥挤否决 + 相关过滤 + 成长/防御袖仓），
整文件粘贴进国金 PTrade，业务类型 ETF，建议分钟周期（14:45 风控 / 14:50 周频调仓 / 14:54 买入）。
国金为 Python 3.11，文件仍避免 f-string。设计与验证流程见
[`docs/rmdc_etf_design.md`](docs/rmdc_etf_design.md)。

在 ADM 的冻结样本外（OOS）结果明确优于 RMDC 前，**唯一的主实盘粘贴文件仍是
`ptrade_rmdc_etf.py`**。实验策略状态如下；状态不是收益承诺：

| 文件 | 状态 | 用途 |
|---|---|---|
| `ptrade_rmdc_etf.py` | **PRIMARY** | 当前唯一主实盘粘贴文件 |
| `ptrade_combo_etf.py` | **REJECTED** | 已否决，仅保留为研究对照 |
| `ptrade_gem_etf.py` | **REJECTED** | 17 行业池 12-1 动量方案已否决，仅保留复现 |
| `ptrade_adm_etf.py` | **UNDER TEST** | ADM 候选仍在验证，不得替代 RMDC 实盘 |

## 本地验证

```bash
pip install numpy pandas pytest pyarrow
python3 -m pytest tests -q                  # 单元测试
python3 research/fetch_free_etf_bars.py     # 抓免费日 K（新浪，腾讯兜底）
python3 research/backtest_rmdc_etf.py       # 研究回测（含 2024-02 / 2026-07 窗口）
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
