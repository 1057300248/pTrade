# Wave 2 execution ledger

Status: **EXECUTED 2026-08-22, research-only. Proposed live edit: None.**

Run log: `/opt/cursor/artifacts/evoquant_wave2_run.log`.
Report: [`evoquant_candidates_wave2.md`](evoquant_candidates_wave2.md).

Declarations:

- Genome: [`evoquant_genome_wave2.json`](evoquant_genome_wave2.json)
- Plan: [`evoquant_wave2_plan.md`](evoquant_wave2_plan.md)

## Declared candidates

| Candidate ID | Family | Field | Declared value | Status |
| --- | --- | --- | ---: | --- |
| `W2-CROWD-P90` | `W2-CROWD` | `crowding_percentile` | 0.90 | IS family winner; OOS PASSED research-only (matches incumbent) |
| `W2-CROWD-P95` | `W2-CROWD` | `crowding_percentile` | 0.95 | REJECTED not IS family winner (tie → lower field) |
| `W2-TRANCHE-N2` | `W2-TRANCHE` | `n_tranches` | 2 | IS family winner; OOS PASSED research-only |
| `W2-TRANCHE-N3` | `W2-TRANCHE` | `n_tranches` | 3 | REJECTED not IS family winner |
| `W2-TRANCHE-N4` | `W2-TRANCHE` | `n_tranches` | 4 | REJECTED not IS family winner |
| `W2-BREADTH-C25` | `W2-BREADTH` | `breadth_cut` | 0.25 | IS family winner; OOS PASSED research-only (matches incumbent) |
| `W2-BREADTH-C50` | `W2-BREADTH` | `breadth_cut` | 0.50 | REJECTED not IS family winner |
| `W2-BREADTH-C75` | `W2-BREADTH` | `breadth_cut` | 0.75 | REJECTED not IS family winner |

There is no Cartesian product. Each family is tested one field at a time.
OOS of rejected IS losers was not opened.

## Family winners vs incumbent ADM (`vol_target=0.16`)

Incumbent OOS (from Wave 1 / official table): CAGR 8.17%, Sharpe 0.67,
2024-02 +3.24%, 2026-07 −3.90%.

| Family winner | IS CAGR | IS Sharpe | IS MDD | OOS CAGR | OOS Sharpe | 2024-02 | 2026-07 | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `W2-CROWD-P90` | 12.03% | 0.85 | −21.51% | 8.17% | 0.67 | +3.24% | −3.90% | PASSED research-only; OOS identical to incumbent |
| `W2-TRANCHE-N2` | 11.69% | 0.85 | −16.95% | 9.41% | 0.76 | +3.21% | −4.43% | PASSED research-only; **not auto-applied** |
| `W2-BREADTH-C25` | 12.03% | 0.85 | −21.51% | 8.17% | 0.67 | +3.24% | −3.90% | PASSED research-only; OOS identical to incumbent |

`W2-BREADTH-C25` binds only when 0 of 4 RISK assets pass `month_gate`
(`breadth < 0.25`). That almost never happens, so it is effectively a no-op.

`W2-CROWD-P90` matching incumbent OOS means the percentile path did not
change live-relevant vetoes on this sample. Do not treat it as new alpha.

`W2-TRANCHE-N2` is the only material research difference. Promotion still
needs human review + SimTradeLab + 国金 minute sim + ≥4 weeks paper. Zero
live promotion is the default of this run.

## Trial accounting

- Wave 1: **N=8**, already counted.
- Wave 2: **+N=8**, all eight executed.
- Cumulative: **N=16**.
- RMDC hysteresis alignment is a separate **N=0** track.

Do not start the extra six rows in `docs/iteration_experiments.md` unless
explicitly requested. Those would be a new N increment.

## Frozen selection rule

Each family selected one setting on IS 2018-01-02 through 2021-12-31 using:

1. highest IS Sharpe;
2. highest IS CAGR;
3. least-negative IS maximum drawdown;
4. lower field value as the deterministic exact-tie break.

OOS results were not used to re-pick a grid value.

## Frozen OOS gates

Each of the three IS-frozen family winners was accepted or rejected
independently using:

- OOS Sharpe `>= 0.5 × IS Sharpe`;
- 2024-02 return `> -8%`;
- 2026-07 return `> -10%`;
- OOS CAGR greater than 510300 buy-and-hold.

All three winners passed those gates. That is not a live-edit instruction.

## Data and execution contract

- Data: split-adjusted bars from `research.etf_panel`.
- Signal and fill: T close signal, T+1 close fill.
- Trading cost: 8bp one way.

## Run constraints and outcome

- No live file was edited. `AUTO_APPLY_LIVE_EDITS = False`.
- 2026-07 was a verification gate only.
- No Cartesian product.
- **Proposed live edit: None.**
