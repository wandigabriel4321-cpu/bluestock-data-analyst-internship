# Day 14 — Sprint 2 Final Test and Review Report

**Execution date:** 29 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** Sprint 2 exit checks, manual validation and delivery preparation

## Final outcome

All automated and data-based Day 14 exit gates passed.

| Verification | Result |
|---|---:|
| Complete automated test suite | 140 passed, 0 failed |
| Dedicated formula tests | 60 passed |
| Sprint 2 tests | 90 passed |
| `financial_ratios` rows | 1,155 |
| Distinct companies | 92 |
| Foreign-key violations | 0 |
| SQLite integrity | ok |
| Explained edge-case entries | 6,993 of 6,993 |
| Screener companies | 38 |
| Manual company sample | 5 |
| Manual checks below 0.1 percentage point | 5 of 5 |
| Manual checks within 2 percentage points | 5 of 5 |
| Overall result | PASS |

The 60 dedicated formula tests exceed the task requirement of 20. The 90
Sprint 2 tests exceed the internal target of 26.

## Full engine execution

The ratio engine was run again before the final review. It rebuilt the
`financial_ratios` table idempotently and retained:

- 1,155 unique company-year rows;
- 92 distinct companies;
- zero foreign-key violations;
- no required KPI column that is completely empty.

A pre-review database copy is stored as
`db/backups/nifty100_pre_day14_20260929.db` in the confidential package.

## Edge-case log review

`output/ratio_edge_cases.log` contains 6,993 entries. Every entry contains a
category, metric and written explanation.

| Category | Entries |
|---|---:|
| CAGR edge case | 6,113 |
| Allowed null | 625 |
| OPM mismatch | 216 |
| Debt free | 21 |
| Financials ROCE/ROE review | 18 |
| **Total** | **6,993** |

No unexplained entry remains.

## Preliminary screener

The screener used the latest company-year row for which both metrics were
calculable:

- ROE greater than 15%;
- Debt-to-Equity below 1.

It returned 38 companies, within the required range of 15 to 50. Thirty-four
results passed the immediate business review. Four results were retained but
marked `REVIEW_SOURCE_BASE` because source values produced ROE above 100%:

| Company | ROE | D/E | Review reason |
|---|---:|---:|---|
| BEL | 4,744.05% | 0.5119 | Net profit is large relative to the supplied equity and reserves base. |
| HAL | 3,816.58% | 0.6181 | Net profit is large relative to the supplied equity and reserves base. |
| INDIGO | 892.57% | 0.0186 | Net profit is large relative to the supplied equity and reserves base. |
| NESTLEIND | 117.75% | 0.1033 | Net profit is large relative to the supplied equity and reserves base. |

These values are mathematically consistent with the supplied source rows, but
they require source review before investment interpretation. They were not
silently removed from the screener.

## Reinforced manual validation

Eligible companies were ranked by
`SHA-256("20260929:" + company_id)`. The first five formed the reproducible
sample.

| Rank | Company | End period | Manual ROE difference | Manual 5-year Revenue CAGR difference |
|---:|---|---|---:|---:|
| 1 | BAJAJFINSV | 2024-03 | 0.00 pp | 0.00 pp |
| 2 | BAJAJ-AUTO | 2024-03 | 0.00 pp | 0.00 pp |
| 3 | IRFC | 2024-03 | 0.00 pp | 0.00 pp |
| 4 | PIDILITIND | 2024-03 | 0.00 pp | 0.00 pp |
| 5 | COALINDIA | 2024-03 | 0.00 pp | 0.00 pp |

The review used these independent formulas on the original Excel values:

```text
ROE = net_profit / (equity_capital + reserves) × 100
Revenue CAGR = ((sales_end / sales_start) ^ (1 / 5) - 1) × 100
```

All five companies met both tolerance rules. At least three had to remain
below 0.1 percentage point, and all five had to remain within 2 percentage
points. The maximum observed difference was 0.00 percentage point.

## Generated evidence

- `output/sprint2_final_review_summary.json`
- `output/screener_preview.csv`
- `output/manual_kpi_validation.csv`
- `output/sprint2_final_test_results.txt`
- `docs/sprint2_retro.md`
- `docs/sprint2_technical_documentation.md`

## Reproduction

```bash
make sprint2-final-check PYTHON=.venv/bin/python
```

Confidential workbooks, databases and detailed generated outputs must remain
outside a public GitHub repository.
