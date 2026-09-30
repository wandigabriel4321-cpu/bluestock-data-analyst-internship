# Day 21 — Final Validation and Documentation Report

**Execution date:** 21 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** Sprint 1 final review and submission preparation

## Final outcome

The Sprint 1 database passed the reproducible manual review, the SQLite
foreign-key check, all automated tests, and all ten exploratory SQL queries.

| Verification | Result |
|---|---:|
| Reproducible company sample | 5 companies |
| Source-to-database table comparisons | 50 |
| Matching comparisons | 50 |
| Mismatches | 0 |
| Foreign-key violations | 0 |
| Exploratory queries executed | 10 of 10 |
| Automated tests | 49 passed, 0 failed |
| Final review status | PASS |

## Reproducible sample

The sample was selected by ranking each company using
`SHA-256("20260921:" + company_id)` and taking the five lowest hash values.
This method is deterministic and independent of the physical row order.

| Rank | Company ID | Company name |
|---:|---|---|
| 1 | PNB | Punjab National Bank |
| 2 | BANKBARODA | Bank of Baroda |
| 3 | AXISBANK | Axis Bank Ltd |
| 4 | RELIANCE | Reliance Industries Ltd |
| 5 | COALINDIA | Coal India Ltd |

Each company was reviewed across all ten Sprint 1 tables. The review compared
the source values after the documented DQ actions with the values published in
SQLite. All 50 table-level checks passed. The original row counts, post-DQ row
counts, database row counts and SHA-256 content checksums are recorded in
`output/manual_review.csv`.

## Reporting-year coverage

Coverage was calculated independently for `profitandloss`, `balancesheet` and
`cashflow`. Five table-level findings across three companies contained fewer
than five valid reporting years:

| Company | Table | Valid years | Result |
|---|---|---:|---|
| ATGL | cashflow | 0 | REVIEW |
| JIOFIN | profitandloss | 2 | REVIEW |
| JIOFIN | balancesheet | 3 | REVIEW |
| JIOFIN | cashflow | 2 | REVIEW |
| SBIN | balancesheet | 0 | REVIEW |

These findings are retained in `output/limited_year_coverage.csv`. Companies
with fewer than three valid years in a required annual table must be excluded
from the related CAGR calculation, in accordance with DQ-16.

## SQLite verification

`PRAGMA foreign_keys = ON` was enabled before review. The command
`PRAGMA foreign_key_check` returned zero rows, confirming that no published
record violates the declared relationships. The preceding Day 20 integrity
check also returned `ok`.

## Exploratory SQL queries

`notebooks/exploratory_queries.sql` contains ten numbered queries covering:

1. row counts for all Sprint 1 tables;
2. company distribution by broad sector;
3. largest companies by latest market capitalisation;
4. highest sales in the latest reporting year;
5. calculated operating-margin comparison;
6. borrowings relative to total assets;
7. operating cash flow compared with net profit;
8. first-to-last stock-price return;
9. annual-data coverage by company;
10. latest integrated financial and market snapshot.

All ten queries executed successfully. Their row counts and output filenames
are recorded in `output/exploratory_query_audit.csv`, with individual results
stored in `output/exploratory_results/`.

## Test and structure review

The final suite contains 49 tests covering normalisation, loader behaviour,
all 16 data-quality rules, schema constraints, atomic database publication,
manual-review reproducibility and exploratory-query structure. All tests pass.

The final structure keeps source data, processed extracts, the database and
generated reports outside Git tracking. The GitHub-safe package contains only
code, tests, SQL, schemas, configuration templates and non-confidential project
documentation. The company-provided PDF, original workbooks, generated SQLite
database and detailed validation outputs must not be committed to a public
repository.

## Reproduction

Run the entire Sprint 1 workflow from the project root:

```bash
make final-check PYTHON=.venv/bin/python
```

This command repeats the full load, the reproducible manual review, all ten
exploratory queries and the complete automated test suite.

## Generated Day 21 evidence

- `output/manual_review.csv`
- `output/manual_review_summary.json`
- `output/limited_year_coverage.csv`
- `notebooks/exploratory_queries.sql`
- `output/exploratory_query_audit.csv`
- `output/exploratory_results/Q01.csv` through `Q10.csv`
- `docs/day21_final_validation_report.md`

GitHub publication and Google Drive upload require the account owner's final
external upload action. The prepared packages and exact submission procedure
are documented in `docs/SUBMISSION_GUIDE.md`.
