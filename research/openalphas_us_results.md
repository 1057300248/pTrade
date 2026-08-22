# OpenAlphas risk parity + momentum: US reproduction

Research only; no live `ptrade_*.py` strategy is imported or changed.

## Data

- Pool: `SPY, QQQ, GLD, TLT, XLV, XLF, XLK, XLE, EWJ, FXI, HYG, LQD, SLV, USO, EEM`
- Source: Yahoo Finance via yfinance (Adj Close) [parquet cache]
- Field: adjusted close (the Stooq fallback uses its provider-adjusted historical Close)
- Aligned data: 2015-01-02 through 2026-08-21 (2926 sessions)
- Cache: `research/cache/openalphas_us/*.parquet`

## Results

| Window | Strategy CAGR | Strategy MDD | Strategy Sharpe | Benchmark CAGR | Benchmark MDD | Benchmark Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Published window (actual bars 2018-01-02 .. 2024-03-28) (through 2024-03-28) | -4.10% | 45.17% | -0.23 | 7.80% | 27.92% | 0.58 |
| Extended window (actual bars 2018-01-02 .. 2026-08-21) (through 2026-08-21) | -0.31% | 45.17% | 0.05 | 11.44% | 27.92% | 0.84 |

## Blog comparison

Blog claim: CAGR 52.3%, MDD 14.7%, Sharpe 2.6. This run does **not** replicate the claimed 52.3% CAGR (difference -56.40 percentage points). Parameters were not retuned.

Mechanics: Friday dates missing from the price index are skipped; signals and fills use the same Friday close; transaction cost is 0.1% per side.
