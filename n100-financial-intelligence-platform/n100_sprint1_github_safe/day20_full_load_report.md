# Day 20 — Full Load and Audit Report

**Execution date:** 20 September 2026  
**Scope:** Complete Sprint 1 load of the N100 Financial Intelligence Platform

## Outcome

The end-to-end pipeline read and audited all 12 official Excel workbooks. Ten
Sprint 1 datasets were validated and loaded into `db/nifty100.db` in
foreign-key-safe order. The two remaining files were read successfully and
recorded in the audit as reference inputs for later sprints:

- `financial_ratios.xlsx` — Sprint 2 reference input
- `peer_groups.xlsx` — Sprint 3 reference input

The initial validation identified 640 CRITICAL occurrences. The documented
rejection and deduplication actions were applied, then the complete validation
was repeated. The published database contains **zero CRITICAL failures**, zero
foreign-key violations, and passes `PRAGMA integrity_check`.

## Source-count confirmation

The quantities named in the task were confirmed against the actual source
workbooks before any rows were rejected:

| Dataset | Reference | Actual source | Final database |
|---|---:|---:|---:|
| companies | 92 | 92 | 92 |
| profitandloss | approximately 1,276 | 1,276 | 1,073 |
| balancesheet | approximately 1,312 | 1,312 | 1,140 |
| cashflow | approximately 1,187 | 1,187 | 1,056 |
| stock_prices | 5,520 | 5,520 | 5,520 |

The ten Sprint 1 sources contained 11,652 rows. After 640 controlled
rejections, 11,012 rows were loaded into the database.

## Final database row counts

| Load order | Table | Rows loaded |
|---:|---|---:|
| 1 | companies | 92 |
| 2 | profitandloss | 1,073 |
| 3 | balancesheet | 1,140 |
| 4 | cashflow | 1,056 |
| 5 | analysis | 16 |
| 6 | documents | 1,457 |
| 7 | prosandcons | 14 |
| 8 | sectors | 92 |
| 9 | market_cap | 552 |
| 10 | stock_prices | 5,520 |
|  | **Total** | **11,012** |

## Critical-rejection analysis

The initial CRITICAL occurrences were mutually exclusive after applying the
rules in their documented order, so their count is also the number of rows
excluded before database publication.

| Rule | Reason and action | Count |
|---|---|---:|
| DQ-02 | Duplicate `(company_id, year)`; discarded duplicate and kept the last occurrence | 134 |
| DQ-03 | `company_id` absent from `companies.id`; rejected orphan row | 401 |
| DQ-07 | Unsupported reporting period; rejected invalid-year row | 105 |
|  | **Total resolved CRITICAL occurrences** | **640** |

DQ-02 consisted of 12 P&L, 87 balance-sheet, and 35 cash-flow duplicates.
DQ-03 consisted of 91 P&L, 80 balance-sheet, 96 cash-flow, 4 analysis, 128
document, and 2 pros-and-cons orphans. DQ-07 consisted of 100 `TTM` P&L rows
and five `2024.5` balance-sheet rows that could not be represented as the
required `YYYY-MM` reporting period without inventing information.

## Warning review

The first pass recorded 674 warnings. DQ-09 corrected one cash-flow mismatch
by replacing `net_cash_flow` with the component sum. After correction, the
second pass retained 673 non-blocking warnings for analyst review:

| Rule | Final warnings | Treatment |
|---|---:|---|
| DQ-04 | 1 | Retained and flagged for balance-sheet review |
| DQ-05 | 216 | Retained; computed OPM will be used by the Ratio Engine |
| DQ-06 | 1 | Retained; excluded from growth CAGR where applicable |
| DQ-11 | 90 | Retained and flagged for tax-rate review |
| DQ-12 | 5 | Retained and flagged for dividend review |
| DQ-13 | 348 | Missing/malformed report URLs retained and logged |
| DQ-14 | 7 | Retained and flagged for EPS-sign review |
| DQ-16 | 5 | Limited history flagged for coverage/CAGR handling |
|  | **673** |  |

DQ-13 live HTTP requests remained disabled during this deterministic load.
URL syntax and missing values were validated, while live availability remains
an optional network-dependent check (`--check-urls`).

## Generated artefacts

- `db/nifty100.db` — atomically published 10-table SQLite database
- `output/load_audit.csv` — per-source counts, checksums, rejections and loads
- `output/read_errors.csv` — 105 year-conversion errors from the source files
- `output/validation_failures_initial.csv` — complete pre-correction evidence
- `output/validation_failures.csv` — final warning-only validation report
- `output/validation_summary.csv` — final DQ metrics
- `output/full_load_summary.json` — machine-readable execution summary

## Verification

- Source workbooks audited: **12 of 12**
- Sprint 1 database tables: **10 of 10**
- Database rows: **11,012**
- Final CRITICAL failures: **0**
- SQLite foreign-key violations: **0**
- SQLite integrity check: **ok**
- Automated tests: **44 passed, 0 failed**

## Reproduction

From the project root:

```bash
make full-load PYTHON=.venv/bin/python
make test PYTHON=.venv/bin/python
```

The full load publishes the database only after the corrected second-pass
validation reports zero CRITICAL failures and SQLite passes both foreign-key
and integrity checks.
