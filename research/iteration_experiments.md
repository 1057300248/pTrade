# Ranked next-iteration experiments

## Boundary and common IS protocol

These are bounded, literature-backed edits to the existing ADM/RMDC
incumbents. They change only **sizing**, **gold-diversifier overlay**,
**crowding overlay**, or **execution tranche** behavior. Signal definitions,
signal horizons, universes, crash rules, and eligibility gates stay frozen.

For every row, “common IS” means:

- add one candidate and compare it with its named incumbent on
  `2018-01-02`–`2021-12-31` only;
- use the same split-adjusted panel, costs, `T`-close signal and no-earlier-than
  `T+1` fills;
- choose by IS Sharpe, then CAGR, then least-negative MDD, with the incumbent
  winning an exact tie;
- freeze the IS choice before opening the existing 2022–2026 OOS and stress
  diagnostics; OOS cannot rescue a candidate rejected on IS;
- run rows independently, never as a Cartesian product.

`Estimated N add` is the number of predeclared candidate trials added to the
ledger, not an estimate of return or statistical significance.

| Rank | Name | Prior citation | Genome layer | IS protocol | Reject-if | Estimated N add |
| ---: | --- | --- | --- | --- | --- | ---: |
| 1 | RMDC full-covariance risk scaling | [EN-020, *Demystifying Time-Series Momentum Strategies*](https://doi.org/10.1002/9781119599364.ch3) and [EN-092, *Momentum and Markowitz*](https://doi.org/10.2139/ssrn.2606884) in `lit_en_momentum.md` | `sizing.portfolio_vol` | Common IS; keep RMDC picks and inverse-vol weights fixed, but scale them with the full covariance of the already-buffered return panel instead of a diagonal-only portfolio-vol estimate. One fixed estimator; no horizon candidates. | Not the IS winner; covariance is non-finite/ill-conditioned without a predeclared deterministic fallback; or turnover rises without an IS MDD improvement. | +1 |
| 2 | Two-timescale volatility floor | [EN-020](https://doi.org/10.1002/9781119599364.ch3) and the adverse real-time evidence in [EN-066, *On the performance of volatility-managed portfolios*](https://doi.org/10.1016/j.jfineco.2020.04.015), both in `lit_en_momentum.md` | `sizing.asset_vol` | Common IS; for sizing only, replace each incumbent 20-session volatility input with `max(vol20, vol60)`, reusing the existing 20/60-session buffers. Keep the target, cap, signals and assets unchanged; do not vary either horizon. | Not the IS winner; improvement exists gross but not after the frozen cost model; or de-risking lowers CAGR without improving Sharpe or MDD. | +1 |
| 3 | Monotone crowding size ladder | [S002, *Crowded Trades and Tail Risk*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3326802), [S013, *MSCI Security Crowding Model*](https://www.msci.com/research-and-insights/paper/msci-security-crowding-model), and the overlay interpretation in `lit_crowding_crossasset.md` | `crowding_overlay.target_cap` | Common IS; reuse the incumbent 0–4 score: `0–1` leaves target size unchanged, `2` forbids an increase above current weight, and `3+` applies one predeclared risk-weight cap while leaving independent hard exits untouched. Test the mapping as one candidate, not threshold variants. | Not the IS winner; the overlay increases turnover; IS MDD does not improve; or the implementation turns crowding into a directional alpha/forced-exit signal. | +1 |
| 4 | Crowding-gated two-session entry | [EN-067, *Strategic Rebalancing*](https://doi.org/10.3905/jpm.2020.1.150) in `lit_en_momentum.md`; [S005, *Asset Fire Sales*](https://www.nber.org/papers/w11357) and the staged-entry prescription in `lit_crowding_crossasset.md` | `execution_tranche.entry` | Common IS; only when a new target has crowding score `2`, buy one half at the incumbent `T+1` fill and the remainder at `T+2` if eligibility/tradeability still pass. Sells and hard-risk exits retain incumbent timing. | Not the IS winner; net turnover or modeled costs increase; delayed entry worsens IS MDD; or the result depends on one rebalance date. | +1 |
| 5 | Positive-gate gold diversifier sidecar | [S062, *Is Gold a Hedge or a Safe Haven?*](https://ideas.repec.org/a/bla/finrev/v45y2010i2p217-229.html), [S063, international evidence](https://doi.org/10.1016/j.jbankfin.2009.12.008), and [S067, gold survey](https://doi.org/10.1016/j.irfa.2015.07.005) in `lit_crowding_crossasset.csv` | `gold_div_overlay.risk_budget` | Common IS on ADM; retain the incumbent risk winner, but allow one bounded, inverse-vol-funded gold sidecar only when gold passes its existing absolute gate. Fund it pro rata from risk exposure, never by leverage, and use one fixed cap. | Not the IS winner; IS MDD worsens; the sidecar is effectively an uncapped permanent gold allocation; or gains depend on one crisis interval or rebalance date. | +1 |
| 6 | Crash-lockdown gold substitution | [S062](https://ideas.repec.org/a/bla/finrev/v45y2010i2p217-229.html), [S063](https://doi.org/10.1016/j.jbankfin.2009.12.008), and the conclusion that gold protection is short-lived and regime-dependent in `lit_crowding_crossasset.md` | `gold_div_overlay.lockdown` | Common IS on ADM; during the already-defined crash lockdown only, replace one fixed, bounded portion of bond parking with gold when gold passes its existing absolute gate. Do not alter crash thresholds, lockdown length or normal-state allocation. | Not the IS winner; lockdown MDD and worst month both fail to improve; ordinary-state exposure changes; or the candidate relies on gold despite a failed incumbent gate. | +1 |

If all six rows are admitted to the ledger, the total declared addition is
`N=6`. Admission does not imply promotion: a failed candidate is recorded and
discarded, and combinations require a separate future declaration.
