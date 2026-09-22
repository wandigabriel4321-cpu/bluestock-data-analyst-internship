# Day 19 — SQLite schema and data-quality validation

## Scope completed

- Created `db/schema.sql` for all ten Sprint 1 tables.
- Defined SQLite `TEXT`, `INTEGER` and `REAL` data types.
- Added the `companies.id` primary key.
- Added composite `(company_id, year)` primary keys to P&L, balance sheet and
  cash-flow tables.
- Added primary keys and natural-key constraints to the remaining tables.
- Added foreign keys from every child table to `companies.id`.
- Added supporting indexes for year, company and date access patterns.
- Enabled `PRAGMA foreign_keys = ON` in the schema.
- Implemented DQ-01 through DQ-16 in `src/etl/validator.py`.
- Added required rejection, deduplication, correction and audit actions.
- Added CRITICAL and WARNING classifications.
- Created `output/validation_failures.csv`.
- Created `output/validation_summary.csv`, including the DQ-15 informational
  strict-balance counter.
- Added `make schema` and `make validate` commands.

## Automated tests

The complete project suite now contains 40 tests:

- 20 loader and normalisation tests;
- 18 validator tests covering DQ-01 through DQ-16 and CSV output;
- two SQLite schema and constraint tests.

Result: `Ran 40 tests — OK`.

## Official-data validation results

Rules were executed in operational ETL order. Invalid year/ticker rows were
rejected before duplicate and FK checks. Duplicates and orphans were then
removed before warning-level analytical checks.

| Rule | Severity | Recorded occurrences | Result/action |
|---|---|---:|---|
| DQ-01 | CRITICAL | 0 | Company PK unique; no hard load block |
| DQ-02 | CRITICAL | 134 | Discarded duplicate annual rows; kept last |
| DQ-03 | CRITICAL | 401 | Rejected orphan rows |
| DQ-04 | WARNING | 1 | Zero-asset balance requires analyst review |
| DQ-05 | WARNING | 216 | Source OPM retained; computed OPM identified |
| DQ-06 | WARNING | 1 | Non-bank non-positive sales flagged |
| DQ-07 | CRITICAL | 105 | Rejected unparseable periods with raw values logged |
| DQ-08 | CRITICAL | 0 | All remaining tickers valid |
| DQ-09 | WARNING | 1 | Net cash recomputed from CFO + CFI + CFF |
| DQ-10 | WARNING | 0 | No negative fixed assets |
| DQ-11 | WARNING | 90 | Tax rates outside 0–60% flagged |
| DQ-12 | WARNING | 5 | Dividend payouts above 200% flagged |
| DQ-13 | WARNING | 348 | Missing/malformed URLs logged; live HEAD checks optional |
| DQ-14 | WARNING | 7 | Positive-profit EPS inconsistencies flagged |
| DQ-15 | INFO | 1,140/1,140 | All comparable retained balance sheets strictly balance |
| DQ-16 | WARNING | 5 | Limited company histories flagged |

The output contains 640 corrected/rejected CRITICAL occurrences and 674
WARNING occurrences, for 1,314 total records in
`validation_failures.csv`. `load_blocked` is `False` because DQ-01 has no
failure; other CRITICAL violations have a defined rejection or deduplication
action.

## SQLite integration verification

The validated tables were inserted into an in-memory database created directly
from `db/schema.sql`:

| Table | Validated rows inserted |
|---|---:|
| companies | 92 |
| profitandloss | 1,073 |
| balancesheet | 1,140 |
| cashflow | 1,056 |
| analysis | 16 |
| documents | 1,457 |
| prosandcons | 14 |
| sectors | 92 |
| market_cap | 552 |
| stock_prices | 5,520 |
| **Total** | **11,012** |

`PRAGMA foreign_key_check` returned zero rows, confirming that the validated
dataset satisfies all declared foreign-key constraints.

## DQ-13 execution note

URL structure and missing values were validated during this execution. Live
HTTP HEAD validation is fully implemented but remains opt-in through
`--check-urls` to prevent network restrictions, link decay and remote-server
rate limits from blocking the local ETL pipeline.

## Confidentiality

The raw workbooks, processed tables, generated SQLite database and validation
outputs contain internal project information and remain excluded by
`.gitignore`. They must not be committed to a public repository.
