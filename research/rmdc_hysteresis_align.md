# RMDC live hysteresis alignment

## Change

The research engine now mirrors live `ptrade_rmdc_etf._compute_targets`
name-stickiness:

1. Build raw target weights.
2. Sort and retain proposed names with weight at least the live minimum of 4%.
3. Retain currently held names that still exist in the raw weights.
4. Apply the live `apply_hysteresis` formula with a 1.20 score gap.
5. Use the raw weights for the resulting stable names.

The weekly loop passes the current holding names into `weekly_target`. This is
anti-overfit rule 15 alignment with `N_add=0`; no TQ, crowding, crash, lockdown,
or sleeve parameters were retuned.

## Before and after

The before result is from `/opt/cursor/artifacts/rmdc_research_backtest.txt`.
The after result is from:

```text
python3 research/backtest_rmdc_etf.py
```

| Metric | Before | After | Change |
|---|---:|---:|---:|
| CAGR | 5.44% | 6.38% | +0.94 pp |
| Maximum drawdown | -15.93% | -14.01% | +1.92 pp (less severe) |
| Sharpe | 0.58 | 0.68 | +0.10 |
| Fills | 459 | 459 | 0 |
| 2024-02 return / drawdown | +2.53% / -0.40% | +2.53% / -0.40% | unchanged |
| 2026-07 return / drawdown | -0.71% / -1.44% | -0.71% / -1.44% | unchanged |

The after CAGR change means the research backtest is closer to live behavior;
it is not evidence of new alpha or parameter improvement.

The aligned 2024-02 drawdown equals the combo-E reference of -0.40%. The
aligned 2026-07 drawdown of -1.44% is less severe than the combo-E reference of
-1.65%. These windows therefore do not show a materially worse drawdown from
live hysteresis.

## Verification

```text
python3 -m pytest tests/test_backtest_rmdc_hysteresis.py tests/test_ptrade_rmdc_etf.py -q
................                                                         [100%]
16 passed in 0.46s
```
