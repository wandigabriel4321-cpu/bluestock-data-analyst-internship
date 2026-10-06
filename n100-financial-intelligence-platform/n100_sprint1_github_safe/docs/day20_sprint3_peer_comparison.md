# Sprint 3 Day 20 — Peer Comparison Excel Report

Date: 6 October 2026  
Status: Complete

## Scope completed

- Created `src/analytics/peer_report.py`.
- Generated `output/peer_comparison.xlsx` with exactly 11 worksheets, one for
  each official peer group.
- Included all 56 assigned companies exactly once.
- Included two identifiers, 20 raw KPI columns and the 10 officially defined
  Day 18 percentile columns on every worksheet.
- Highlighted the official benchmark company in gold/amber.
- Added a recomputed group-median row as the last row on every worksheet.
- Added filters, frozen identifier columns, readable widths, financial number
  formats and percentile colour bands.
- Generated a reproducible worksheet-level audit.

## Interpretation of the metric requirement

The task mentions 20 metric columns and also says “percentile rank for each
metric”, while the Sprint 3 objective defines peer percentiles for only 10
official metrics. The implemented, documented interpretation is therefore:

- 20 raw KPI columns; and
- 10 percentile columns corresponding to the 10 metrics officially ranked on
  Day 18.

Together with `company_id` and `company_name`, every sheet has 32 columns.
No additional percentile was fabricated for a metric outside the official
ranking specification.

## Raw KPI columns

1. Sprint 3 Composite Score;
2. Sector-relative Composite Score;
3. Return on Equity;
4. Return on Capital Employed;
5. Net Profit Margin;
6. Operating Profit Margin;
7. Free Cash Flow;
8. FCF CAGR 5yr;
9. CFO/PAT Ratio 5yr;
10. Revenue CAGR 3yr;
11. Revenue CAGR 5yr;
12. PAT CAGR 5yr;
13. EPS CAGR 5yr;
14. Debt-to-Equity;
15. Interest Coverage;
16. Asset Turnover;
17. P/E;
18. P/B;
19. Dividend Yield;
20. Sales.

## Official percentile columns

1. ROE;
2. ROCE;
3. Net Profit Margin;
4. Debt-to-Equity;
5. Free Cash Flow;
6. PAT CAGR 5yr;
7. Revenue CAGR 5yr;
8. EPS CAGR 5yr;
9. Interest Coverage;
10. Asset Turnover.

The raw value and percentile for every official metric come from the same
latest non-null `peer_percentiles` observation. Debt-to-Equity uses the
already-inverted Day 18 percentile, so a lower D/E receives a higher rank.

## Formatting rules

- percentile greater than or equal to 75: green;
- percentile less than or equal to 25: red;
- percentile strictly between 25 and 75: yellow;
- missing percentile: grey;
- official benchmark row: gold/amber;
- final group-median row: blue.

At the exact boundaries, 75 belongs to the green band and 25 belongs to the
red band. Benchmark and median row formatting takes precedence over the
individual percentile-cell fill so those special rows remain identifiable.

Percentage, ratio, percentile and rupee-crore values use separate number
formats. Every worksheet freezes at `C2`, filters the company rows and repeats
the header when printed.

## Verified results

| Check | Result |
|---|---:|
| Worksheets | 11/11 |
| Assigned companies represented | 56/56 |
| Unique companies | 56 |
| Raw KPI columns per sheet | 20 |
| Percentile columns per sheet | 10 |
| Total columns per sheet | 32 |
| Official benchmarks | 11/11 |
| Benchmark rows highlighted | 11/11 |
| Duplicate companies | 0 |
| Correct group medians | 11/11 |
| Percentiles outside 0–100 | 0 |
| Worksheet validation status | 11/11 PASS |
| New Day 20 tests | 13/13 PASS |
| Complete regression suite | 221/221 PASS |

## Outputs

- `output/peer_comparison.xlsx` — principal 11-sheet deliverable;
- `output/peer_comparison_audit.csv` — sheet-level validation evidence;
- `output/day20_test_results.txt` — focused and complete test evidence;
- `src/analytics/peer_report.py` — reusable report generator and validator;
- `tests/analytics/test_peer_report.py` — Day 20 test suite.

## Reproduction

```bash
python -m src.analytics.peer_report \
  --database db/nifty100.db \
  --output output/peer_comparison.xlsx \
  --audit output/peer_comparison_audit.csv

python -m unittest tests.analytics.test_peer_report -v
python -m unittest discover -s tests -p "test_*.py" -v
```

