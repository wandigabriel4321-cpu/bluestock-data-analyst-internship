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
