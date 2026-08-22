# EvoQuant Wave 2 predeclared plan

Status: **PREDECLARED — NOT RUN**.

This document freezes Wave 2 before any candidate backtest. It proposes three
research candidates only. No `ptrade_*.py` file is changed, and no result in
2022–2026 or either stress window may alter these grids.

The machine-readable declaration is
`research/evoquant_genome_wave2.json`.

## Trial accounting fixed in advance

Wave 2 is three one-field-at-a-time candidate families, not a Cartesian
product:

| Candidate | Proposed field | Exact IS grid | IS grid size |
| --- | --- | --- | ---: |
| `W2-CROWD` | `crowding_percentile` | `{0.90, 0.95}` | 2 |
| `W2-TRANCHE` | `n_tranches` | `{2, 3, 4}` | 3 |
| `W2-BREADTH` | `breadth_cut` | `{0.25, 0.50, 0.75}` | 3 |
| **Wave 2 total** | one field at a time | no cross-products | **N=8** |

Wave 1 already declared and ran `N=8`. If all Wave-2 grids are run, the
cumulative EvoQuant trial count is therefore **N=16**, regardless of which
results are eventually reported.

Each family selects one setting on IS 2018-01-02 through 2021-12-31 using:

1. highest IS Sharpe;
2. highest IS CAGR;
3. least-negative IS maximum drawdown;
4. lower field value as the deterministic exact-tie break.

Only after all three family winners are frozen may their OOS 2022-01-04
through 2026-08-21 and stress-window metrics be revealed. OOS results cannot
re-pick a grid value or move a losing family into promotion.

## Candidate 1: causal crowding percentile

`W2-CROWD` tests whether the fixed RMDC-style crowding component thresholds
should be replaced by causal, self-calibrating adverse-tail percentiles.

Frozen implementation for both grid points:

- Preserve the existing four crowding components: volume heat, price
  extension, price-volume correlation, and amplitude.
- For each risk asset and component, use only observations strictly before
  the signal date, with a trailing maximum of 1,250 sessions.
- Require 252 prior component observations. Before warm-up, use the
  incumbent fixed-threshold `crowding_points` result.
- Volume heat, price extension, and amplitude trigger in the upper tail.
  Price-volume correlation triggers in the lower tail at `1 - percentile`.
- Preserve ADM's existing aggregate veto: all four points (`>=4`) block the
  risk asset. The aggregate threshold is not another grid dimension.
- Grid only `crowding_percentile ∈ {0.90, 0.95}`. The 0.95 point is the
  literature value; 0.90 is the sole predeclared robustness neighbor.

Grid size is exactly **2**.

## Candidate 2: staggered weekly execution

`W2-TRANCHE` tests whether fixed-day execution noise can be reduced without
changing ADM's signal.

Frozen implementation for every tranche count:

- Compute the weekly ADM target once at the incumbent signal close.
- Freeze that target; do not refresh momentum, month gate, crowding, or
  volatility between tranches.
- Split the original position-to-target gap into equal
  `1 / n_tranches` pieces and execute them on consecutive closes.
- Apply the existing 8bp one-way cost to every tranche's actual turnover.
- Crash liquidation remains immediate and bypasses unfinished tranches.
- A new weekly signal cancels any stale unfinished schedule before creating
  the next one.
- Grid only `n_tranches ∈ {2, 3, 4}`, matching the predeclared literature
  range.

Grid size is exactly **3**.

## Candidate 3: cross-asset breadth cut

`W2-BREADTH` tests a Keller-style capital-preservation gate using only ADM's
existing one-month absolute-momentum signal.

Frozen implementation for every cut:

- At the weekly signal close, evaluate the existing `month_gate` for each of
  the four `RISK` assets.
- Breadth is the passing count divided by the fixed denominator four.
- If `breadth < breadth_cut`, force the incumbent defensive target
  `{511010.SS: 0.95}`.
- Otherwise run incumbent ADM selection and volatility scaling unchanged.
- The crash overlay and three-session lockdown remain unchanged and take
  priority.
- Grid only `breadth_cut ∈ {0.25, 0.50, 0.75}`. With four assets these are
  exact one-, two-, and three-passing-asset boundaries.

Grid size is exactly **3**.

## Frozen OOS gates

Each of the three IS-frozen family winners is accepted or rejected
independently using the existing gates:

- OOS Sharpe `>= 0.5 × IS Sharpe`;
- 2024-02 return `> -8%`;
- 2026-07 return `> -10%`;
- OOS CAGR greater than 510300 buy-and-hold.

Stress windows are verification only, never targets. If a family winner
fails, the family is rejected; no OOS rescue value may be chosen from its
grid.

## Explicit exclusions

- Do not combine the three proposed fields in Wave 2.
- Do not grid momentum lookback, skip, month gate, volatility target,
  crowding block count, crash thresholds, lockdown days, universe, or costs.
- Do not use 2026-07 to choose any value.
- Do not auto-edit `ptrade_adm_etf.py` or any other live strategy.
- Do not run the grids merely by merging this declaration; execution is a
  separate, explicitly requested research step.
