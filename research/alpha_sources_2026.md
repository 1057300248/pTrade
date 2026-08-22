# 2026 年 A 股残余 Alpha 来源（ETF / 个人账户视角）

研究时点：2026-08-22。目标账户：国金 PTrade 个人账户，ETF 为主，日频 OHLCV（`get_history`），无 tick、无 Level-2、无融券对冲、T+1（黄金 ETF 518880 等商品/跨境品种 T+0）。

本文回答一个问题：**2026 年 7 月量化拥挤踩踏之后，还有哪些 alpha 对个人 ETF 账户是可实现的**，并给出 5 个只用日频 OHLCV 就能落地的信号。

## 一、2026-07 拥挤事件回顾

- 上半年 K 型分化：成交与收益高度集中在 AI/算力/半导体等科技高动量方向，动量因子强度处于近十年高分位（[新浪财经](https://finance.sina.com.cn/money/fund/jjzl/2026-08-20/doc-ininxkrs8013218.shtml)、[证券之星](https://4g.stockstar.com/detail/IG2026072100042063)）。
- 7 月头部反转：动量因子从高点回撤超 7%，Beta 由 +4% 转为 −1.84%，残差波动率累计 −4.74%；动量、残差波动率、流动性、短反转等本可互相对冲的因子罕见同向下跌，多因子分散逻辑阶段性失效（[同花顺](https://stock.10jqka.com.cn/20260806/c678726521.shtml)、[好买基金](https://www.howbuy.com/news/2026-07-29/5829614.html)）。
- 头部量化（含幻方/High-Flyer）单月回撤最深约 20%，触发同步降仓踩踏（[Hedgeweek](https://www.hedgeweek.com/china-quant-hedge-funds-hit-by-ai-led-selloff-as-systematic-strategies-suffer-sharp-losses/)）。
- J.P. Morgan 2026-08-12 复盘：7 月 Momentum L/S −11.0%、Growth −13.6%，同期 **Low Vol +21.8%、Value +19.0%、Quality +5.1%**；且流动性深度指标显示市场并未失灵，是拥挤仓位的定价出清而非流动性挤兑。其风格建议：防御为主，超配 Value/Low Vol/Quality，动量中性（[JPM China Quant Strategy](https://www.scribd.com/document/1073401355/J-P-Morgan-China-Quant-Strategy-Momentum-Unwound-Without-a-Liquidity-Squeeze-Prefer-Defensive-Styles-Neutral-on-Momentum-260812)）。

结论：死掉的是"裸动量 + 高 Beta + 高换手"的拥挤组合，不是全部量价 alpha。样本外仍然有效的，恰好是低拥挤、防御、以及**对拥挤本身定价**的信号。

## 二、7 月之后样本外仍成立的方向

### 仍然有效

| 方向 | 样本外证据 |
| --- | --- |
| 残差动量 | 学术上 A 股 2000–2019 残差动量月均超额 0.66%（t=3.36），显著强于总收益动量（[Blitz/Hanauer/Vidojevic, Anomalies in the China A-share market](https://pure.eur.nl/ws/files/58642799/Anomalies_in_the_China_A_share_market.pdf)；原始方法 [Blitz, Huij & Martens 2011](https://repub.eur.nl/pub/22252/ResidualMomentum-2011.pdf)）。华泰金工 2026 年复盘：时点动量与残差动量因子在行业轮动上"经受住了时间考验"（[华泰金工](https://www.163.com/dy/article/KO76I6EI05568W0A.html)）。剔除市场/风格暴露后，7 月式的因子共振对残差动量的杀伤远小于总动量。 |
| 拥挤度规避 | 华泰 4 指标量价拥挤度模型 2026 年 1 月提前预警国防军工、工业金属、贵金属的阶段性顶部；回测显示规避高拥挤行业长期正贡献（[华泰金工](https://www.163.com/dy/article/KO76I6EI05568W0A.html)）。招商证券：对高 Beta 拥挤行业做动量惩罚后，行业轮动 RankIC 9.67%、TOP5 年化超额约 11%（[招商证券](https://www.hibor.com.cn/repinfodetail_3902421.html)）。西南证券：拥挤/非拥挤分域切换信号，2013–2026.05 年化超额 11.51%（[西南证券](http://www.hibor.net/data/b9711be329ae9a5ceb81a8c7110292c4.html)）。 |
| 黄金 | 7 月以来境内黄金+黄金股 ETF 净流入超 200 亿元，规模重回 3000 亿上方；降息预期 + 央行连续 21 个月购金 + 从拥挤科技仓位再配置的跨资产资金（[新浪财经](https://finance.sina.com.cn/jjxw/2026-08-12/doc-inimzqcs5381956.shtml)）。7/1–8 月初中证黄金产业股票指数 +23.4%，弹性约为现货 3 倍（[同花顺](https://invest.10jqka.com.cn/20260808/c678776465.shtml)）。黄金是趋势/配置 beta，不与量化拥挤同源。 |
| 红利 / 低波 | 7 月中证红利低波 100 单月 +10.96%，红利整体跑赢大盘超 24 个百分点；股息率 4.3–4.4% 对 10 年国债 1.73%，息差约 2.6–3.6pp，处于历史"击球区"（[新浪财经](https://finance.sina.com.cn/roll/2026-08-14/doc-ininhtfh4144443.shtml)、[FX168](https://www.fx168news.com/article/1070459)）。低利率 + 资产荒是慢变量，容量大、不怕拥挤出清。 |
| 行业 ETF 轮动 | 动量 + 拥挤惩罚的行业轮动在 2026 年样本外继续有效：周频调仓相对月频信号保留更好，行业周频多头年化超额 12.85%、映射到 ETF 后 15.35%（[国泰海通 ETF 配置系列八](https://max.book118.com/html/2026/0702/8076043131010105.shtm)）。改进方向普遍是"长动量减短动量"、拥挤度排雷（[国泰海通系列五](http://www.huiyunyan.com/doc-3613f39e97f64a2d056c25f56389e0e6.html)）。 |

### 明确放弃

| 方向 | 原因 |
| --- | --- |
| 微盘 / 小微市值 | 尽管 8 月初小市值因子拥挤度 −1.00 逼近历史极低、有均值回归论调（[同花顺](https://stock.10jqka.com.cn/20260805/c678683195.shtml)），但该交易本质是接量化减仓的流动性刀口：2024 年初微盘流动性危机与本轮 7 月微盘拖累都证明尾部风险极端；个人账户无法像机构一样持 600–900 只票分散，单票微盘的冲击成本与退市/停牌风险不可控。不做。 |
| 高频 / 日内 | PTrade 个人账户无 tick、无低延迟通道，T+1 制度下股票 ETF 日内往返本身受限；高频 alpha 属于基础设施竞赛，个人零胜率。不做。 |
| 国盛证券 tick 资金流因子 | 该类因子（主动买卖单拆分、大小单资金流）依赖 tick / 逐笔数据重构订单流。PTrade `get_history` 只有日频/分钟 OHLCV，**没有 tick**，因子无法计算；用日频量价近似会退化成普通量价因子且失真。不做。 |

## 三、5 个可落地信号（只用日频 OHLCV）

所有信号的数据需求都是 `get_history` 的 `open/high/low/close/volume/amount`，周频（每周最后一个交易日收盘信号、次日开盘或收盘执行，T+1 一致）。

### 信号 1：ETF 残差动量（RMDC 核心，已在 `ptrade_rmdc_etf.py`）

- 池：行业/主题 ETF ≈ 15–25 只（互不高度重叠）。
- 计算：每只 ETF 日收益对沪深 300 ETF（510300）日收益做滚动 OLS，**回归窗口 120 日**；取残差序列，**形成期 = 最近 60 日残差累计和，跳过最近 5 日**（规避短期反转），再除以同 60 日残差标准差（残差夏普式打分）。
- 持仓：得分 TOP 3–5 等权，周频换仓。
- 依据：Blitz/Huij/Martens 2011 —— 残差动量夏普约为总动量 2 倍、波动低 45%；A 股样本 0.66%/月（t=3.36）。剔除市场 beta 后，2026-07 式的"动量 = 高 Beta = 高波动"共振被结构性削弱。
- 回看参数汇总：120d（回归）/ 60d（形成）/ 5d（跳过）。

### 信号 2：量价拥挤度否决（overlay，覆盖在信号 1/3 之上）

- 对每只候选 ETF 计算 4 个日频拥挤指标，各取**滚动 1250 日（约 5 年）分位数**：
  1. 成交额分位：20 日均 `amount` 的 1250 日分位；
  2. 换手热度分位：20 日均 `volume` 的 1250 日分位（ETF 份额变动缺失时的换手代理）；
  3. 波动分位：20 日收益标准差的 1250 日分位；
  4. 涨幅分位：60 日累计收益的 1250 日分位。
- 单指标分位 ≥ 95% 记 1 分，合计 ≥ 3 分记当日"高拥挤"；**最近 20 日内有 ≥ 2 天高拥挤则该 ETF 一票否决**（从买入名单剔除，已持有则减半或清出）。
- 依据：华泰 4 指标模型（同为 1250 日分位、95% 阈值、3/4 分触发、20 日窗观察），2026 年 1 月实盘级预警国防军工/工业金属/贵金属顶部；规避高拥挤长期正贡献。
- 回看参数汇总：1250d（分位基准）/ 20d（指标平滑与触发窗）/ 60d（涨幅）。

### 信号 3：动量期限差行业轮动（长动量 − 短动量）

- 池：申万一级映射的行业 ETF。
- 计算：**因子 = 近 10 日收益 − 近 5 日收益**（国泰海通"动量期限差"原式）。长端动量代表趋势与筹码沉淀，短端动量过高代表短期拥挤；相减即"未拥挤的趋势"。可叠加**近 10 日累计日内动量 Σ(close/open − 1)** 做第二排序键（日内涨幅由真实资金推动，趋势延续性强于隔夜）。
- 持仓：TOP 3 等权，周频；跌破 60 日均线的行业不买。
- 依据：国泰海通 ETF 配置系列五/八 —— 该类因子构成的行业组合样本外（含 2026 年）周频年化超额 12–15%；招商证券拥挤惩罚动量 RankIC 9.67%。
- 回看参数汇总：10d / 5d（期限差）、10d（日内动量）、60d（趋势过滤）。

### 信号 4：红利低波底仓 + 相对强弱开关

- 标的：红利低波 ETF（512890 / 563020）或红利 ETF（515180）。
- 计算：**相对强弱 = 红利 ETF 60 日收益 − 510300 的 60 日收益**；且红利 ETF 收盘价 > 自身 **120 日均线**。两条件同时满足→底仓权重 30–40%；只满足均线条件→20%；均不满足→归入进攻仓位池。
- 依据：7 月红利低波单月 +10.96%、对大盘超额 24pp 的样本外验证；股息率−国债息差 2.6–3.6pp 提供估值锚，容量极大（年内红利 ETF 净流入 200 亿+），拥挤出清风险与量价因子不同源；JPM 建议超配 Low Vol/Value。
- 回看参数汇总：60d（相对强弱）/ 120d（趋势）。
- 风险注记：红利低波指数银行权重普遍 >50%，若需分散可与红利质量类搭配。

### 信号 5：黄金 ETF 绝对动量（趋势跟随，T+0 品种）

- 标的：黄金 ETF 518880（T+0，可当日纠错）；激进替代：黄金股 ETF（约 3 倍现货弹性，按波动倒数缩仓）。
- 计算：**双条件绝对动量**——收盘价 > **100 日均线** 且 **20 日收益 > 0** →持有；任一失效→退出到货币 ETF（511990/511880）。仓位 = 目标波动 10% 年化 ÷ 该 ETF **20 日已实现波动**，上限 20%。
- 依据：7 月以来黄金+黄金股 ETF 净流入 200 亿+、央行 21 个月连续购金的慢变量支撑；趋势过滤解决"高位追涨"问题（8 月中旬头部黄金 ETF 已现连续 3 日净流出的获利了结信号，[BT 财经](https://businesstimescn.com/articles/623584.html)），跌破趋势线机械离场。
- 回看参数汇总：100d（趋势）/ 20d（动量与波动）。

## 四、组合视角

- 结构：信号 4（红利底仓 20–40%）+ 信号 5（黄金 0–20%）为防御层；信号 1 + 信号 3（合计 40–60%）为进攻层；信号 2 作为全局否决 overlay。
- 所有回看窗口 ≤ 1250 日，`get_history` 一次拉取即可；周频调仓将换手压到个人佣金结构可承受范围。
- 最大的单一风险不是某个因子失效，而是再次发生因子共振——信号 2 的拥挤否决和信号 4/5 的防御层就是针对这一点设计的。

## 五、截面 Rank IC 为何判残差动量死刑、以及下一步

本节记录 walk-forward（`research/factor_walkforward.py`，扩窗、防泄漏）对本文信号的裁决，以及由此确定的实盘路线。

- **判决**：在 35 只混合池（股票行业/宽基 + 债券 + 黄金/商品 ETF）的扩窗 walk-forward 中，`residual_mom` 的截面 Rank IC IR 为 **−0.099**，且全部候选因子无一达到 prior-OOS IR > 0.30 的上线门槛。这是对"残差动量作为**混合资产 ETF 池的截面排序器**"的有效否决——信号 1 的原始形态（跨类 ETF 截面打分选 TOP N）不再上实盘。
- **判决边界**：这**不是**对学术残差动量的否决。Blitz/Huij/Martens 的结论建立在 A 股**个股**截面、剔除市场/风格因子暴露后的残差上（0.66%/月，t=3.36）；混合 ETF 池的截面 IC 度量的是资产类别轮动能力，两者不是同一个假设，前者未被本次 WF 触碰。
- **不要引用残差化后的截面 IC**：对池内每只 ETF 减去同一条黄金或债券收益序列，截面排名**不变**（对共同项平移是 rank-invariant 的）。因此"减黄金/减债券后的 CS IC"与原始 CS IC 是同一个数，不构成新证据，本文及后续研究一律不引用。
- **5 个信号映射到 GEM sleeve 框架**（sleeve 内自比、sleeve 间配权，不再做跨类截面排序）：信号 1 → GROWTH sleeve 内部的 **12-1 时序动量**（约 250 日形成期、跳过最近 20 日，对自身历史或现金基准比较，非截面）；信号 2 → 拥挤度否决 overlay，覆盖所有权益 sleeve；信号 4 → dividend-lowvol sleeve（红利低波底仓）；信号 5 → gold absolute momentum sleeve（黄金绝对动量，逻辑本就是时序而非截面，不受本判决影响）。
- **信号 3（动量期限差）降级为 research-only**：在它**单独**通过纯股票行业 ETF 池的独立 walk-forward（同样的扩窗、防泄漏、prior-OOS 门槛）之前，不进入实盘代码。
- **下一个实盘文件是 `ptrade_gem_etf.py`**：GEM 双动量骨架（sleeve 内绝对动量决定持有/退出到货币 ETF，sleeve 间相对动量与固定上限配权），**不是**再做一个残差动量组合。

## 参考来源

1. 新浪财经《两轮量化回撤，风险来源有何不同？》2026-08-20 — https://finance.sina.com.cn/money/fund/jjzl/2026-08-20/doc-ininxkrs8013218.shtml
2. 同花顺《量化私募的"压力测试"》2026-08-06 — https://stock.10jqka.com.cn/20260806/c678726521.shtml
3. 好买基金《量化超额收益荒》2026-07-29 — https://www.howbuy.com/news/2026-07-29/5829614.html
4. Hedgeweek, China quant hedge funds hit by AI-led selloff, 2026-07 — https://www.hedgeweek.com/china-quant-hedge-funds-hit-by-ai-led-selloff-as-systematic-strategies-suffer-sharp-losses/
5. J.P. Morgan China Quant Strategy, Momentum Unwound Without a Liquidity Squeeze, 2026-08-12 — https://www.scribd.com/document/1073401355/
6. Blitz, Huij & Martens, Residual Momentum, JEF 2011 — https://repub.eur.nl/pub/22252/ResidualMomentum-2011.pdf
7. Blitz, Hanauer & Vidojevic, Anomalies in the China A-share market — https://pure.eur.nl/ws/files/58642799/Anomalies_in_the_China_A_share_market.pdf
8. 华泰金工《量化行业轮动的"崎岖"》（残差动量 + 拥挤度模型，2026）— https://www.163.com/dy/article/KO76I6EI05568W0A.html
9. 招商证券《行业动量策略的改进与 ETF 组合落地》— https://www.hibor.com.cn/repinfodetail_3902421.html
10. 西南证券《基于拥挤度的动态分域行业配置策略》— http://www.hibor.net/data/b9711be329ae9a5ceb81a8c7110292c4.html
11. 国泰海通《ETF 配置系列（五）（八）》2026 — http://www.huiyunyan.com/doc-3613f39e97f64a2d056c25f56389e0e6.html / https://max.book118.com/html/2026/0702/8076043131010105.shtm
12. 新浪财经《重回 3000 亿元！黄金相关 ETF 大举"吸金"》2026-08-12 — https://finance.sina.com.cn/jjxw/2026-08-12/doc-inimzqcs5381956.shtml
13. 同花顺《现货黄金站上 4300 美元》2026-08-08 — https://invest.10jqka.com.cn/20260808/c678776465.shtml
14. 新浪财经《红利 ETF 三天累计净流入 8.67 亿元》2026-08-14 — https://finance.sina.com.cn/roll/2026-08-14/doc-ininhtfh4144443.shtml
15. 同花顺《小市值因子拥挤度触及历史极低值》2026-08-05 — https://stock.10jqka.com.cn/20260805/c678683195.shtml
16. BT 财经《黄金 ETF 两个月吸金 187 亿，但头部产品突然连续净流出》2026-08 — https://businesstimescn.com/articles/623584.html
