# Wave 2 execution ledger

Status: **IMPLEMENTATION IN PROGRESS, grids not yet executed**.

This is the pre-run ledger. Wave 2 has no results yet.

Declarations:

- Genome: [`evoquant_genome_wave2.json`](evoquant_genome_wave2.json)
- Plan: [`evoquant_wave2_plan.md`](evoquant_wave2_plan.md)

## Declared candidates

| Candidate ID | Family | Field | Declared value | Status |
| --- | --- | --- | ---: | --- |
| `W2-CROWD-P90` | `W2-CROWD` | `crowding_percentile` | 0.90 | Not executed |
| `W2-CROWD-P95` | `W2-CROWD` | `crowding_percentile` | 0.95 | Not executed |
| `W2-TRANCHE-N2` | `W2-TRANCHE` | `n_tranches` | 2 | Not executed |
| `W2-TRANCHE-N3` | `W2-TRANCHE` | `n_tranches` | 3 | Not executed |
| `W2-TRANCHE-N4` | `W2-TRANCHE` | `n_tranches` | 4 | Not executed |
| `W2-BREADTH-C25` | `W2-BREADTH` | `breadth_cut` | 0.25 | Not executed |
| `W2-BREADTH-C50` | `W2-BREADTH` | `breadth_cut` | 0.50 | Not executed |
| `W2-BREADTH-C75` | `W2-BREADTH` | `breadth_cut` | 0.75 | Not executed |

There is no Cartesian product. Each family is tested one field at a time.

## Trial accounting

- Wave 1: **N=8**, already counted.
- Wave 2: **+N=8**, declared here.
- Cumulative: **N=16** if all eight Wave 2 candidates run.
- RMDC hysteresis alignment is a separate **N=0** track and is not part of
  these eight Wave 2 candidates.

## Frozen selection rule

Each family selects one setting on IS 2018-01-02 through 2021-12-31 using:

1. highest IS Sharpe;
2. highest IS CAGR;
3. least-negative IS maximum drawdown;
4. lower field value as the deterministic exact-tie break.

Only after all three family winners are frozen may their OOS 2022-01-04
through 2026-08-21 and stress-window metrics be revealed. OOS results cannot
re-pick a grid value or move a losing family into promotion.

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

## Data and execution contract

- Data: split-adjusted bars from `research.etf_panel`.
- Signal and fill: T close signal, T+1 close fill.
- Trading cost: 8bp one way.

## Run constraints and valid outcome

- No live file edits are permitted, including edits to any live strategy.
- There is no 2026-07 targeting: do not use that window to choose or tune any
  value. Its return threshold above is an OOS verification gate only.
- Do not combine the three fields or run a Cartesian product.
- Zero promotion is a valid successful outcome of Wave 2.
