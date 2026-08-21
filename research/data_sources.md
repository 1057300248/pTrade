# 研究数据源（国金 PTrade 策略不依赖它们）

实盘策略的历史行情只使用 PTrade `get_history`。下面这些外部数据源只用于本地研究、参数校准和 SimTradeLab 第一道过滤，不会被 `ptrade_rmdc_etf.py` 导入。

研究时点：2026-08-21。

## 分层

| 层 | 用途 | 默认 |
| --- | --- | --- |
| Live | 策略历史行情 | PTrade `get_history` |
| Research bars | ETF 日 K（OHLCV + amount） | **新浪 `CN_MarketData.getKLineData`**，腾讯 `fqkline` 兜底 |
| Optional local engine | 全市场日/分钟数据 | free-stockdb（用户 PC，不进仓库或实盘策略） |

## 用户点名的源

| 源 | 结论 | 本仓库怎么用 |
| --- | --- | --- |
| 同花顺 iFinD / HiThink | iFinD 需要客户端和账号认证；HiThink Financial API 需要 API Key，均不是免鉴权数据源。 | 不接入研究脚本或实盘策略。 |
| akshare / 东方财富历史行情 | 本 VM 调用东方财富历史行情失败，`akshare` 的东方财富历史行情封装同样失败。 | 不作为依赖，也不加入回退链。 |
| 新浪 | 日 K 接口在本 VM 可用。 | 默认源：`CN_MarketData.getKLineData`。 |
| 腾讯 | `fqkline` 在本 VM 可用。 | 新浪失败后的唯一回退源。 |
| mootdx | 通达信 TCP 7709 在允许该端口的网络中可以工作。 | 可手动用于研究，但不是默认源或脚本回退项。 |
| free-stockdb | 面向本地全市场数据，数据体积和同步流程不适合本次云环境。 | 用户 PC 可选，本仓库不绑定。 |
| CMES / cmesdata | 需要付费数据服务或 token。 | 不依赖。 |

## 本仓库实际取数

`research/fetch_free_etf_bars.py`：

1. 新浪日 K，`scale=240`，`datalen=2500`（约 2016 至今）
2. 失败则腾讯前复权日 K
3. 每次公共接口请求之间暂停约 0.25 秒
4. 写成 `research/cache/etf_daily/<code>.parquet`
5. 同时写成 SimTradeLab 的 `research/simtradelab_data/cn/stocks/<code>.parquet`
6. 两份文件都已覆盖到 2026-08-21 时跳过；只有一份完整时在本地复制，不重复下载

字段：`date, open, high, low, close, volume, amount`。新浪和腾讯响应无成交额字段时用 `close * volume` 近似；腾讯成交量从“手”换算为股。

不要把这些数据提交进 git。
