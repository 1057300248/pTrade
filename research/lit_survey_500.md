# Literature survey: 568 unique sources

Generated on 2026-08-22 from all four requested inputs.  The deduplicated,
row-level bibliography is [`lit_survey_500.csv`](lit_survey_500.csv).

## Source counts

The inputs contain 613 rows.  Global URL-then-title deduplication leaves
**568 unique sources**, so the 500-source quantity target is exceeded by 68.
No rows were invented.  This count measures bibliography coverage, not
strategy validity or evidence quality.

| Input | Input rows | Retained after global dedup |
| --- | ---: | ---: |
| `lit_cn_sources.csv` | 134 | 134 |
| `lit_en_momentum.csv` | 190 | 183 |
| `lit_en_alphamine.csv` | 147 | 135 |
| `lit_crowding_crossasset.csv` | 142 | 116 |
| **Total** | **613** | **568** |

Deduplication respects the input order shown above.  URL normalization applies
Unicode NFKC, trimming and case folding; removes fragments and tracking
parameters; normalizes HTTP(S), `www`, DOI hosts, repeated/trailing slashes,
and query order; then keeps the first nonblank URL.  Survivors are deduplicated
again by NFKC/case-folded, whitespace-normalized title.  Blank keys are not
collapsed.  The CSV retains both original and normalized URLs for audit.

## Counts by input type

Input type distributions before cross-file deduplication:

- `lit_cn_sources.csv`: broker 57, media 19, blog 15, journal 14, other 14,
  forum 6, arXiv 5, SSRN 4.
- `lit_en_momentum.csv`: journal 144, arXiv 21, working-SSRN 20,
  working-NBER 3, book chapter 1, book 1.
- `lit_en_alphamine.csv`: paper 91, code 32, survey 16, benchmark 3,
  platform 2, book 1, tool 1, dataset 1.
- `lit_crowding_crossasset.csv`: 142 rows; this input has no `type` column
  (its separate `theme` field is preserved).

Type counts among the 568 retained rows:

| Type | Count | Type | Count |
| --- | ---: | --- | ---: |
| journal | 151 | not provided | 116 |
| paper | 82 | broker | 57 |
| code | 29 | arXiv | 26 |
| working-SSRN | 20 | media | 19 |
| survey | 16 | blog | 15 |
| other | 14 | forum | 6 |
| SSRN | 4 | working-NBER | 3 |
| benchmark | 3 | book | 2 |
| platform | 2 | book chapter | 1 |
| tool | 1 | dataset | 1 |

## What we will actually test next

1. Keep **ADM and RMDC as frozen incumbents**; a bibliography entry alone
   cannot promote or replace a live strategy.
2. Convert only literature-backed hypotheses with a clear causal and
   execution rationale into typed ADM/RMDC candidate edits.
3. Predeclare every candidate, mutable field, range, and seed before reading
   results, and count every generated candidate in `N_trials`.
4. Test ADM hypotheses only inside its existing risk/bond architecture; do not
   expand its universe opportunistically after seeing OOS outcomes.
5. Test RMDC factor or risk-layer hypotheses with expanding walk-forward data,
   keeping its current execution and crash-control behavior as the comparator.
6. Use the same split-adjusted panel, T-close/T+1-fill convention, costs, and
   eligibility rules for candidate and incumbent.
7. Run selection through [`evoquant_loop.py`](evoquant_loop.py): typed genome,
   IS-only choice, live-file hash guard, and explicit rejection ledger.
8. Read frozen OOS once, apply the 2024-02 and 2026-07 stress gates as
   pass/fail, and report multiple-testing-adjusted evidence.
9. Require reproducible backtest, SimTradeLab `auto` first-filter, and later
   PTrade minute simulation before any human-reviewed promotion.
10. Do **not** perform an unconstrained LLM rewrite of `ptrade_adm_etf.py` or
    `ptrade_rmdc_etf.py`; bounded verifier-guided edits may all lose, in which
    case retaining the incumbent is the correct result.
