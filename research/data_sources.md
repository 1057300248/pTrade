# 研究数据源（国金 PTrade 策略不依赖它们）

实盘/仿真只使用国金 PTrade 的 `get_history` 等生命周期 API。下面这些源只用于本地研究、参数校准和 SimTradeLab 第一道过滤。

研究时点：2026-08-21。

## 分层

| 层 | 用途 | 默认 |
| --- | --- | --- |
| Live | 国金 PTrade `get_history` / `get_positions` / `order` | 券商终端 |
| Research bars | ETF 日 K（OHLCV） | **新浪 `CN_MarketData.getKLineData`**，腾讯 `fqkline` 兜底 |
| Research quote | 最新价/成交额抽查 | 腾讯 `qt.gtimg.cn` |
| Optional local engine | 全市场日/分钟底座 | free-stockdb（用户本机，不进策略文件） |
| Do not use in live file | 同花顺 iFinD / HiThink API Key / CMES token / 东财 | 需要账号或会封 IP |

## 用户点名的源

| 源 | 结论 | 本仓库怎么用 |
| --- | --- | --- |
| 同花顺免费 API | 官方 iFinD 要 Windows 客户端+账号；HiThink Financial-API 要 API Key。零鉴权的热点/北向网页接口不稳定，且北向持仓明细已不可得。 | **不接入策略**。没有 Key 就不拉。 |
| mootdx（通达信 TCP 7709） | a-stock-data 首选 K 线源，不封 IP。云环境出站 TCP 7709 不一定通。 | 研究脚本可作第二兜底，失败则跳过。 |
| akshare（askshare） | 2026 仍可用，但是东财/同花顺等的封装；a-stock-data V3 已移除。本环境未预装，且 Python 要求 3.11+。 | **不作为默认依赖**。需要时再装。 |
| a-stock-data | GitHub Skill，不是 pip 包。建议直连通达信/腾讯，东财仅独有数据。 | 只借鉴优先级：腾讯/新浪 > mootdx > 东财。 |
| free-stockdb | 本地 C++ 日K/分钟引擎，有 Linux 包，无 token。体积和全市场同步不适合塞进策略或这次云会话。 | 用户本机可选；本仓库不绑定。 |
| CMES / cmesdata | 专业库，分钟/逐笔要 token，偏付费。PTrade 实盘用不到 tick。 | **不依赖**。14:50 时点用国金分钟回测验证。 |

## 本仓库实际取数

`research/fetch_free_etf_bars.py`：

1. 新浪日 K，`scale=240`，`datalen=2500`（约 2016 至今）
2. 失败则腾讯前复权日 K
3. 本环境实测：东财 K 线会断开；akshare 的 `fund_etf_hist_em` 同样失败，腾讯兜底可用；mootdx TCP 7709 可达但未作为默认依赖
4. 写成 `research/cache/etf_daily/<code>.parquet`
5. 同时写成 SimTradeLab 的 `research/simtradelab_data/cn/stocks/<code>.parquet`

字段：`date, open, high, low, close, volume, amount`。新浪无成交额时用 `close * volume` 近似。

不要把这些数据提交进 git。
