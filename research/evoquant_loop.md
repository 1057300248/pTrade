# Local EvoQuant-style ADM verifier

`research/evoquant_loop.py` is a bounded research verifier, not a strategy
generator and not a live-file editor. It turns the frozen ADM specification
into typed layers, runs a small controlled candidate set, freezes one choice
on 2018–2021, and only then exposes 2022–2026 and stress-window results.

## Run

```bash
python3 research/evoquant_loop.py
```

The command loads split-adjusted parquet bars through
`research.etf_panel.load_panel`, imports numeric scoring and allocation
functions from `ptrade_adm_etf.py`, reuses the T-close/T+1-close mechanics
from `research.ablate_adm_knobs`, prints the result table, and regenerates
`research/evoquant_candidates.md`.

The local cache must contain the four risk assets and bond:

- `510300.SS`: CSI 300
- `159915.SZ`: ChiNext
- `513100.SS`: Nasdaq
- `518880.SS`: gold
- `511010.SS`: government bond

## Typed genome

`research/evoquant_genome_adm.json` is the source of candidate data. Frozen
layers preserve the live universe, 252/21 TSMOM with 126/5 fallback,
crowding threshold 4, 6%/8% crash overlay, three-session lockdown, weekly
T+1 execution, and 8bp one-way research cost.

Only three layers can vary:

1. volatility target: `0.12` or `0.16`;
2. 21-session month gate: on or off;
3. gold overlay: on or off, where off makes `518880.SS` ineligible as the
   weekly risk winner.

Their Cartesian product is exactly eight declared trials. There is no
lookback grid, no universe expansion, and no parameter selected from the
2024-02 or 2026-07 windows.

## Freeze and promotion protocol

All eight equity curves are generated on one fixed engine. Candidate
selection reads only 2018-01-02 through 2021-12-31 metrics:

1. highest IS Sharpe;
2. highest IS CAGR;
3. least-negative IS maximum drawdown;
4. deterministic incumbent-layer tie breaks.

The IS winner is frozen before OOS and stress metrics are calculated. OOS
alternatives never replace a failed IS winner.

Promotion requires every gate:

- OOS Sharpe is at least `0.5 × IS Sharpe`;
- 2024-02 return is greater than `-8%`;
- 2026-07 return is greater than `-10%`;
- OOS CAGR is greater than 510300 buy-and-hold.

An IS winner that misses any gate is explicitly rejected. All seven
non-winners are rejected as not selected by IS, even if their diagnostic OOS
numbers happen to look attractive.

## Controls and multiple testing

The verifier computes 510300 from the same split-adjusted panel and reads
RMDC diagnostics from `research/backtest_adm_report.md` rather than rerunning
the slower RMDC engine. It reports the declared trial count `N=8` and a
transparent Bonferroni-adjusted normal-Sharpe note. Because the eight trials
are strongly dependent, the note is not mislabeled as a formal iid Deflated
Sharpe Ratio.

## Write boundary

The only runtime output is `research/evoquant_candidates.md`. Before and
after the run, the script hashes `ptrade_adm_etf.py` and aborts if the live
file changes. Candidate edits remain prose proposals for human review; they
are never auto-applied.
