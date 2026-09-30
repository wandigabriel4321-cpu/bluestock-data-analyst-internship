# Day 17 technical analysis

## Work completed

- Received and inventoried all 12 Excel source workbooks.
- Read and visually checked the 43-page official project specification.
- Confirmed the 7 core and 5 supplementary datasets.
- Confirmed the ten Sprint 1 SQLite tables.
- Extracted the official 16 data-quality rules.
- Identified the exact `YYYY-MM` year-normalisation contract.
- Created the official project directory structure.
- Created a virtual environment and dependency file.
- Created `.env.example`, `config/.env.template`, `.gitignore`,
  `Makefile`, source package and test package.
- Implemented the first version of `normaliser.py`.
- Tested ticker and reporting-period normalisation.
- Generated a machine-readable 12-workbook inventory.
- Calculated source checksums so future changes can be detected.

## Resolution of the table-count discrepancy

The specification uses three different counts for different concepts:

- **12 files:** seven core workbooks plus five supplementary workbooks.
- **10 Sprint 1 SQLite tables:** seven core tables plus `sectors`,
  `market_cap` and `stock_prices`.
- **Later analytical structures:** `financial_ratios` is generated in Sprint
  2 and peer-group outputs are developed in Sprint 3.

Therefore, the correct Sprint 1 database target is ten tables. The two remaining
supplementary workbooks are reference and later-sprint inputs, not missing
initial database tables.

## Starter-code decision

No starter Python source code was included in the official 13-file package.
The PDF supplies specifications, examples and required paths, but the Python
implementation must be created by the analyst. The previously seen Google
Drive folders are not substitutes for the N100 source package.

## Preliminary official-rule results

| Rule | Initial result |
|---|---|
| DQ-01 | PASS: 92 unique company IDs |
| DQ-02 | 12 P&L, 87 BS and 35 CF duplicates after year normalisation |
| DQ-03 | 414 orphan child rows across the core data |
| DQ-04 | PASS: no balance-sheet difference at or above 1% |
| DQ-05 | 234 rows differ by at least one OPM percentage point |
| DQ-06 | One non-bank row has non-positive sales |
| DQ-07 | 100 P&L and five BS periods are unparseable under the official rules |
| DQ-08 | PASS: no missing or invalid-length ticker after normalisation |
| DQ-09 | One row exceeds the ₹10 crore net-cash tolerance |
| DQ-10 | PASS: no negative fixed assets |
| DQ-11 | 108 tax-rate values fall outside 0–60% |
| DQ-12 | Seven dividend-payout values exceed 200% |
| DQ-13 | 383 annual-report values are blank, `Null`, incomplete or malformed; live HEAD checks remain for the validator stage |
| DQ-14 | Five positive-profit rows have non-positive EPS |
| DQ-15 | PASS: zero strict balance-sheet differences |
| DQ-16 | P&L: 1 company below five years; BS: 2; CF: 2 |

These are discovery results, not corrections to the source data. The loader
must reject, flag, deduplicate or recalculate rows exactly as the official rule
requires and must record every action in `validation_failures.csv` and
`load_audit.csv`.

## Updated technical direction

The next implementation step is Day 2 of Sprint 1:

1. Finish 20 normalisation cases for years and 20 for tickers.
2. Implement `src/etl/loader.py` with `header=1` for core and `header=0`
   for supplementary workbooks.
3. Preserve `raw_value` when a period becomes `PARSE_ERROR`.
4. Normalise before applying DQ-02 and DQ-03.
5. Keep the last duplicate only after logging every discarded occurrence.
6. Do not add the confidential workbooks to a public Git repository.
