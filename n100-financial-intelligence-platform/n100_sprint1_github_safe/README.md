# N100 Financial Intelligence Platform

Sprint 1 prepares the source data for a validated SQLite database. The project
loads the supplied Nifty 100 workbooks, normalises identifiers and reporting
periods, validates data quality and records all accepted and rejected rows.

## Confidentiality

The source workbooks are company-provided project data. They are excluded from
Git through `.gitignore` and must not be published in a public repository.

## Current Sprint 1 structure

- `data/raw`: original source workbooks, unchanged
- `data/supporting`: five official supplementary workbooks, unchanged
- `data/processed`: normalised extracts created by the ETL
- `src/etl`: inventory, normalisation, loading and validation code
- `db`: SQLite schema and generated database
- `tests/etl`: automated ETL tests
- `output`: load and validation reports
- `docs`: project notes and data dictionary

The project uses 12 source workbooks but loads ten tables during Sprint 1.
`financial_ratios.xlsx` is a Sprint 2 reference and `peer_groups.xlsx` is used
for the Sprint 3 peer-comparison work. The official 16 ETL rules are recorded
in `docs/data_quality_rules.md`.

## Loader

The Day 2 loader is implemented in `src/etl/loader.py`. It detects all 12
official workbooks even when their downloaded names contain a timestamp and
hash prefix, selects the required worksheet and header row, validates the
schema, standardises column names and missing values, normalises tickers and
reporting periods, converts numeric and percentage values, and logs read or
conversion errors to `output/read_errors.csv`.

Run the ten-table Sprint 1 load with:

```bash
make load PYTHON=.venv/bin/python
```

Run the automated tests with:

```bash
make test PYTHON=.venv/bin/python
```

## SQLite schema and data-quality validation

`db/schema.sql` defines the ten Sprint 1 tables, their SQLite data types,
primary keys, composite annual keys, foreign keys and supporting indexes. It
starts with `PRAGMA foreign_keys = ON`; every application connection must also
enable this connection-level SQLite setting.

Create the empty database schema with:

```bash
make schema PYTHON=.venv/bin/python
```

`src/etl/validator.py` implements DQ-01 through DQ-16. It applies required
rejections and corrections in a controlled order and writes both
`output/validation_failures.csv` and `output/validation_summary.csv`.

Run validation after the loader with:

```bash
make validate PYTHON=.venv/bin/python
```

Live HTTP HEAD checks for DQ-13 are intentionally opt-in because annual-report
websites may be unavailable or rate-limited. Enable them with:

```bash
python -m src.etl.validator --check-urls
```

## Complete Sprint 1 load

`src/etl/pipeline.py` executes the complete Day 20 workflow. It reads and
audits all 12 official workbooks, validates the ten Sprint 1 tables, preserves
the initial rejection evidence, applies the documented DQ actions, repeats the
validation, and atomically publishes `db/nifty100.db` only when the final pass
has zero CRITICAL failures and SQLite has zero foreign-key violations.

Run the complete workflow with:

```bash
make full-load PYTHON=.venv/bin/python
```

The generated audit artefacts are:

- `output/load_audit.csv`
- `output/read_errors.csv`
- `output/validation_failures_initial.csv`
- `output/validation_failures.csv`
- `output/validation_summary.csv`
- `output/full_load_summary.json`

The verified 20 September 2026 execution loaded 11,012 rows into ten database
tables, resolved 640 initial CRITICAL occurrences, and finished with zero
CRITICAL failures. See `docs/day20_full_load_report.md` for the source counts,
rejection analysis, final warning breakdown and verification evidence.

## Final validation and exploratory review

Day 21 adds a deterministic five-company source-to-database review. The sample
is selected by ranking `SHA-256("20260921:" + company_id)`, which makes the
selection reproducible and independent of physical row order. The review
compares each sampled company across all ten Sprint 1 tables and writes:

- `output/manual_review.csv`
- `output/manual_review_summary.json`
- `output/limited_year_coverage.csv`

Run it with:

```bash
make manual-review PYTHON=.venv/bin/python
```

The ten exploratory queries are stored in
`notebooks/exploratory_queries.sql`. Execute them with:

```bash
make explore PYTHON=.venv/bin/python
```

The query runner writes an execution audit and ten CSV result files under
`output/`. Run the complete Sprint 1 workflow, including all tests, with:

```bash
make final-check PYTHON=.venv/bin/python
```

The verified 21 September 2026 review produced 50 matching table-level
comparisons, zero mismatches, zero foreign-key violations, ten successful SQL
queries and 49 passing automated tests. Three companies require limited-history
handling under DQ-16: `ATGL`, `JIOFIN` and `SBIN`. Full evidence appears in
`docs/day21_final_validation_report.md`.

## Sprint 2 — financial ratio engine

Day 08 adds `src/analytics/ratios.py` with guarded calculations for Net Profit
Margin, Operating Profit Margin, ROE, ROCE and ROA. The OPM cross-check records
differences greater than one percentage point, while Financials-sector
membership is read from the official `sectors` table for later sector-relative
rules.

`db/schema.sql` now includes the Sprint 2 `financial_ratios` table with a unique
company-year key and the explicitly required downstream KPI fields. Run the
Day 08 test module with:

```bash
make test-profitability PYTHON=.venv/bin/python
```

The verified 23 September 2026 execution passed all 12 profitability tests and
the complete 62-test regression suite. See
`docs/day23_sprint2_foundation.md` for formulas, schema decisions and audit
results.

Day 09 adds Debt-to-Equity, dynamic Financials-sector high-leverage
suppression, Interest Coverage assessment, Net Debt and Asset Turnover. The
verified 24 September 2026 execution passed all 16 new leverage and efficiency
tests and the complete 78-test regression suite. See
`docs/day24_sprint2_leverage_efficiency.md` for edge-case decisions and the
real-data audit.

Day 10 adds the CAGR engine for Revenue, PAT and EPS over exact 3-, 5- and
10-year reporting windows. Negative transitions, zero bases and incomplete
histories receive separate flags instead of invalid calculations. Run its tests
and real-data audit with:

```bash
make test-cagr PYTHON=.venv/bin/python
make cagr-audit PYTHON=.venv/bin/python
```

The verified 25 September 2026 execution passed all 16 new CAGR tests and the
complete 94-test regression suite. The real-data audit covered 1,073 P&L rows
and all 92 companies. See `docs/day25_sprint2_cagr_engine.md` for formulas,
edge-case decisions and per-window results.

Day 11 adds Free Cash Flow, annual and five-year CFO/PAT analysis, CFO Quality,
CapEx Intensity, FCF Conversion and the exhaustive CFO/CFI/CFF capital-
allocation matrix. Run the focused tests and regenerate the required CSV with:

```bash
make test-cashflow PYTHON=.venv/bin/python
make cashflow-audit PYTHON=.venv/bin/python
```

The verified 26 September 2026 execution passed all 16 new cash-flow tests and
the complete 110-test regression suite. `output/capital_allocation.csv`
contains 1,054 eligible annual rows, all six required columns and zero blank
pattern labels. See `docs/day26_sprint2_cashflow_kpis.md` for formulas,
classification decisions and the real-data distribution.

Day 12 adds `src/analytics/ratio_engine.py`, the idempotent orchestrator that
builds the company-year universe from the union of P&L, Balance Sheet and Cash
Flow keys, calculates the complete Sprint 2 KPI set and atomically replaces the
SQLite `financial_ratios` table. It also verifies required-column coverage,
compares every available value with the official pre-computed workbook and
records all permitted edge cases.

Run the complete Day 12 load with:

```bash
make ratio-engine PYTHON=.venv/bin/python
```

The verified 27 September 2026 execution produced 1,155 unique company-year
rows for all 92 companies, zero foreign-key violations and no completely empty
required KPI column. The output audit files are:

- `output/ratio_engine_load_audit.csv`;
- `output/financial_ratios_null_audit.csv`;
- `output/financial_ratios_reference_comparison.csv`;
- `output/financial_ratios_comparison_summary.json`;
- `output/ratio_edge_cases.log`.

Run the focused Day 12 tests with:

```bash
make test-ratio-engine PYTHON=.venv/bin/python
```

See `docs/day27_ratio_engine_load.md` for formulas, comparison policy and exit
gate evidence.

Day 13 formalises the Financials-sector carve-out. Banks, NBFCs and insurers
are identified from `sectors.broad_sector` and `sectors.sub_sector`, and the
ordinary D/E greater-than-five warning is not applied to them. ROCE remains
calculated for transparency but is interpreted against the relevant financial
entity group instead of an industrial-company absolute threshold.

The review compares the latest calculable ROCE and ROE with the company-level
reference fields, records differences above five percentage points and assigns
one of the required audit explanations: source problem, version difference,
formula difference or insufficient history.

Run the integrated Day 13 review with:

```bash
make sector-review PYTHON=.venv/bin/python
make test-sector-review PYTHON=.venv/bin/python
```

The verified 28 September 2026 execution reviewed all 23 companies currently
classified as Financials, produced 46 ROCE/ROE comparisons and appended 18
material or insufficient-history findings to `output/ratio_edge_cases.log`.
The task's count of 19 is treated as a source-version difference because the
supplied `sectors.xlsx`, processed extract and SQLite database all contain 23,
while no historical 19-company membership list was supplied. Full evidence is
in `docs/day28_financials_roce_review.md` and
`output/sector_roce_notes.csv`.

Day 14 adds `src/analytics/sprint2_review.py`, which independently recalculates
ROE and five-year Revenue CAGR from the original workbooks for a reproducible
five-company sample. It also audits every explanation in
`output/ratio_edge_cases.log` and runs the preliminary screen using the latest
calculable ROE greater than 15% and Debt-to-Equity below 1.

Run the complete Sprint 2 exit review with:

```bash
make sprint2-final-check PYTHON=.venv/bin/python
```

The verified 29 September 2026 execution produced 1,155 ratio rows for all 92
companies, zero foreign-key violations, 6,993 explained edge cases and 38
screener companies. All five manual ROE and Revenue CAGR checks matched the
database with a 0.00 percentage-point difference. The complete regression
suite passed 140 tests, including 60 dedicated formula tests and 90 Sprint 2
tests. See `docs/day29_sprint2_final_review.md`,
`docs/sprint2_technical_documentation.md` and `docs/sprint2_retro.md`.

The 30 September 2026 release check repeated the complete engine and all tests,
confirmed non-empty mandatory-column coverage and re-audited the public package
for confidential files. The release remained at 1,155 rows, 92 companies and
140 passing tests. See `docs/day30_release_and_submission_check.md` and
`output/sprint2_validation_report.csv`.
