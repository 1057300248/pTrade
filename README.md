# pTrade 量化策略仓库

个人/小资金用券商 PTrade 做 A 股量化。2026 年的方向判断和落地说明见
[`docs/2026_a_share_quant_and_ptrade.md`](docs/2026_a_share_quant_and_ptrade.md)。

## 当前主策略

把 [`regime_etf_rotation.py`](regime_etf_rotation.py) 整文件粘贴进 PTrade：

- 业务类型：ETF / 股票
- 运行周期：建议分钟线（实盘 14:50 调仓）；日线回测也能跑 `run_daily`
- Python：兼容 3.5（无 f-string）

核心规则：沪深300ETF 相对 60 日均线划分风险开/关 → 动量×R²×效率系数打分 → 持有 2 只 → 分差不够不换仓。

## 本地验证

```bash
pip install numpy pandas pytest
python -m pytest tests/test_regime_etf_rotation.py -q
python research/backtest_regime_etf.py
```

更完整的 PTrade API 本地回测可用同工作区的 SimTradeLab，注意以它的支持矩阵为准。

## 旧策略怎么用

| 文件 | 建议 |
| --- | --- |
| `ETF轮动策略.py` / `V2` / `优化V3` | 被主策略吸收，保留对照 |
| `动量效率因子.py` / `分数差距.py` | 已并入打分和换仓滞后 |
| `国债逆回购.py` | 主策略实盘尾盘调用 |
| `小市值策略.py` | 2026 年不作为主实盘 |
| `RSI震荡策略v1.py` / `MACD背离策略.py` / `一阳穿三线策略.py` | 仅研究 |
