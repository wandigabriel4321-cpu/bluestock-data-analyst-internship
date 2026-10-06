# Sprint 3 — Day 17 Composite Score and Screener Excel

**Scheduled date:** 3 October 2026  
**Rebuilt and validated:** 6 October 2026  
**Status:** PASS

## Deliverables

- `src/screener/composite_score.py` — FCF CAGR, winsorisation, normalisation,
  global score and sector-relative score.
- `src/screener/excel_report.py` — six-sheet Excel generator and workbook
  validator.
- `output/screener_output.xlsx` — final formatted screener workbook.
- `output/composite_score_audit.csv` — 92-company score and component audit.
- `output/composite_score_bounds.csv` — global and sector P10/P90 bounds.
- `output/day17_workbook_validation.csv` — sheet-level validation evidence.
- `tests/screener/test_composite_score.py` — 14 Day 17 tests.

## New Sprint 3 formula

| Pillar | Component | Weight |
| --- | --- | ---: |
| Profitability | ROE | 15% |
| Profitability | ROCE | 10% |
| Profitability | Net Profit Margin | 10% |
| Cash Quality | FCF CAGR 5yr | 15% |
| Cash Quality | CFO/PAT Ratio 5yr | 10% |
| Cash Quality | FCF Positive Flag | 5% |
| Growth | Revenue CAGR 5yr | 10% |
| Growth | PAT CAGR 5yr | 10% |
| Leverage | D/E Score | 10% |
| Leverage | Interest Coverage Score | 5% |

The weights sum to exactly 100%. The earlier Sprint 2
`composite_quality_score` is preserved as
`legacy_composite_quality_score`; it is neither overwritten nor used as the
new score.

## FCF CAGR policy

FCF CAGR uses the exact reporting period five years before each company’s
current screener year. It is computed only when both endpoints are positive.
Sign transitions and incomplete histories receive separate flags rather than
entering an invalid fractional-power calculation.

| FCF CAGR status | Companies |
| --- | ---: |
| OK | 47 |
| TURNAROUND | 16 |
| DECLINE_TO_LOSS | 8 |
| BOTH_NEGATIVE | 17 |
| INSUFFICIENT | 4 |

## Normalisation and missing values

1. Finite values are winsorised at their P10 and P90 limits.
2. Winsorised values are scaled linearly to 0–100.
3. D/E is inverted so lower leverage receives the higher score.
4. Debt-Free ICR labels receive the top finite ICR treatment before P90
   capping.
5. FCF Positive Flag is 100 when latest FCF is positive and 0 when it is
   non-positive.
6. A missing component remains missing in the audit columns. For the final
   weighted score only, it receives the neutral normalised value 50 — never
   zero — so the official weights remain unchanged and missing data is neither
   rewarded nor severely penalised.
7. `global_score_coverage_pct` and `sector_score_coverage_pct` disclose the
   weight represented by observed components for every company.

Global normalisation uses the 92-company universe. Sector-relative
normalisation independently recalculates P10/P90 within each `broad_sector`.
Constant distributions receive the neutral component score 50.

## Score validation

| Check | Result |
| --- | ---: |
| Companies scored | 92 |
| Companies with 100% component coverage | 45 |
| Global score minimum | 17.142273 |
| Global score maximum | 77.259828 |
| Normalisation-bound rows | 110 |
| Legacy score preserved | Yes |

## Excel structure

`output/screener_output.xlsx` contains exactly six sheets:

| Sheet | Rows | KPIs | Status |
| --- | ---: | ---: | --- |
| Quality Compounder | 21 | 20 | PASS |
| Value Pick | 2 | 20 | PASS |
| Growth Accelerator | 19 | 20 | PASS |
| Dividend Champion | 30 | 20 | PASS |
| Debt-Free Blue Chip | 2 | 20 | PASS |
| Turnaround Watch | 31 | 20 | PASS |

The 20 KPI columns are:

1. Sprint 3 Composite Score;
2. Sector-Relative Composite Score;
3. ROE;
4. ROCE;
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
16. P/E;
17. P/B;
18. Dividend Yield;
19. Dividend Payout Ratio;
20. Sales.

Identifier and audit columns are kept outside the 20-KPI count. Every sheet is
sorted by the new Sprint 3 score descending and includes filters, a frozen
header row, readable widths and numeric formatting. Preset-threshold cells use
green when the rule passes and red when it fails. Because the workbook contains
selected preset results, the official output cells pass; the red failure path
is separately covered by an automated style test.

## Automated tests

- Day 17 focused tests: **14 passed**.
- Complete project suite: **184 passed, 0 failures**.
- Workbook validation: **6 of 6 sheets PASS**.

Tests cover exact FCF CAGR windows, negative FCF cases, P10/P90 capping,
inverse scaling, constant distributions, official weights, missing-value
treatment, legacy-score preservation, sector scoring, exact sheet count,
non-empty sheets, 20 KPI columns, sorting, filters, frozen panes and green/red
threshold styling.

## Execution

```bash
make day17-excel PYTHON=python3
make test-composite-score PYTHON=python3
make day17-check PYTHON=python3
```
