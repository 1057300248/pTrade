# pTrade 量化策略仓库

个人/小资金用券商 **国金 PTrade** 做 A 股量化。2026 年约束见
[`docs/2026_a_share_quant_and_ptrade.md`](docs/2026_a_share_quant_and_ptrade.md)。
从零主策略说明见 [`docs/rmdc_etf_design.md`](docs/rmdc_etf_design.md)。

## 当前主策略

把 [`ptrade_rmdc_etf.py`](ptrade_rmdc_etf.py) 整文件粘贴进国金 PTrade：

- 业务类型：ETF
- 运行周期：建议分钟线（14:45 风控，14:50 周频调仓，实盘 14:54 买入）
- Python：国金为 3.11；文件仍避免 f-string，方便 SimTradeLab 过滤

核心：残差动量 + 拥挤否决 + 相关过滤 + 成长/防御袖仓，而不是 510300 均线状态机。

## 本地验证

```bash
pip install numpy pandas pytest pyarrow
python -m pytest tests/test_ptrade_rmdc_etf.py -q
python research/fetch_free_etf_bars.py
python research/backtest_rmdc_etf.py
```

SimTradeLab 第一道过滤（国金没有独立 broker 口径，用 `auto`，不要填 `guosheng`）：

```bash
PYTHONPATH=../SimTradeLab/src python research/run_simtradelab_rmdc.py
```

SimTradeLab 不能替代国金分钟回测和仿真。不要为此去开 QMT。

## 旧策略

`regime_etf_rotation.py` 以及 RSI / MACD / 小市值 / 旧 ETF 轮动文件只作对照，不作为 2026 主实盘。
