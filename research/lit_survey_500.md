# Literature survey: 284 unique sources (500 target not reached)

Generated on 2026-08-22 from the sibling CSVs that existed after the requested
12-minute wait.  The merged, row-level bibliography is
[`lit_survey_500.csv`](lit_survey_500.csv).

## Honest source count

Only two of the four requested inputs arrived.  They contained 289 rows; URL
deduplication removed 3 rows, then title deduplication removed 2 more, leaving
**284 unique sources**.  This is **216 short of 500**.  No synthetic or
placeholder references were added.

| Requested input | Status after 12 minutes | Input rows | Retained after global dedup |
| --- | --- | ---: | ---: |
| `lit_cn_sources.csv` | missing | 0 | 0 |
| `lit_en_momentum.csv` | missing | 0 | 0 |
| `lit_en_alphamine.csv` | present | 147 | 145 |
| `lit_crowding_crossasset.csv` | present | 142 | 139 |
| **Total** | **2 present / 2 missing** | **289** | **284** |

Deduplication is deterministic and respects the requested file order.  URLs
are stripped, case-folded, and normalized for a trailing slash before keeping
the first occurrence.  The survivors are then deduplicated by stripped,
case-folded, whitespace-normalized title.  Blank keys, had there been any,
would not have been collapsed.

## Coverage in the available inputs

The alpha-mining file contributes 91 papers, 30 code repositories, 16 surveys,
3 benchmarks, 2 platforms, and one each of book, tool, and dataset.  The
cross-asset file contributes 139 retained records across gold (29), crowding
(24), momentum (24), low volatility (20), quality (15), China unwind (15),
index-futures basis/IC (7), and QDII premium (5).  Publication years span
1993–2026.

This is not a complete 500-source survey: the missing Chinese-source and
dedicated English-momentum files leave known language and topic gaps.  The CSV
should be regenerated if those inputs arrive; this report does not infer their
contents from secondary references already present.

## What we will actually test next

1. Keep **ADM and RMDC as the frozen incumbents**.  A literature source is an
   a-priori hypothesis, not evidence that either live strategy should be
   replaced.
2. Translate only a small, typed, predeclared set of literature-backed changes
   into the ADM/RMDC candidate genome.  Preserve the live universe and
   execution constraints, record every generated candidate in `N_trials`, and
   make no edits merely because a paper reports a high return.
3. Send those candidates through the existing
   [`evoquant_loop.py`](evoquant_loop.py) verifier: IS-only selection,
   one-time frozen OOS reading, transaction-cost and stress gates, multiple-test
   accounting, and live-file hash protection.
4. Do **not** use an unconstrained LLM rewrite of `ptrade_adm_etf.py` or
   `ptrade_rmdc_etf.py`.  The EvoQuant-style loop proposes bounded edits and
   verifies them; a human-reviewed promotion is the only path to a live-file
   change.  “No candidate beats the incumbent” remains an acceptable result.
