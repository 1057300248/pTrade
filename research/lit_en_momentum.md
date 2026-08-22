# English Academic Sweep: Momentum, ETF Rotation, A-Share Anomalies

Scope: time-series momentum, dual momentum, residual momentum, ETF rotation,
A-share anomalies, momentum crashes, crowding/capacity, transaction costs,
and recent (2023-2026) arXiv/SSRN work.

**Total unique sources: 190** (target was >=125).
Composition: 21 arxiv, 1 book, 1 book-chapter, 144 journal, 3 working-nber, 20 working-ssrn

URL verification: every journal/SSRN/NBER entry was resolved through the
Crossref API (title + author match, then a direct per-DOI lookup); arXiv IDs
were verified against the arXiv API; the two non-DOI entries (JOIM article,
Antonacci book) were verified by web search. No URL is hand-invented.
All `doi.org` links resolve to the publisher or SSRN landing page.

Companion file: `research/lit_en_momentum.csv`
(columns: `id,type,year,title,url,venue,relevance_one_line`).

## Time-Series Momentum & Trend Following (25)

- **EN-001** Brock, Lakonishok & LeBaron (1992). *Simple Technical Trading Rules and the Stochastic Properties of Stock Returns*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.1992.tb04681.x>
  Brock-Lakonishok-LeBaron classic: technical trading rules on the Dow; the original evidence and its data-snooping caveats.
- **EN-002** Szakmary, Shen & Sharma (2010). *Trend-following trading strategies in commodity futures: A re-examination*. Journal of Banking & Finance. <https://doi.org/10.1016/j.jbankfin.2009.08.004>
  Commodity trend-following rules profitable over decades; out-of-sample support for simple trend filters.
- **EN-003** Baltas & Kosowski (2011). *Momentum Strategies in Futures Markets and Trend-following Funds*. SSRN working paper. <https://doi.org/10.2139/ssrn.1968996>
  Baltas-Kosowski: TSMOM in futures explains CTA returns; capacity and correlation structure of trend strategies.
- **EN-004** Moskowitz, Ooi & Pedersen (2012). *Time series momentum*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2011.11.003>
  Canonical TSMOM paper: 12m own-return sign predicts futures returns across 58 assets; basis for our absolute-momentum gates.
- **EN-005** Han, Yang & Zhou (2013). *A New Anomaly: The Cross-Sectional Profitability of Technical Analysis*. Journal of Financial and Quantitative Analysis. <https://doi.org/10.1017/s0022109013000586>
  Han-Yang-Zhou: MA timing on volatility-sorted portfolios earns large cross-sectional profits; technical analysis as anomaly.
- **EN-006** Neely et al. (2014). *Forecasting the Equity Risk Premium: The Role of Technical Indicators*. Management Science. <https://doi.org/10.1287/mnsc.2013.1838>
  Neely et al: technical indicators forecast equity premium as well as macro variables, especially in recessions.
- **EN-007** Dudler, Gmuer & Malamud (2014). *Risk Adjusted Time Series Momentum*. SSRN working paper. <https://doi.org/10.2139/ssrn.2457647>
  Risk-adjusted TSMOM: scaling positions by vol improves crisis behavior; template for our vol-targeted books.
- **EN-008** Zakamulin (2014). *The real-life performance of market timing with moving average and time-series momentum rules*. Journal of Asset Management. <https://doi.org/10.1057/jam.2014.25>
  Zakamulin: realistic out-of-sample market timing with MA/TSMOM is far weaker than in backtests; anti-overfit caution.
- **EN-009** Lemperiere et al. (2014). *Two Centuries of Trend Following*. arXiv preprint. <https://arxiv.org/abs/1404.3274>
  CFM: trend following statistically significant for two centuries across all asset classes; deep prior for trend persistence.
- **EN-010** D’Souza et al. (2016). *The Enduring Effect of Time-Series Momentum on Stock Returns Over Nearly 100-Years*. SSRN working paper. <https://doi.org/10.2139/ssrn.2720600>
  TSMOM on US stocks over ~100 years remains profitable; long-sample robustness for time-series rules.
- **EN-011** Clare et al. (2016). *The trend is our friend: Risk parity, momentum and trend following in global asset allocation*. Journal of Behavioral and Experimental Finance. <https://doi.org/10.1016/j.jbef.2016.01.002>
  Clare et al: trend following beats buy-and-hold in global multi-asset allocation; direct TAA evidence.
- **EN-012** Kim, Tse & Wald (2016). *Time series momentum and volatility scaling*. Journal of Financial Markets. <https://doi.org/10.1016/j.finmar.2016.05.003>
  Shows TSMOM profits largely come from volatility scaling; relevant to our inverse-vol weighting choice.
- **EN-013** Levine & Pedersen (2016). *Which Trend Is Your Friend?*. Financial Analysts Journal. <https://doi.org/10.2469/faj.v72.n3.3>
  Levine-Pedersen: which trend definition (MA crossovers vs returns) matters less than vol scaling and horizon.
- **EN-014** Hurst, Ooi & Pedersen (2017). *A Century of Evidence on Trend-Following Investing*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2017.44.1.015>
  Hurst-Ooi-Pedersen: trend following profitable in every decade since 1880; long-horizon prior for trend overlays.
- **EN-015** Georgopoulou & Wang (2017). *The Trend Is Your Friend: Time-Series Momentum Strategies across Equity and Commodity Markets*. Review of Finance. <https://doi.org/10.1093/rof/rfw048>
  TSMOM works across international equity and commodity markets; supports cross-market generalization of our ETF rules.
- **EN-016** Marshall, Nguyen & Visaltanachoti (2017). *Time series momentum and moving average trading rules*. Quantitative Finance. <https://doi.org/10.1080/14697688.2016.1205209>
  Proves TSMOM and moving-average rules are near-equivalent signals; justifies treating MA filters as TSMOM variants.
- **EN-017** Goyal & Jegadeesh (2018). *Cross-Sectional and Time-Series Tests of Return Predictability: What Is the Difference?*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhx131>
  Goyal-Jegadeesh: TS vs XS momentum difference is mostly the net long position; clarifies what our long-only rotation actually harvests.
- **EN-018** Gupta & Kelly (2019). *Factor Momentum Everywhere*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2019.45.3.013>
  Gupta-Kelly: momentum of factor returns themselves is pervasive; factor-of-factor timing evidence.
- **EN-019** Garg et al. (2019). *Momentum Turning Points*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.3489539>
  Garg-Goulding-Harvey-Mazzoleni: momentum turning points (slow vs fast signal disagreement) drive strategy risk; motivates dual-lookback gates.
- **EN-020** Baltas & Kosowski (2020). *Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and Pairwise Correlations*. Market Momentum. <https://doi.org/10.1002/9781119599364.ch3>
  Baltas-Kosowski follow-up: volatility estimators, trading rules and pairwise correlations materially change TSMOM Sharpe.
- **EN-021** Huang et al. (2020). *Time series momentum: Is it there?*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2019.08.004>
  Huang-Li-Wang-Zhou critique: TSMOM t-stats weak asset-by-asset; sign rule partly fits the mean - keep expectations honest.
- **EN-022** Ehsani & Linnainmaa (2022). *Factor Momentum and the Momentum Factor*. The Journal of Finance. <https://doi.org/10.1111/jofi.13131>
  Ehsani-Linnainmaa: stock momentum largely reflects factor momentum; changes what a momentum screen actually picks up.
- **EN-023** Arnott, Kalesnik & Linnainmaa (2023). *Factor Momentum*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhad006>
  Arnott et al: factor momentum is strongest in the first month and concentrated in unpriced factors.
- **EN-024** Goulding, Harvey & Mazzoleni (2024). *Breaking Bad Trends*. Financial Analysts Journal. <https://doi.org/10.1080/0015198x.2023.2270084>
  Breaking Bad Trends: dynamic trend speed selection cuts whipsaw losses at turning points; practical fix we can borrow.
- **EN-025** Sepp & Lucic (2026). *The Science and Practice of Trend-Following Systems*. arXiv preprint. <https://arxiv.org/abs/2607.19497>
  Sepp-Lucic 2026: comprehensive practitioner treatment of trend system design choices (signals, sizing, portfolio construction).

## Cross-Sectional Momentum: Classics & Mechanisms (30)

- **EN-026** Jegadeesh & Titman (1993). *Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.1993.tb04702.x>
  Jegadeesh-Titman 1993: the original 3-12 month winner-loser momentum; foundation of every relative-strength rule we run.
- **EN-027** Carhart (1997). *On Persistence in Mutual Fund Performance*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.1997.tb03808.x>
  Carhart: adds UMD to the 3-factor model; the standard benchmark for judging momentum alpha.
- **EN-028** Asness (1997). *The Interaction of Value and Momentum Strategies*. Financial Analysts Journal. <https://doi.org/10.2469/faj.v53.n2.2069>
  Asness: momentum works best among expensive stocks and vice versa; value-momentum interaction mechanics.
- **EN-029** Barberis, Shleifer & Vishny (1998). *A model of investor sentiment*. Journal of Financial Economics. <https://doi.org/10.1016/s0304-405x(98)00027-0>
  Barberis-Shleifer-Vishny: conservatism and representativeness produce underreaction (momentum) and overreaction (reversal).
- **EN-030** Rouwenhorst (1998). *International Momentum Strategies*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.95722>
  Rouwenhorst: momentum in 12 European markets; first major out-of-sample international confirmation.
- **EN-031** Daniel, Hirshleifer & Subrahmanyam (1998). *Investor Psychology and Security Market Under- and Overreactions*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.00077>
  Daniel-Hirshleifer-Subrahmanyam: overconfidence and self-attribution as the behavioral engine of momentum.
- **EN-032** Hong & Stein (1999). *A Unified Theory of Underreaction, Momentum Trading, and Overreaction in Asset Markets*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.00184>
  Hong-Stein model: gradual information diffusion plus trend chasers generate momentum then reversal.
- **EN-033** Moskowitz & Grinblatt (1999). *Do Industries Explain Momentum?*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.00146>
  Moskowitz-Grinblatt: industry momentum subsumes much of stock momentum; direct motivation for sector/ETF rotation.
- **EN-034** Hong, Lim & Stein (2000). *Bad News Travels Slowly: Size, Analyst Coverage, and the Profitability of Momentum Strategies*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.00206>
  Hong-Lim-Stein: momentum strongest in small, low-analyst-coverage stocks; information diffusion evidence.
- **EN-035** Jegadeesh & Titman (2001). *Profitability of Momentum Strategies: An Evaluation of Alternative Explanations*. The Journal of Finance. <https://doi.org/10.1111/0022-1082.00342>
  Jegadeesh-Titman 2001: momentum persists out-of-sample post-publication with long-horizon reversal; behavioral interpretation.
- **EN-036** Grundy & Martin (2001). *Understanding the Nature of the Risks and the Source of the Rewards to Momentum Investing*. Review of Financial Studies. <https://doi.org/10.1093/rfs/14.1.29>
  Grundy-Martin: momentum's dynamic factor exposures create crash risk when hedged naively; early crash warning.
- **EN-037** Lewellen (2002). *Momentum and Autocorrelation in Stock Returns*. Review of Financial Studies. <https://doi.org/10.1093/rfs/15.2.533>
  Lewellen: momentum in size/BM portfolios too large for individual-stock underreaction stories alone.
- **EN-038** Griffin, Ji & Martin (2003). *Momentum Investing and Business Cycle Risk: Evidence from Pole to Pole*. The Journal of Finance. <https://doi.org/10.1046/j.1540-6261.2003.00614.x>
  Griffin-Ji-Martin: momentum profits worldwide, weakly related to business-cycle risk; hard to explain as risk premium.
- **EN-039** Cooper, Gutierrez & Hameed (2004). *Market States and Momentum*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2004.00665.x>
  Cooper-Gutierrez-Hameed: momentum profits follow UP markets and vanish after DOWN markets; simple regime conditioning.
- **EN-040** George & Hwang (2004). *The 52-Week High and Momentum Investing*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2004.00695.x>
  George-Hwang: distance to 52-week high beats past returns as a momentum signal; anchoring-based alternative ranking.
- **EN-041** Avramov et al. (2007). *Momentum and Credit Rating*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2007.01282.x>
  Avramov et al: momentum concentrated in low-credit-quality firms; junk drives the anomaly.
- **EN-042** Heston & Sadka (2008). *Seasonality in the cross-section of stock returns*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2007.02.003>
  Heston-Sadka: 12-month-multiple seasonality in returns; contaminates naive momentum lookbacks.
- **EN-043** Chui, Titman & Wei (2010). *Individualism and Momentum around the World*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2009.01532.x>
  Chui-Titman-Wei: momentum strength varies with individualism across countries; why China momentum differs.
- **EN-044** Novy-Marx (2012). *Is momentum really momentum?*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2011.05.003>
  Novy-Marx: momentum driven by 12-7 month returns, not recent ones; lookback window selection matters.
- **EN-045** Fama & French (2012). *Size, value, and momentum in international stock returns*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2012.05.011>
  Fama-French: size/value/momentum in four global regions; momentum everywhere except Japan.
- **EN-046** Israel & Moskowitz (2013). *The role of shorting, firm size, and time on market anomalies*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2012.11.005>
  Israel-Moskowitz: momentum robust across size and time; shorting is not essential - supports long-only implementations.
- **EN-047** Asness, Moskowitz & Pedersen (2013). *Value and Momentum Everywhere*. The Journal of Finance. <https://doi.org/10.1111/jofi.12021>
  Asness-Moskowitz-Pedersen: value and momentum premia everywhere, negatively correlated; core case for combining them.
- **EN-048** Asness et al. (2014). *Fact, Fiction, and Momentum Investing*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2014.40.5.075>
  AQR's fact-check of momentum myths (costs, taxes, decay); practical rebuttals with data.
- **EN-049** Da, Gurun & Warachka (2014). *Frog in the Pan: Continuous Information and Momentum*. Review of Financial Studies. <https://doi.org/10.1093/rfs/hhu003>
  Frog-in-the-pan: continuous small news generates stronger momentum than discrete jumps; signal-quality filter idea.
- **EN-050** Chabot, Ghysels & Jagannathan (2014). *Momentum Trading, Return Chasing, and Predictable Crashes*. NBER working paper. <https://doi.org/10.3386/w20660>
  Chabot-Ghysels-Jagannathan: Victorian-era momentum also crashed predictably; crashes are intrinsic, not modern.
- **EN-051** Fama & French (2016). *Dissecting Anomalies with a Five-Factor Model*. Review of Financial Studies. <https://doi.org/10.1093/rfs/hhv043>
  Fama-French: five-factor lens on anomalies; momentum survives as the big unexplained one.
- **EN-052** Keloharju, Linnainmaa & Nyberg (2016). *Return Seasonalities*. The Journal of Finance. <https://doi.org/10.1111/jofi.12398>
  Keloharju-Linnainmaa-Nyberg: return seasonalities pervade all major anomalies including momentum.
- **EN-053** Geczy & Samonov (2016). *Two Centuries of Price-Return Momentum*. Financial Analysts Journal. <https://doi.org/10.2469/faj.v72.n5.1>
  Geczy-Samonov: 212 years of US momentum including its worst crashes; longest-sample stress test.
- **EN-054** Goetzmann & Huang (2018). *Momentum in Imperial Russia*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2018.07.008>
  Momentum in 1865-1914 Imperial Russia; pre-modern out-of-sample confirmation.
- **EN-055** Bouchaud et al. (2019). *Sticky Expectations and the Profitability Anomaly*. The Journal of Finance. <https://doi.org/10.1111/jofi.12734>
  Bouchaud et al: sticky analyst expectations explain profitability momentum; mechanism evidence.

## Momentum Crashes & Risk-Managed Momentum (23)

- **EN-056** Stivers & Sun (2010). *Cross-Sectional Return Dispersion and Time Variation in Value and Momentum Premiums*. Journal of Financial and Quantitative Analysis. <https://doi.org/10.1017/s0022109010000384>
  Stivers-Sun: cross-sectional return dispersion predicts momentum premium sign; cheap regime signal.
- **EN-057** Daniel, Jagannathan & Kim (2012). *Tail Risk in Momentum Strategy Returns*. NBER working paper. <https://doi.org/10.3386/w18169>
  Daniel-Jagannathan-Kim: hidden Markov model of momentum tail risk; regime-switching crash detection.
- **EN-058** Wang & Xu (2015). *Market volatility and momentum*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2014.11.009>
  Wang-Xu: market volatility forecasts momentum payoffs, especially after down markets.
- **EN-059** Barroso & Santa-Clara (2015). *Momentum has its moments*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2014.11.010>
  Barroso-Santa-Clara: scaling momentum by its own realized vol doubles Sharpe and kills crashes; direct recipe.
- **EN-060** Daniel & Moskowitz (2016). *Momentum crashes*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2015.12.002>
  Daniel-Moskowitz: momentum crashes in panic states via short-leg optionality; the paper our crash-overlay logic descends from.
- **EN-061** Moreira & Muir (2017). *Volatility-Managed Portfolios*. The Journal of Finance. <https://doi.org/10.1111/jofi.12513>
  Moreira-Muir: vol-managed versions of major factors raise alpha; theoretical basis for vol targeting.
- **EN-062** Bollerslev et al. (2018). *Risk Everywhere: Modeling and Managing Volatility*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhy041>
  Bollerslev et al: realized-vol modeling across assets; the estimation layer under any vol-managed book.
- **EN-063** Grobys, Ruotsalainen & Äijö (2018). *Risk-managed industry momentum and momentum crashes*. Quantitative Finance. <https://doi.org/10.1080/14697688.2017.1420211>
  Risk-managed industry momentum: constant-vol scaling fixes industry momentum crashes; sector-level fix relevant to ETF rotation.
- **EN-064** Harvey et al. (2018). *The Impact of Volatility Targeting*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2018.45.1.014>
  Man/AHL study: vol targeting improves Sharpe mainly for risk assets and cuts left tails; supports our 16% vol target.
- **EN-065** Atilgan et al. (2020). *Left-tail momentum: Underreaction to bad news, costly arbitrage and equity returns*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2019.07.006>
  Left-tail momentum: stocks with recent large losses keep underperforming; asymmetric-tail complement to winner momentum.
- **EN-066** Cederburg et al. (2020). *On the performance of volatility-managed portfolios*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2020.04.015>
  Cederburg et al: vol-managed portfolios fail in real-time spanning tests for most factors; sobering counterpoint.
- **EN-067** Rattray et al. (2020). *Strategic Rebalancing*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2020.1.150>
  Strategic rebalancing: mechanical rebalance timing interacts with momentum; trade-scheduling insight for weekly rebalances.
- **EN-068** Barroso & Detzel (2021). *Do limits to arbitrage explain the benefits of volatility-managed portfolios?*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.02.009>
  Barroso-Detzel: vol management's benefits survive costs mainly for momentum; limits-to-arbitrage explanation.
- **EN-069** Dierkes & Krupski (2022). *Isolating momentum crashes*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2021.12.001>
  Dierkes-Krupski: ex-ante beta/vol crash indicator isolates momentum crashes; implementable overlay that beats prior fixes.
- **EN-070** Iwanaga & Sakemoto (2023). *Commodity momentum decomposition*. Journal of Futures Markets. <https://doi.org/10.1002/fut.22382>
  Commodity momentum decomposition: separates auto-covariance vs cross-covariance sources; diagnostic for signal design.
- **EN-071** Hanauer & Windmüller (2023). *Enhanced momentum strategies*. Journal of Banking & Finance. <https://doi.org/10.1016/j.jbankfin.2022.106712>
  Hanauer-Windmueller: enhanced (vol-scaled, crash-aware) momentum works internationally after costs.
- **EN-072** Byun & Jeon (2023). *Momentum Crashes and the 52-Week High*. Financial Analysts Journal. <https://doi.org/10.1080/0015198x.2023.2183706>
  Byun-Jeon 2023: neutralizing the 52-week-high effect attenuates momentum crashes and lifts Sharpe.
- **EN-073** Butt, Kolari & Sadaqat (2023). *Momentum, Market Volatility, and Reversal*. SSRN working paper. <https://doi.org/10.2139/ssrn.4478316>
  Butt-Kolari-Sadaqat 2023-24 SSRN: switch momentum-to-reversal when volatility is high; constant-leverage crash avoidance.
- **EN-074** Büsing, Mohrschladt & Siedhoff (2024). *Decomposing momentum: The forgotten component*. Journal of Banking & Finance. <https://doi.org/10.1016/j.jbankfin.2024.107292>
  Buesing et al 2024: the 'forgotten' overnight/intraday component of momentum; decomposition matters for T+1 fills.
- **EN-075** Ghazi, Schneider & Strauss (2025). *Momentum is still there conditional on volatility-amplified pessimism*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2025.101653>
  2025: momentum survives conditional on volatility-amplified pessimism; newest regime-conditioning evidence.
- **EN-076** Han (2025). *Understanding price momentum, market fluctuations, and crashes: insights from the extended Samuelson model*. Financial Innovation. <https://doi.org/10.1186/s40854-024-00743-y>
  2025: extended Samuelson model linking momentum, fluctuations and crashes in one framework.
- **EN-077** Noguer i Alonso & Al Fallouji (2026). *Tail Risk Management with Puts and Trend Following: A CVaR Framework for Crashes*. arXiv preprint. <https://arxiv.org/abs/2607.00883>
  2026 arXiv: CVaR framework combining puts with trend following for crash protection; overlay cost-benefit analysis.
- **EN-078** Chakraborty & Singh (2026). *Taming the Black Swan: A Momentum-Gated Hierarchical Optimisation Framework*. arXiv preprint. <https://arxiv.org/abs/2604.09060>
  2026 arXiv: momentum-gated hierarchical optimisation aimed at black-swan drawdowns; recent crash-management design.

## Residual & Idiosyncratic Momentum (6)

- **EN-079** Gutierrez & Prinsky (2007). *Momentum, reversal, and the trading behaviors of institutions*. Journal of Financial Markets. <https://doi.org/10.1016/j.finmar.2006.09.002>
  Gutierrez-Pirinsky: institutions trade residual returns; why residual momentum has a distinct clientele.
- **EN-080** Blitz, Huij & Martens (2011). *Residual momentum*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2011.01.003>
  Blitz-Huij-Martens: momentum on FF3 residuals halves factor risk and doubles Sharpe; the residual-momentum blueprint (our RMDC).
- **EN-081** Blitz et al. (2013). *Short-term residual reversal*. Journal of Financial Markets. <https://doi.org/10.1016/j.finmar.2012.10.005>
  Blitz et al: short-term residual reversal profits; the mean-reversion mirror of residual momentum at short horizons.
- **EN-082** Hühn & Scholz (2018). *Alpha Momentum and Price Momentum*. International Journal of Financial Studies. <https://doi.org/10.3390/ijfs6020049>
  Huehn-Scholz: alpha momentum (ranking on estimated alphas) vs price momentum; alternative residual-type ranking.
- **EN-083** Chang et al. (2018). *Residual momentum in Japan*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2017.11.005>
  Residual momentum profitable in Japan where raw momentum famously fails; strongest possible out-of-sample test.
- **EN-084** Blitz, Hanauer & Vidojevic (2020). *The idiosyncratic momentum anomaly*. International Review of Economics & Finance. <https://doi.org/10.1016/j.iref.2020.05.008>
  Blitz-Hanauer-Vidojevic: idiosyncratic momentum works globally and survives factor adjustments; robustness of residual momentum.

## Dual Momentum, Tactical Asset Allocation & Market Timing (12)

- **EN-085** O'Neal (2000). *Industry Momentum and Sector Mutual Funds*. Financial Analysts Journal. <https://doi.org/10.2469/faj.v56.n4.2372>
  O'Neal: sector-fund momentum rotation profitable pre-ETF; earliest sector-rotation fund evidence.
- **EN-086** Faber (2007). *A Quantitative Approach to Tactical Asset Allocation*. The Journal of Wealth Management. <https://doi.org/10.3905/jwm.2007.674809>
  Faber: 10-month SMA timing on five asset classes; the classic TAA baseline every rotation book is judged against.
- **EN-087** Faber (2010). *Relative Strength Strategies for Investing*. SSRN working paper. <https://doi.org/10.2139/ssrn.1585517>
  Faber: top-N relative strength rotation among sectors/assets; direct ancestor of our ETF rotation rules.
- **EN-088** Glabadanidis (2012). *Market Timing with Moving Averages*. SSRN working paper. <https://doi.org/10.2139/ssrn.2135337>
  Glabadanidis: MA timing looks great but is plagued by look-ahead/microstructure issues; required skepticism.
- **EN-089** Antonacci (2012). *Risk Premia Harvesting Through Dual Momentum*. SSRN working paper. <https://doi.org/10.2139/ssrn.2042750>
  Antonacci: dual momentum = relative strength across modules + absolute momentum gate; the GEM design our GEM book copies.
- **EN-090** Antonacci (2013). *Absolute Momentum: A Simple Rule-Based Strategy and Universal Trend-Following Overlay*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.2244633>
  Antonacci: absolute momentum as a universal trend overlay - the 12m excess-return gate we use for risk-off.
- **EN-091** Antonacci (2014). *Dual Momentum Investing: An Innovative Strategy for Higher Returns with Lower Risk*. McGraw-Hill. <https://www.mheducation.com/highered/mhp/product/dual-momentum-investing-innovative-strategy-higher-returns-lower-risk.html>
  Antonacci's book-length treatment of dual momentum (GEM); accessible statement of the full strategy and its evidence.
- **EN-092** Keller, Butler & Kipnis (2015). *Momentum and Markowitz: A Golden Combination*. SSRN working paper. <https://doi.org/10.2139/ssrn.2606884>
  Keller-Butler EAA: momentum plus correlation-aware weights ('golden combination') for multi-asset rotation.
- **EN-093** Keller & Keuning (2016). *Protective Asset Allocation (PAA): A Simple Momentum-Based Alternative for Term Deposits*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.2759734>
  Keller-Keuning PAA: breadth-based capital-preservation switch to bonds; blueprint for breadth on/off gates.
- **EN-094** Keller & Keuning (2017). *Breadth Momentum and Vigilant Asset Allocation (VAA): Winning More by Losing Less*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.3002624>
  Keller-Keuning VAA: aggressive dual momentum with breadth momentum crash protection; fast risk-off variant.
- **EN-095** Zakamulin (2018). *Revisiting the Profitability of Market Timing with Moving Averages*. International Review of Finance. <https://doi.org/10.1111/irfi.12132>
  Zakamulin: revisits MA timing profitability with proper statistics; tempered conclusions on timing value.
- **EN-096** Xiong (2026). *Continuous Timing Signals for Growth-Defensive Style Allocation*. arXiv preprint. <https://arxiv.org/abs/2605.20636>
  2026 arXiv: continuous timing signals for growth-vs-defensive style rotation; recent style-timing design.

## ETF Rotation & ETF Market Structure (13)

- **EN-097** Andreu, Swinkels & Tjong-A-Tjoe (2013). *Can exchange traded funds be used to exploit industry and country momentum?*. Financial Markets and Portfolio Management. <https://doi.org/10.1007/s11408-013-0207-8>
  Andreu-Swinkels-Tjong-A-Tjoe: country and industry momentum are tradable with ETFs; feasibility check for ETF rotation.
- **EN-098** Madhavan & Sobczyk (2014). *Price Dynamics and Liquidity of Exchange-Traded Funds*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.2429509>
  Madhavan-Sobczyk: ETF price dynamics and staleness vs NAV; measurement issues when backtesting ETF closes.
- **EN-099** Tse (2015). *Momentum strategies with stock index exchange-traded funds*. The North American Journal of Economics and Finance. <https://doi.org/10.1016/j.najef.2015.04.003>
  Tse: momentum strategies implemented with index ETFs; costs and turnover of practical ETF momentum.
- **EN-100** Bhattacharya & O'Hara (2017). *Can ETFs Increase Market Fragility? Effect of Information Linkages in ETF Markets*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.2740699>
  Bhattacharya-O'Hara: information linkages can make ETFs propagate shocks across markets (fragility).
- **EN-101** Israeli, Lee & Sridharan (2017). *Is there a dark side to exchange traded funds? An information perspective*. Review of Accounting Studies. <https://doi.org/10.1007/s11142-017-9400-8>
  Israeli-Lee-Sridharan: ETF ownership can degrade underlying price informativeness; cost of the ETF wrapper.
- **EN-102** Ben-David, Franzoni & Moussawi (2018). *Do ETFs Increase Volatility?*. The Journal of Finance. <https://doi.org/10.1111/jofi.12727>
  Ben-David-Franzoni-Moussawi: ETF arbitrage propagates liquidity shocks and raises constituent volatility; ETF microstructure risk.
- **EN-103** Da & Shive (2018). *Exchange traded funds and asset return correlations*. European Financial Management. <https://doi.org/10.1111/eufm.12137>
  Da-Shive: ETF trading raises return comovement of constituents; relevant to correlation filters in rotation books.
- **EN-104** Alexiou & Tyagi (2020). *Gauging the effectiveness of sector rotation strategies: evidence from the USA and Europe*. Journal of Asset Management. <https://doi.org/10.1057/s41260-020-00161-6>
  Alexiou-Tyagi: US/Europe sector-rotation strategies evaluated; evidence on what rotation logic survives costs.
- **EN-105** Glosten, Nallareddy & Zou (2021). *ETF Activity and Informational Efficiency of Underlying Securities*. Management Science. <https://doi.org/10.1287/mnsc.2019.3427>
  Glosten-Nallareddy-Zou: ETF activity improves short-horizon informational efficiency for small stocks.
- **EN-106** Brown, Davies & Ringgenberg (2021). *ETF Arbitrage, Non-Fundamental Demand, and Return Predictability*. Review of Finance. <https://doi.org/10.1093/rof/rfaa027>
  Brown-Davies-Ringgenberg: ETF flows are non-fundamental demand whose reversal is predictable; flow-based signal and warning.
- **EN-107** Box et al. (2021). *Intraday arbitrage between ETFs and their underlying portfolios*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.04.023>
  Box et al: intraday ETF-NAV arbitrage mechanics; how premiums/discounts close - relevant to fill quality.
- **EN-108** Easley et al. (2021). *The Active World of Passive Investing*. Review of Finance. <https://doi.org/10.1093/rof/rfab021>
  Easley et al: 'passive' ETFs host highly active trading strategies; taxonomy of ETF use including rotation.
- **EN-109** Karatas & Hirsa (2021). *Two-Stage Sector Rotation Methodology Using Machine Learning and Deep Learning Techniques*. arXiv preprint. <https://arxiv.org/abs/2108.02838>
  Karatas-Hirsa: two-stage ML sector-rotation methodology on sector ETFs; ML variant of the rotation problem.

## China / A-Share Anomalies & Momentum (32)

- **EN-110** Kang, Liu & Ni (2002). *Contrarian and momentum strategies in the China stock market: 1993–2000*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/s0927-538x(02)00046-x>
  Kang-Liu-Ni: first major contrarian/momentum study on A-shares (1993-2000); short-horizon reversal dominates.
- **EN-111** Wang & Chin (2004). *Profitability of return and volume-based investment strategies in China's stock market*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2003.12.002>
  Wang-Chin: volume-conditioned momentum/reversal in China; early evidence volume changes everything.
- **EN-112** Mei, Scheinkman & Xiong (2005). *Speculative Trading and Stock Prices: Evidence from Chinese A-B Share Premia*. NBER working paper. <https://doi.org/10.3386/w11362>
  Mei-Scheinkman-Xiong: A-B share premia driven by speculative trading intensity; turnover as speculation proxy.
- **EN-113** Naughton, Truong & Veeraraghavan (2008). *Momentum strategies and stock returns: Chinese evidence*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2007.10.001>
  Naughton et al: price momentum present in Shanghai stocks; one of the pro-momentum China datapoints.
- **EN-114** Chen et al. (2010). *On the predictability of Chinese stock returns*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2010.04.003>
  Chen et al: predictability of Chinese returns from fundamentals; early comprehensive A-share cross-section.
- **EN-115** Wu (2011). *Momentum trading, mean reversal and overreaction in Chinese stock market*. Review of Quantitative Finance and Accounting. <https://doi.org/10.1007/s11156-010-0206-z>
  Wu: A-share momentum/reversal and overreaction decomposition; reversal-heavy conclusion.
- **EN-116** Xiong & Yu (2011). *The Chinese Warrants Bubble*. American Economic Review. <https://doi.org/10.1257/aer.101.6.2723>
  Xiong-Yu: Chinese warrants bubble - textbook retail speculation; why crash overlays matter in A-share products.
- **EN-117** Cheema & Nartea (2014). *Momentum returns and information uncertainty: Evidence from China*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2014.10.002>
  Cheema-Nartea: momentum exists in China conditional on information uncertainty; where A-share momentum hides.
- **EN-118** Lee, Li & Zhang (2015). *Shell Games: The Long-Term Performance of Chinese Reverse-Merger Firms*. The Accounting Review. <https://doi.org/10.2308/accr-50960>
  Lee-Li-Zhang: Chinese reverse-merger (shell) firm performance; the shell-value channel behind CH-3's size fix.
- **EN-119** Hilliard & Zhang (2015). *Size and price-to-book effects: Evidence from the Chinese stock markets*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2015.02.003>
  Hilliard-Zhang: size and price-to-book in A-shares; fundamental cross-section before CH-3.
- **EN-120** Pan, Tang & Xu (2016). *Speculative Trading and Stock Returns*. Review of Finance. <https://doi.org/10.1093/rof/rfv059>
  Pan-Tang-Xu: speculative trading explains many China return patterns; turnover-based mispricing channel.
- **EN-121** Cakici, Chan & Topyan (2017). *Cross-sectional stock return predictability in China*. The European Journal of Finance. <https://doi.org/10.1080/1351847x.2014.997369>
  Cakici-Chan-Topyan: cross-sectional predictability in China A-shares; momentum weak, reversal and liquidity strong.
- **EN-122** Nartea, Kong & Wu (2017). *Do extreme returns matter in emerging markets? Evidence from the Chinese stock market*. Journal of Banking & Finance. <https://doi.org/10.1016/j.jbankfin.2016.12.008>
  Nartea et al: MAX/extreme-return preference priced in China; lottery demand shapes A-share tails.
- **EN-123** Cheema & Nartea (2017). *Momentum, idiosyncratic volatility and market dynamics: Evidence from China*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2017.09.001>
  Cheema-Nartea: momentum vs idiosyncratic volatility and market states in China; regime dependence of A-share momentum.
- **EN-124** Shi & Zhou (2017). *Time series momentum and contrarian effects in the Chinese stock market*. Physica A: Statistical Mechanics and its Applications. <https://doi.org/10.1016/j.physa.2017.04.139>
  Shi-Zhou: time-series momentum at short horizons flips to contrarian at long horizons in China; TSMOM-specific A-share evidence.
- **EN-125** Hsu et al. (2018). *Anomalies in Chinese A-Shares*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2018.44.7.108>
  Hsu et al: which US anomalies replicate in A-shares - momentum fails, reversal/turnover work; anomaly map for China.
- **EN-126** Chu, Gu & Zhou (2019). *Intraday momentum and reversal in Chinese stock market*. Finance Research Letters. <https://doi.org/10.1016/j.frl.2019.04.002>
  Chu-Gu-Zhou: intraday momentum in China's first/last half-hours; microstructure-level A-share momentum.
- **EN-127** Liu, Stambaugh & Yuan (2019). *Size and value in China*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2019.03.008>
  Liu-Stambaugh-Yuan: CH-3 factors for China - shell-value distortion means size/value must be redefined; our factor baseline.
- **EN-128** Lin et al. (2020). *Which is the better fourth factor in China? Reversal or turnover?*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2020.101347>
  Lin-Huang et al: reversal beats turnover as China's fourth factor; ranking of A-share factor candidates.
- **EN-129** Jansen, Swinkels & Zhou (2021). *Anomalies in the China A-share market*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2021.101607>
  Jansen et al: comprehensive A-share anomaly replication with local adjustments; updated China factor zoo.
- **EN-130** Carpenter, Lu & Whitelaw (2021). *The real value of China's stock market*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2020.08.012>
  Carpenter-Lu-Whitelaw: A-share price informativeness has risen to US levels; China market efficiency context.
- **EN-131** Li, Liang & L.D. Huynh (2022). *A new momentum measurement in the Chinese stock market*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2022.101759>
  Li et al: new momentum measurement tailored to China's short-cycle market; alternative signal definition.
- **EN-132** Titman, Wei & Zhao (2022). *Corporate actions and the manipulation of retail investors in China: An analysis of stock splits*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.09.018>
  Titman-Wei-Zhao: stock-split manipulation around SEOs in China; corporate actions can fake momentum signals.
- **EN-133** Leippold, Wang & Zhou (2022). *Machine learning in the Chinese stock market*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.08.017>
  Leippold-Wang-Zhou: ML return prediction in China - retail dominance makes liquidity/vol signals strongest; direct A-share evidence.
- **EN-134** Chui, Subrahmanyam & Titman (2022). *Momentum, Reversals, and Investor Clientele*. Review of Finance. <https://doi.org/10.1093/rof/rfac010>
  Chui-Subrahmanyam-Titman: momentum/reversal depend on investor clientele - key to China's reversal dominance.
- **EN-135** Liu, Wu & Zhu (2022). *Price overreaction to up-limit events and revised momentum strategies in the Chinese stock market*. Economic Modelling. <https://doi.org/10.1016/j.econmod.2022.105910>
  Liu-Wu-Zhu: up-limit (limit-up) events cause overreaction; revised momentum strategies that avoid limit distortion - T+1 relevant.
- **EN-136** Huang et al. (2023). *Momentum effect and contrarian effect in China's A-share market, under registration-based system*. Pacific-Basin Finance Journal. <https://doi.org/10.1016/j.pacfin.2023.102126>
  Huang et al 2023: momentum vs contrarian effects under the registration-based IPO reform; the post-2019 regime we trade in.
- **EN-137** Liu et al. (2024). *Analyst Reports and Stock Performance: Evidence from the Chinese Market*. arXiv preprint. <https://arxiv.org/abs/2411.08726>
  2024 arXiv: analyst-report tone predicts A-share performance; text-based alternative signal for China.
- **EN-138** Allen et al. (2024). *Dissecting the Long-Term Performance of the Chinese Stock Market*. The Journal of Finance. <https://doi.org/10.1111/jofi.13312>
  Allen et al 2024 JF: dissects why Chinese listed-market long-run returns lagged GDP growth; the A-share base-rate context.
- **EN-139** Zhu & Zhu (2024). *Enhancement of Price Trend Trading Strategies via Image-Induced Importance Weights*. arXiv preprint. <https://arxiv.org/abs/2408.08483>
  2024 arXiv: image-induced importance weights improve price-trend strategies in Chinese data.
- **EN-140** Ma, Liao & Jiang (2024). *Factor momentum in the Chinese stock market*. Journal of Empirical Finance. <https://doi.org/10.1016/j.jempfin.2023.101458>
  Ma-Liao-Jiang 2024: factor momentum exists in China and subsumes stock momentum; factor-rotation evidence for A-shares.
- **EN-141** Xu (2025). *Replication of Reference-Dependent Preferences and the Risk-Return Trade-Off in China*. arXiv preprint. <https://arxiv.org/abs/2505.20608>
  2025 arXiv: replication of reference-dependent preference (CGO) effects and risk-return trade-off in China.

## Anomalies: Methodology, Replication & Machine Learning (13)

- **EN-142** Ang et al. (2006). *The Cross-Section of Volatility and Expected Returns*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2006.00836.x>
  Ang et al: IVOL puzzle - high idiosyncratic vol predicts low returns; interacts with momentum screens.
- **EN-143** Stambaugh, Yu & Yuan (2012). *The short of it: Investor sentiment and anomalies*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2011.12.001>
  Stambaugh-Yu-Yuan: anomalies strongest after high sentiment via overpriced short legs; sentiment conditioning framework.
- **EN-144** Stambaugh, YU & Yuan (2015). *Arbitrage Asymmetry and the Idiosyncratic Volatility Puzzle*. The Journal of Finance. <https://doi.org/10.1111/jofi.12286>
  Stambaugh-Yu-Yuan: arbitrage asymmetry explains the IVOL puzzle; mispricing-side interpretation of anomalies.
- **EN-145** McLean & Pontiff (2016). *Does Academic Research Destroy Stock Return Predictability?*. The Journal of Finance. <https://doi.org/10.1111/jofi.12365>
  McLean-Pontiff: anomaly returns decay ~50% post-publication; expected live-vs-backtest haircut.
- **EN-146** Harvey, Liu & Zhu (2016). *… and the Cross-Section of Expected Returns*. Review of Financial Studies. <https://doi.org/10.1093/rfs/hhv059>
  Harvey-Liu-Zhu: multiple-testing haircut for factor discoveries (t>3); the standard our backtests should be judged by.
- **EN-147** Gao et al. (2018). *Market intraday momentum*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2018.05.009>
  Gao et al: first-half-hour return predicts last-half-hour; intraday momentum benchmark (relevant to close-fill timing).
- **EN-148** Hanauer & Lauterbach (2019). *The cross-section of emerging market stock returns*. Emerging Markets Review. <https://doi.org/10.1016/j.ememar.2018.11.009>
  Hanauer-Lauterbach: EM factor premia comparison; momentum robust in EM ex-China.
- **EN-149** Gu, Kelly & Xiu (2020). *Empirical Asset Pricing via Machine Learning*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhaa009>
  Gu-Kelly-Xiu: ML for asset pricing; momentum-family signals dominate importance rankings - method template.
- **EN-150** Hou, Xue & Zhang (2020). *Replicating Anomalies*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhy131>
  Hou-Xue-Zhang: most anomalies fail replication with microcap controls; momentum survives - bar for our claims.
- **EN-151** Han et al. (2022). *Expected return, volume, and mispricing*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.05.014>
  Han et al: volume amplifies mispricing correction vs continuation; volume-conditioned momentum theory.
- **EN-152** Jensen, Kelly & Pedersen (2023). *Is There a Replication Crisis in Finance?*. The Journal of Finance. <https://doi.org/10.1111/jofi.13249>
  Jensen-Kelly-Pedersen: Bayesian replication says most factors are real but shrunk; balanced replication verdict.
- **EN-153** Avramov, Cheng & Metzker (2023). *Machine Learning vs. Economic Restrictions: Evidence from Stock Return Predictability*. Management Science. <https://doi.org/10.1287/mnsc.2022.4449>
  Avramov-Cheng-Metzker: ML alphas shrink under economic restrictions (costs, shorting); realistic ML expectations.
- **EN-154** Hanauer & Kalsbach (2023). *Machine learning and the cross-section of emerging market stock returns*. Emerging Markets Review. <https://doi.org/10.1016/j.ememar.2023.101022>
  Hanauer et al: ML cross-section in emerging markets; momentum/reversal features matter most.

## Crowding, Capacity & Strategy Decay (13)

- **EN-155** Cahan & Luo (2013). *Standing Out From the Crowd: Measuring Crowding in Quantitative Strategies*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2013.39.4.014>
  Cahan-Luo: practitioner crowding dashboard for quant signals; early warning indicators.
- **EN-156** Hanson & Sunderam (2014). *The Growth and Limits of Arbitrage: Evidence from Short Interest*. Review of Financial Studies. <https://doi.org/10.1093/rfs/hht066>
  Hanson-Sunderam: short interest reveals arbitrage capital allocation; capacity of anomaly strategies.
- **EN-157** Akbas et al. (2015). *Smart money, dumb money, and capital market anomalies*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2015.07.003>
  Akbas et al: dumb money flows amplify anomalies, smart money attenuates; flow-based crowding channel.
- **EN-158** Landier, Simon & Thesmar (2015). *The Capacity of Trading Strategies*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.2585399>
  Landier-Simon-Thesmar: strategy capacity estimation under price impact; how big before alpha dies.
- **EN-159** Kinlaw, Kritzman & Turkington (2019). *Crowded Trades: Implications for Sector Rotation and Factor Timing*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2019.45.5.046>
  Kinlaw-Kritzman-Turkington: centrality-based crowding measure for sector rotation and factor timing.
- **EN-160** Volpati et al. (2020). *Zooming In on Equity Factor Crowding*. SSRN working paper. <https://doi.org/10.2139/ssrn.3518404>
  CFM: order-flow imprints of factor crowding - momentum rebalancing is 1-2% of flow and rising; direct crowding measurement.
- **EN-161** Lou & Polk (2022). *Comomentum: Inferring Arbitrage Activity from Return Correlations*. The Review of Financial Studies. <https://doi.org/10.1093/rfs/hhab117>
  Lou-Polk comomentum: high momentum-crowd correlation predicts crashes and reversal; the crowding metric for momentum books.
- **EN-162** Falck, Rej & Thesmar (2022). *When do systematic strategies decay?*. Quantitative Finance. <https://doi.org/10.1080/14697688.2022.2098810>
  Falck-Rej-Thesmar: systematic strategy Sharpe decays after discovery/publication; decay curve estimates.
- **EN-163** Lazo, Moneta & Chincarini (2023). *Crowded Spaces and Anomalies*. SSRN working paper. <https://doi.org/10.2139/ssrn.4618248>
  2023-24 SSRN: anomaly returns concentrate in crowded stocks and raise crash risk; crowding as limit-to-arbitrage.
- **EN-164** Hua & Sun (2024). *Dynamics of Factor Crowding*. SSRN working paper. <https://doi.org/10.2139/ssrn.5023380>
  Hua-Sun 2024 SSRN: cross-sectional and temporal dynamics of factor crowding; barriers-to-entry taxonomy.
- **EN-165** DeMiguel, Martín-Utrera & Uppal (2025). *Can Competition Increase Profits in Factor Investing?*. Management Science. <https://doi.org/10.1287/mnsc.2022.02684>
  DeMiguel-Martin-Utrera-Uppal: competition for factor profits and liquidity provision; equilibrium crowding effects.
- **EN-166** Lee (2025). *Not All Factors Crowd Equally: Modeling, Measuring, and Trading on Alpha Decay*. arXiv preprint. <https://arxiv.org/abs/2512.11913>
  2025 arXiv: hyperbolic alpha-decay law for crowded mechanical factors (momentum); crowding predicts crashes, not means.
- **EN-167** Kurth et al. (2026). *Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend*. arXiv preprint. <https://arxiv.org/abs/2607.01550>
  2026 arXiv (CFM): microstructural account of short-term trend's demise - crowding killed the fast signal.

## Volatility Targeting, Risk Parity & Style Premia (7)

- **EN-168** Blitz & van Vliet (2007). *The Volatility Effect*. The Journal of Portfolio Management. <https://doi.org/10.3905/jpm.2007.698039>
  Blitz-van Vliet: the volatility effect - low-vol stocks match returns with less risk; defensive sleeve rationale.
- **EN-169** Asness, Frazzini & Pedersen (2012). *Leverage Aversion and Risk Parity*. Financial Analysts Journal. <https://doi.org/10.2469/faj.v68.n1.1>
  Asness-Frazzini-Pedersen: risk parity as leverage-aversion payoff; balanced-risk allocation logic.
- **EN-170** Frazzini & Pedersen (2014). *Betting against beta*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2013.10.005>
  Frazzini-Pedersen: leverage-constrained investors overpay for beta; why low-beta/defensive sleeves earn premia.
- **EN-171** Asness et al. (2015). *Investing with Style*. Journal of Investment Management. <https://joim.com/article/investing-with-style/>
  Asness-Ilmanen-Israel-Moskowitz: value/momentum/carry/defensive as implementable style premia; portfolio-construction guide.
- **EN-172** Koijen et al. (2018). *Carry*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2017.11.002>
  Koijen et al: carry generalized to all asset classes, complements momentum; cross-signal diversification.
- **EN-173** Ilmanen et al. (2019). *Factor Premia and Factor Timing: A Century of Evidence*. SSRN Electronic Journal. <https://doi.org/10.2139/ssrn.3400998>
  Ilmanen et al: century of factor premia across markets and the (limited) scope for factor timing.
- **EN-174** Baltussen, Swinkels & Van Vliet (2021). *Global factor premiums*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2021.06.030>
  Baltussen-Swinkels-van Vliet: global multi-asset factor premia over 200 years incl. trend and momentum; deep-sample priors.

## Transaction Costs & Implementability (6)

- **EN-175** Korajczyk & Sadka (2004). *Are Momentum Profits Robust to Trading Costs?*. The Journal of Finance. <https://doi.org/10.1111/j.1540-6261.2004.00656.x>
  Korajczyk-Sadka: momentum survives costs up to multi-billion capacity depending on trade style; capacity math.
- **EN-176** Lesmond, Schill & Zhou (2004). *The illusory nature of momentum profits*. Journal of Financial Economics. <https://doi.org/10.1016/s0304-405x(03)00206-x>
  Lesmond-Schill-Zhou: momentum profits concentrated in high-cost stocks; the pessimistic cost case.
- **EN-177** Novy-Marx & Velikov (2016). *A Taxonomy of Anomalies and Their Trading Costs*. Review of Financial Studies. <https://doi.org/10.1093/rfs/hhv063>
  Novy-Marx-Velikov: anomaly-by-anomaly cost taxonomy and mitigation rules; momentum turnover management.
- **EN-178** Frazzini, Israel & Moskowitz (2018). *Trading Costs*. SSRN working paper. <https://doi.org/10.2139/ssrn.3229719>
  Frazzini-Israel-Moskowitz: live AQR trading data - real costs far below academic estimates; optimistic counterpoint.
- **EN-179** Patton & Weller (2020). *What you see is not what you get: The costs of trading market anomalies*. Journal of Financial Economics. <https://doi.org/10.1016/j.jfineco.2020.02.012>
  Patton-Weller: implementation shortfall of anomalies in live funds; what you see is not what you get.
- **EN-180** Chen & Velikov (2023). *Zeroing In on the Expected Returns of Anomalies*. Journal of Financial and Quantitative Analysis. <https://doi.org/10.1017/s0022109022000874>
  Chen-Velikov: expected returns of anomalies net of costs shrink toward zero post-publication; final word on net alpha.

## Recent arXiv: Deep Learning & Modern Momentum (2019-2026) (10)

- **EN-181** Lim, Zohren & Roberts (2019). *Enhancing Time Series Momentum Strategies Using Deep Neural Networks*. arXiv preprint. <https://arxiv.org/abs/1904.04912>
  Lim-Zohren-Roberts: deep networks that learn TSMOM sizing end-to-end; the DMN baseline.
- **EN-182** Wood, Roberts & Zohren (2021). *Slow Momentum with Fast Reversion: A Trading Strategy Using Deep Learning and Changepoint Detection*. arXiv preprint. <https://arxiv.org/abs/2105.13727>
  Wood et al: changepoint detection module makes slow momentum robust to fast reversion; nonstationarity handling.
- **EN-183** Wood et al. (2021). *Trading with the Momentum Transformer: An Intelligent and Interpretable Architecture*. arXiv preprint. <https://arxiv.org/abs/2112.08534>
  Momentum Transformer: attention-based architecture beating LSTM DMNs with interpretable regimes.
- **EN-184** Ong & Herremans (2023). *Constructing Time-Series Momentum Portfolios with Deep Multi-Task Learning*. arXiv preprint. <https://arxiv.org/abs/2306.13661>
  Ong-Herremans: multi-task deep learning for TSMOM portfolio construction.
- **EN-185** Wood et al. (2023). *Few-Shot Learning Patterns in Financial Time-Series for Trend-Following Strategies*. arXiv preprint. <https://arxiv.org/abs/2310.10500>
  Few-shot pattern learning for trend strategies; adapting to regime scarcity.
- **EN-186** Ong & Herremans (2024). *DeepUnifiedMom: Unified Time-series Momentum Portfolio Construction via Multi-Task Learning*. arXiv preprint. <https://arxiv.org/abs/2406.08742>
  DeepUnifiedMom: unified multi-task momentum portfolios across horizons.
- **EN-187** Li & Ferreira (2025). *Follow the Leader: Enhancing Systematic Trend-Following Using Network Momentum*. arXiv preprint. <https://arxiv.org/abs/2501.07135>
  Network momentum: cross-asset lead-lag graphs enhance trend following.
- **EN-188** Lu et al. (2025). *TrendFolios: A Portfolio Construction Framework for Utilizing Momentum and Trend-Following*. arXiv preprint. <https://arxiv.org/abs/2506.09330>
  TrendFolios: portfolio construction framework combining momentum and trend signals.
- **EN-189** Chen (2026). *Be Water: An Evolutionary Proof for Trend-Following*. arXiv preprint. <https://arxiv.org/abs/2603.29593>
  2026: evolutionary/adaptive argument for why trend following persists; theory of survival.
- **EN-190** Bui & Nguyen (2026). *Systematic Trend-Following with Adaptive Portfolio Construction*. arXiv preprint. <https://arxiv.org/abs/2602.11708>
  2026: adaptive portfolio construction layered on systematic trend; construction-vs-signal decomposition.
