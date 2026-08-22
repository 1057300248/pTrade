# 研究数据源（国金 PTrade 策略不依赖它们）

实盘策略的历史行情只使用 PTrade `get_history`。下面这些外部数据源只用于本地研究、参数校准和 SimTradeLab 第一道过滤，不会被 `ptrade_*.py` 导入。

研究时点：2026-08-21。

## 分层

| 层 | 用途 | 默认 |
| --- | --- | --- |
| Live | 策略历史行情 | PTrade `get_history` |
| Research bars | ETF 日 K（OHLCV + amount） | 新浪 → 腾讯 → **baostock → akshare → 同花顺免费 → free-stockdb** |
| Optional local engine | 全市场日/分钟数据 | free-stockdb（用户 PC 本机服务，不进仓库或实盘策略） |

`aakshare` 按 **akshare** 处理（常见拼写）。

## 用户点名的源

| 源 | 结论 | 本仓库怎么用 |
| --- | --- | --- |
| 同花顺**免费**日 K | `d.10jqka.com.cn/v6/line/hs_XXXXXX/01/{all,year}.js`，免 iFinD 账号。可能要 `hexin-v` 或被反爬拦。 | 研究适配器 `ths`。不是 iFinD / HiThink。 |
| 同花顺 iFinD / HiThink | 客户端或 API Key，不是免鉴权源。 | 不接入研究脚本或实盘策略。 |
| free-stockdb | [hello245m/free-stockdb](https://github.com/hello245m/free-stockdb) 本地 C++ 引擎，默认 `127.0.0.1:7899`。 | 研究适配器：`FREE_STOCKDB_DIR` 本地 dump、HTTP、可选 Python SDK。本仓库不捆绑数据。 |
| baostock | `query_history_k_data_plus`，代码 `sh.510300` / `sz.159915`，`adjustflag=3` 不复权。需 `pip install baostock`。个股历史完整；**本环境 ETF 只返回 2026-01 起约 154 根**。 | 研究回退链。默认 `min_rows=400`，过短序列不会写成 8 年缓存。 |
| akshare / aakshare | `fund_etf_hist_em`（ETF）/ `stock_zh_index_daily`（指数）。东财接口在部分网络会 `RemoteDisconnected`。 | 研究回退链；失败则跳过，不假装成功。本环境 510300 探测成功（2012-05-28 起）。 |
| 新浪 | 日 K 接口。 | 默认第一源：`CN_MarketData.getKLineData`。 |
| 腾讯 | `fqkline`。 | 新浪失败后的第二源。 |
| mootdx | 通达信 TCP 7709。 | 可手动用于研究，不是脚本默认项。 |
| CMES / cmesdata | 付费或 token。 | 不依赖。 |

## 本仓库实际取数

`research/fetch_free_etf_bars.py` 调用 `research/source_adapters.py`：

1. 按 `--sources` 或环境变量 `PTRADE_RESEARCH_SOURCES` 依次尝试
2. 默认顺序：`sina,tencent,baostock,akshare,ths,free-stockdb`
3. 某个源返回空或抛错就试下一个，不中断整次任务
4. 写成 `research/cache/etf_daily/<code>.parquet`
5. 同时写成 SimTradeLab 的 `research/simtradelab_data/cn/stocks/<code>.parquet`
6. 两份文件都已覆盖到 2026-08-21 时跳过；`--force` 才重拉

字段：`date, open, high, low, close, volume, amount`。成交额缺失时用 `close * volume` 近似。腾讯 / 同花顺 / akshare 东财成交量按「手」换算为股；新浪、baostock、free-stockdb 按股。

装入研究回测前必须走 `research/etf_panel.py` 的拆分回调。未修复序列上的数字一律作废。

不要把这些行情文件提交进 git。

## 命令

```bash
# 默认回退链；缓存已到 2026-08-21 则跳过
python research/fetch_free_etf_bars.py

# 只探测各源是否通（不写缓存）
python research/fetch_free_etf_bars.py --probe

# 指定源（aakshare / tonghuashun 是别名）
python research/fetch_free_etf_bars.py --sources ths,baostock,aakshare,free-stockdb --force --codes 510300.SS

# 本机 free-stockdb
export FREE_STOCKDB_URL=http://127.0.0.1:7899
export FREE_STOCKDB_DIR=/path/to/stockdb/dump
```

## 本环境探测（2026-08-22，`510300.SS`）

| 源 | 结果 | 行数 | 区间 |
| --- | --- | ---: | --- |
| sina | 通 | 2500 | 2016-05-10 .. 2026-08-21 |
| tencent | 通 | 800 | 2023-05-09 .. 2026-08-21 |
| baostock | 通，但 ETF 过短 | 154 | 2026-01-05 .. 2026-08-21 |
| akshare | 通 | 3461 | 2012-05-28 .. 2026-08-21 |
| ths（同花顺免费） | 通 | 2584 | 2016-01-04 .. 2026-08-21 |
| free-stockdb | 本 VM 无本地引擎 | 0 | — |

默认写入缓存仍要求 `min_rows>=400`，因此 baostock 的 154 根不会覆盖研究缓存。要强行用短序列：`--sources baostock --min-rows 1`。

可选环境变量：

| 变量 | 作用 |
| --- | --- |
| `PTRADE_RESEARCH_SOURCES` | 默认源列表 |
| `THS_HEXIN_V` / `HEXIN_V` | 同花顺免费接口的 `hexin-v`（若被拦） |
| `FREE_STOCKDB_URL` | 本地引擎 HTTP，默认 `http://127.0.0.1:7899` |
| `FREE_STOCKDB_DIR` | 已导出的 parquet/csv 目录，优先于 HTTP |

可选研究依赖见 `requirements-research.txt`。未安装 baostock / akshare 时这两个源会被跳过。
