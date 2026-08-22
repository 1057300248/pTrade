# Crowding, defensive factors, gold and cross-asset momentum

CN/EN literature sweep for a **long-only cash ETF account**, compiled 2026-08-22.

## Scope and source count

- **142 unique sources**: 115 English and 27 Chinese.
- Theme counts: crowding 24; low volatility 20; quality 17; gold 29; cross-asset momentum 25; 2024-2026 China quant unwind 15; Nasdaq QDII premium 5; IM/IC basis 7.
- The row-level bibliography, language, finding and account decision are in [`lit_crowding_crossasset.csv`](./lit_crowding_crossasset.csv).
- “Unique” means one bibliography row and one normalized URL per distinct document or data page. Mirrors of the same paper are not counted twice.
- Evidence priority is peer-reviewed/working-paper research, regulators, exchanges, index providers and primary product/data pages. Broker-report mirrors and press reports are identified as such.

## Bottom line / 结论

1. **Treat crowding as an exit-risk overlay, not an alpha factor.** Common ownership, correlated signals, leverage and poor exit liquidity interact nonlinearly. Strong momentum can persist while crowded, so an automatic “high crowding = short” rule is not supported by the literature. Use crowding to reduce sizing, slow entry or require a stronger trend signal.
2. **Low volatility plus quality is the defensible equity sleeve.** The two factors overlap, but neither should be represented by one metric. For A-shares, prefer transparent indexes that combine low realized volatility with profitability, cash-flow quality, earnings stability and leverage controls.
3. **Gold remains a useful diversifier, but 2025-2026 flows make it a crowding candidate too.** Gold’s safe-haven property is conditional, not universal. Monitor fund holdings, domestic ETF creations, local premium, real-yield/currency regime and trend; do not infer future returns from record ETF inflows.
4. **Cross-asset dual momentum is suitable only as a simple allocation rule.** Relative strength chooses among eligible ETFs; an absolute trend filter moves failed sleeves to cash/short-duration bonds. Freeze lookbacks a priori, include costs and test the volatility-target contribution separately.
5. **The 2024 and 2026 China episodes are different.** February 2024 combined microcap crowding, DMA leverage, hedging constraints and forced deleveraging. July 2026 was a sharp Growth/Momentum-to-Value/Low-Vol/Quality rotation; the requested J.P. Morgan note argues it was not a broad liquidity seizure. A single “quant unwind” label hides different mechanisms.
6. **Nasdaq QDII premium is a hard tradeability gate.** `513100` can trade materially above iNAV when subscriptions or QDII capacity are constrained. Momentum on the exchange price can therefore be momentum in the premium, not in the Nasdaq-100.
7. **IM/IC basis is rejected as a position for this account.** Futures require derivatives permissions, margin, collateral, rolling and basis management. IM/IC basis can remain a risk indicator for small-cap hedge demand and crowding, but not an executable sleeve in a cash-only ETF account.

## Evidence map

| Question | Strongest usable evidence | What it supports | What it does not support |
|---|---|---|---|
| Does crowding raise crash risk? | Fire-sale, fragility, hedge-fund holding and NBFI studies ([S002](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3326802), [S005](https://www.nber.org/papers/w11357), [S008](https://doi.org/10.1016/j.jfineco.2011.06.003), [S016](https://www.imf.org/-/media/files/publications/gfsr/2023/april/english/ch2.pdf)) | A multi-input risk overlay tied to liquidity and common exposure | Calling every high-momentum ETF a bubble or timing its exact top |
| Is low volatility robust? | Global, emerging-market and China evidence ([S025](https://doi.org/10.3905/jpm.2007.698039), [S027](https://doi.org/10.1016/j.jfineco.2013.10.005), [S033](https://doi.org/10.1016/j.ememar.2013.02.004), [S041](https://doi.org/10.1057/s41260-021-00218-0)) | A defensive equity tilt with investability constraints | Assuming low volatility is valuation-insensitive or crash-proof |
| What is “quality”? | Gross profitability, F-score, QMJ and index definitions ([S045](https://doi.org/10.1016/j.jfineco.2013.01.003), [S046](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2312432), [S048](https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf), [S055](https://www.msci.com/eqb/methodology/meth_docs/MSCI_Quality_Indexes_Meth_Aug14.pdf)) | Multiple accounting dimensions with leverage and earnings-stability controls | A single ROE screen or a narrative label |
| Does gold diversify? | Safe-haven studies and primary flow data ([S062](https://ideas.repec.org/a/bla/finrev/v45y2010i2p217-229.html), [S063](https://doi.org/10.1016/j.jbankfin.2009.12.008), [S083](https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows), [S086](https://sge.com.cn/sjzx/goldEtf)) | A bounded diversifier sleeve plus explicit flow/crowding monitoring | A permanent negative correlation with equities or guaranteed inflation protection |
| Does dual momentum generalize? | Cross-sectional, time-series and long-history studies ([S091](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x), [S102](https://doi.org/10.1016/j.jfineco.2011.11.003), [S103](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750), [S104](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)) | Simple relative ranking plus absolute trend veto | Fine-grained lookback mining or ignoring momentum crashes |
| Is TSMOM alpha separable from risk scaling? | Critical and crash studies ([S108](https://doi.org/10.1016/j.jfineco.2014.11.010), [S109](https://doi.org/10.1016/j.jfineco.2015.12.002), [S113](https://doi.org/10.1016/j.finmar.2016.05.003)) | Report unscaled signal and volatility-target effects separately | Attributing the full scaled backtest return to trend prediction |

## 1. Crowding dashboard / 拥挤度监控

### What the literature measures

The evidence uses four different concepts that should not be collapsed:

- **Ownership/common exposure:** common fund holdings, hedge-fund concentration and strategy overlap.
- **Price/positioning:** momentum, valuation, residual volatility and short interest.
- **Trading intensity:** turnover, volume acceleration, order concentration and ETF creations/redemptions.
- **Exit capacity:** position size relative to normal volume, bid-ask depth, funding/margin needs and open-ended fund liquidity.

The practical implication is a dashboard, not a magic scalar. At weekly frequency, record at least:

| Block | Observable for this ETF account | Preferred interpretation |
|---|---|---|
| Price extension | 1/3/12-month return percentiles; distance from 200-day average | Trend state and acceleration, not a sell signal alone |
| Trading heat | Turnover and value-traded percentiles | Attention and exit congestion |
| Fund flow | ETF share change and estimated net creation percentile | Position accumulation; distinguish price-driven AUM growth |
| Valuation/quality | Index valuation and quality change, where available | Fragility if price extension is unsupported by fundamentals |
| Tradeability | Spread, median daily value, premium/iNAV, suspension/subscription status | Whether an otherwise valid signal can be executed |
| Cross-market stress | IM/IC basis, securities-lending rules, margin financing | Indicator only; no futures trade in this account |

### Huatai four-indicator model / 华泰四指标

The public March 2026 Huatai mirror [S023](http://ftp.microbell.com/data/ed6f88d555977bd8c9ba1bce8b4e571b.html) describes:

- four price/volume crowding indicators chosen by threshold tests;
- parameter ensembles rather than one optimized horizon;
- a trigger when more than half of a metric’s parameterizations exceed the **95th percentile of the prior 1,250 trading days**;
- one point per triggered indicator; **3 or 4 points** denotes high crowding;
- avoiding an industry when it reached 3/4 points on at least two days in the prior 20 sessions.

Important limitation: the searchable public body identifies the free-float-turnover parameter family, while the table containing all four names is image-only. The bibliography intentionally does **not** invent the other three names. Reproduction requires the original report/table or direct data specification. The 95%/3-of-4 rule is a literature reference, not a parameter selected for this strategy.

### Proposed use

- `0-1` blocks elevated: no crowding action.
- `2` blocks elevated: block new overweight and use staged entry.
- `3+` blocks elevated: cap sleeve weight, require positive absolute trend and recheck tradeability daily.
- Exit immediately only for an independent hard failure: premium breach, subscription suspension plus high premium, liquidity floor breach, or absolute trend failure.

This separates **crowding warning** from **trend exit** and avoids turning a descriptive score into an overfit timing model.

## 2. Low volatility and quality / 低波与质量

Low-volatility evidence is broad, including China, but implementation matters:

- Historical volatility and minimum-variance optimization are not interchangeable. Optimization introduces covariance estimation and constraint risk ([S038](https://www.msci.com/indexes/documents/methodology/2_MSCI_Minimum_Volatility_Indexes_Methodology_20180521.pdf), [S040](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-global-minimum-variance-index-series-ground-rules.pdf)).
- Low volatility partly loads on quality ([S034](https://doi.org/10.1016/j.rfe.2013.06.001)), yet China research finds a residual low-volatility effect after common factor controls ([S041](https://doi.org/10.1057/s41260-021-00218-0)).
- Quality definitions differ. MSCI uses ROE, debt/equity and earnings variability; S&P uses ROE, accruals and leverage; QMJ is broader. Results must name the actual index recipe.
- The most directly relevant Chinese template is CSI 300 Quality and Growth Low Volatility [S059](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/931375_Index_Methodology_cn.pdf): quality selection precedes a lowest-volatility cut, with constituent and industry caps.

**Implementation verdict:** eligible under test. Prefer one transparent China quality-low-vol ETF over separately stacking highly overlapping low-vol, dividend and quality ETFs. Check sector concentration, index turnover, fund AUM/spread and live premium before admission.

## 3. Gold and gold-ETF flows / 黄金与ETF资金流

### What survives the sweep

- Gold can hedge equities on average and act as a safe haven during some extreme equity losses, but protection is short-lived and country/regime dependent ([S062](https://ideas.repec.org/a/bla/finrev/v45y2010i2p217-229.html), [S063](https://doi.org/10.1016/j.jbankfin.2009.12.008), [S065](https://doi.org/10.1556/032.2020.00035)).
- The inflation-hedge story is not sufficient for valuation or timing ([S066](https://www.nber.org/papers/w18706)).
- Global gold ETF flows turned positive in 2024, surged in 2025, remained positive in 2026 H1 despite June outflows, and resumed inflows in July ([S078](https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2025/01), [S080](https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/01), [S081](https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/07), [S082](https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/08)).
- China’s 2025 domestic gold-ETF holdings expansion was exceptionally large ([S088](https://www.stcn.com/article/detail/3631234.html)). This supports a flow monitor, not a bullish extrapolation.

### Data hierarchy

1. World Gold Council fund-level holdings and flows [S083](https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows).
2. Shanghai Gold Exchange ETF creation/redemption data [S086](https://sge.com.cn/sjzx/goldEtf).
3. Fund issuer holdings/trust pages for GLD and IAU ([S089](https://www.spdrgoldshares.com/usa/gld/), [S090](https://www.ishares.com/us/products/239561/ishares-gold-trust-fund)).
4. SAFE official reserve data [S087](http://m.safe.gov.cn/big5/big5/www.safe.gov.cn:443/safe/2020/0207/26908.html), kept separate from private ETF demand.

**Implementation verdict:** eligible as a bounded diversifier under test. Require positive absolute trend and acceptable spread/premium; reduce or block additions when price extension, ETF creations and turnover are simultaneously extreme. ETF flow is not itself a timing signal.

## 4. Cross-asset dual momentum / 跨资产双动量

The defensible minimal form is:

1. rank a small, fixed ETF universe by a predeclared intermediate-horizon total return;
2. hold the top eligible sleeve(s);
3. require each selected sleeve to beat cash or its own long moving average;
4. send failed exposure to cash/short-duration government bonds;
5. size with a capped volatility target, reporting results both with and without scaling.

Why the constraints matter:

- Momentum exists across markets ([S101](https://doi.org/10.1111/jofi.12021), [S102](https://doi.org/10.1016/j.jfineco.2011.11.003)), but long histories also show time variation and rising strategy correlation ([S106](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2607730)).
- Momentum crashes occur after prolonged declines when high-volatility markets rebound sharply ([S109](https://doi.org/10.1016/j.jfineco.2015.12.002)).
- Volatility scaling can be a major source of reported TSMOM alpha ([S113](https://doi.org/10.1016/j.finmar.2016.05.003)); cap leverage and attribute returns explicitly.
- Moving-average and time-series-momentum filters encode closely related information ([S112](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2603731)); gridding both families is mostly redundant.
- Factor timing loses much of its apparent edge after data lags and costs ([S115](https://www.aqr.com/Insights/Research/Journal-Article/How-Do-Factor-Premia-Vary-Over-Time-A-Century-of-Evidence)).

**Implementation verdict:** eligible under test only with frozen horizons, next-session execution, adjusted total-return data, realistic premium/spread gates and a genuine OOS period.

## 5. China quant unwind, 2024-2026 / 中国量化踩踏

### February-July 2024: liquidity and leverage

The primary and contemporaneous sources align on the mechanism:

- micro/small-cap crowding and a sharp style reversal;
- leveraged DMA market-neutral products reducing leverage and size ([S120](http://www.csrc.gov.cn/csrc/c100028/c7465086/content.shtml));
- correlated program selling, including the documented Lingjun one-minute sale ([S122](https://star.sse.com.cn/regulation/trading/disposition/c/c_20240321_5736908.shtml));
- short-selling and securities-lending restrictions altering hedge availability ([S118](https://www.reuters.com/markets/asia/chinese-regulator-suspend-securities-relending-curb-short-selling-2024-07-10/));
- HFT and trading-limit enforcement expanding from cash equities to index futures ([S123](http://www.cffex.com.cn/cn/jysdt/20240228/37020.html)).

### 2025: the rules become structural

CSRC’s program-trading rule and the SSE/SZSE implementation measures formalize reporting, monitoring, system controls, HFT thresholds and differentiated fees ([S121](http://www.csrc.gov.cn/csrc/c100028/c7480577/content.shtml), [S124](http://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml), [S125](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020250403603802169453.pdf)). Backtests that assume unchanged shorting, latency or turnover economics across the rule break are not operationally faithful.

### July-August 2026: crowded factor rotation

The requested J.P. Morgan China Quant note dated 2026-08-12 is publicly discoverable only through a [third-party Scribd mirror, S128](https://www.scribd.com/document/1073401355/J-P-Morgan-China-Quant-Strategy-Momentum-Unwound-Without-a-Liquidity-Squeeze-Prefer-Defensive-Styles-Neutral-on-Momentum-260812). It reports:

- July losses in Momentum and Growth;
- strong rotation into Low Volatility and Value, with Quality positive;
- market-depth evidence inconsistent with a broad liquidity freeze;
- a defensive preference for Value/Low Vol/Quality rather than immediately re-chasing Growth.

This is useful but lower-provenance evidence: the URL is **not** an official J.P. Morgan distribution page. The July precursor [S129](https://studylib.net/doc/28691101/china-quant-strategy--expensive-leadership-is-starting-to...) has the same mirror caveat. Use the claims as a scenario description and verify against licensed research before making them model inputs.

**Regime lesson:** 2024 suggests a liquidity/leverage crash model; 2026 suggests a crowded-factor reversal model. Monitor both, and do not calibrate one stress window to explain the other.

## 6. Nasdaq QDII premium / 纳指QDII溢价

`513100` is a useful example of why an ETF signal needs a separate tradeability layer:

- The fund manager’s SSE filing [S133](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-02/513100_20260302_3IBP.pdf) says the exchange price was materially above reference NAV, subscriptions had been suspended since 2024-11-25, and temporary halts could be used.
- Official QDII quota data are published by SAFE [S134](https://www.safe.gov.cn/safe/file/file/20260529/60b3d0380b124a09a5e2c4bb39f23b49.pdf).
- Premium warnings recur across products and years ([S131](https://paper.cnstock.com/html/2024-12/23/content_2009323.htm), [S132](https://www.21jingji.com/article/20260225/herald/b36e6a1c0a6ae6ec28c9a015bfacf00d.html)).

Required controls:

- calculate `(market price / latest usable iNAV or NAV) - 1`;
- block entry above a fixed premium ceiling and while primary subscriptions are suspended;
- do not use the local close as a clean Nasdaq-100 total-return observation;
- model premium normalization separately from underlying-market return;
- prefer an uncrowded substitute only if tracking, FX, tax, liquidity and premium are all comparable.

**Verdict:** high-premium Nasdaq QDII is **rejected until the premium/tradeability gate passes**. The underlying Nasdaq exposure is not rejected.

## 7. IM/IC basis / IM、IC基差

IM (CSI 1000) and IC (CSI 500) can reveal hedge demand and neutral-strategy crowding:

- both use a RMB 200 multiplier and at least 8% contract-value margin under the cited specifications ([S136](http://www.cffex.com.cn/cn/zz1000.html), [S137](http://www.cffex.com.cn/cn/ssxz/20181228/43092.html));
- short-sale constraints, hedge demand, sentiment and roll concentration can deepen discounts beyond textbook carry ([S140](https://ideas.repec.org/a/eme/cfripp/cfri-07-2021-0144.html), [S142](https://wap.hibor.com.cn/data/f1673b803c4062cb08b6e7438d3263bd.html));
- official contract data must be joined to cash-index data to compute basis [S138](http://www.cffex.com.cn/cn/lssjxz.html).

For this repository’s cash ETF account, a basis trade would introduce:

- derivatives account and suitability requirements;
- daily variation margin and collateral liquidity;
- contract selection and roll rules;
- dividend/carry estimation;
- basis convergence and regulation risk;
- leverage that is absent from the cash ETF mandate.

**Verdict: REJECT as an executable strategy.** Retain front/next-quarter annualized IM and IC basis as read-only crowding/regime features. Never include hypothetical basis carry in the cash ETF backtest P&L.

## 8. Research and backtest protocol

Any strategy change motivated by this sweep should satisfy:

1. Define the economic role before choosing a ticker: offense, defensive equity, gold diversifier, bond/cash or unavailable.
2. Freeze the eligible universe, signal families, lookbacks, rebalance schedule and premium/liquidity gates before OOS testing.
3. Use split- and distribution-adjusted total-return data; preserve local exchange calendars and FX treatment.
4. Generate signals from information available at close `T`; fill no earlier than `T+1`.
5. Include spread, commissions, taxes where applicable, QDII premium and blocked/suspended sessions.
6. Report gross and net results, turnover, capacity, CAGR, volatility, Sharpe, MDD, worst month and crisis windows.
7. Attribute separately: relative momentum, absolute filter, volatility scaling, crowding overlay and premium gate.
8. Test the frozen choice across 2024-02 and 2026-07, but never select parameters on those windows.
9. Reject a rule whose result depends on one ETF, one rebalance date or one unadjusted split.
10. Keep live deployment status at **UNDER TEST** until a frozen OOS run and paper-trading period both pass.

## Source limitations

- This is a literature map, not an endorsement or a meta-analysis with pooled effect sizes.
- World Gold Council research is valuable for primary flow data but is industry-sponsored.
- Broker research hosted on Microbell, Nxny, Scribd, StudyLib or Hibor is a public mirror/summary, not an official distribution channel. It receives lower evidentiary weight.
- Dynamic pages can change after the retrieval date. Stable DOI, regulator, exchange and PDF links are preferred in the CSV.
- Paywalls do not make a source false, but they can prevent full-text replication. Findings here are limited to publicly visible abstracts/text.
- The 142-source count is the actual bibliography count, not a claimed count rounded to the target.
