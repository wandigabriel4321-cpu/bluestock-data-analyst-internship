# Day 10 — CAGR Engine

Date: 25 September 2026

## Scope completed

The Sprint 2 CAGR engine was implemented in `src/analytics/cagr.py` for:

- Revenue CAGR over 3, 5 and 10 years;
- PAT / net-profit CAGR over 3, 5 and 10 years;
- EPS CAGR over 3, 5 and 10 years.

Each of the nine numeric outputs has its own flag field. The field names match
the corresponding columns already reserved in the `financial_ratios` SQLite
schema.

## Formula and window policy

For valid positive endpoints, the engine applies:

```text
CAGR = ((end_value / start_value) ** (1 / elapsed_years) - 1) * 100
```

Windows use exact reporting periods, not row positions. For example, a 3-year
CAGR ending in `2024-03` requires the `2021-03` observation. This prevents a
missing year from silently changing a 3-year calculation into a 2- or 4-year
calculation. Reporting labels are parsed and sorted chronologically as
`YYYY-MM`, supporting March, September, December and other valid fiscal ends.

## Edge-case flags

| Start | End | Numeric CAGR | Flag |
|---|---|---:|---|
| Positive | Positive | Calculated | `OK` |
| Positive | Negative or zero | `None` | `DECLINE_TO_LOSS` |
| Negative | Positive | `None` | `TURNAROUND` |
| Negative | Negative or zero | `None` | `BOTH_NEGATIVE` |
| Zero | Any finite value | `None` | `ZERO_BASE` |
| Missing endpoint or exact reporting period | — | `None` | `INSUFFICIENT` |

The sign is classified before any fractional-power operation. Consequently,
negative inputs can never produce a misleading real or complex CAGR value.

## Implementation components

- `calculate_cagr()` classifies endpoints and calculates valid CAGR values;
- `parse_reporting_year()` validates fiscal reporting labels;
- `sort_annual_records()` sorts years and rejects duplicates;
- `calculate_window_cagr()` selects exact elapsed-year endpoints;
- `calculate_company_cagrs()` creates nine values and nine separate flags;
- `calculate_dataset_cagrs()` groups records by company;
- `write_cagr_audit()` writes a reproducible value/flag CSV;
- `python -m src.analytics.cagr` runs the audit directly from SQLite.

## Automated tests

`tests/kpi/test_cagr.py` contains 16 focused tests covering:

- all six required CAGR states;
- exact positive CAGR arithmetic;
- correct chronological ordering of unsorted inputs;
- exact elapsed-year window selection;
- missing-period handling;
- Revenue CAGR for 3, 5 and 10 years;
- separate PAT and EPS flags;
- all nine value/flag pairs;
- company grouping and deterministic ordering;
- duplicate and invalid reporting periods;
- invalid CAGR periods;
- CSV audit structure.

Verification result:

- Day 10 CAGR tests: **16 passed**;
- complete project regression suite: **94 passed, 0 failed**.

## Real-data audit

The reproducible command below evaluated all populated P&L records:

```bash
make cagr-audit PYTHON=.venv/bin/python
```

It generated the confidential output `output/cagr_day10.csv` with 20 columns:
company, calculation date, nine CAGR values and nine corresponding flags.

| Metric | Window | Calculated | OK | Decline to loss | Turnaround | Zero base | Insufficient |
|---|---:|---:|---:|---:|---:|---:|---:|
| Revenue | 3 years | 89 | 89 | 0 | 0 | 0 | 3 |
| Revenue | 5 years | 89 | 89 | 0 | 0 | 0 | 3 |
| Revenue | 10 years | 78 | 78 | 0 | 0 | 1 | 13 |
| PAT | 3 years | 82 | 82 | 2 | 5 | 0 | 3 |
| PAT | 5 years | 82 | 82 | 2 | 5 | 0 | 3 |
| PAT | 10 years | 74 | 74 | 2 | 2 | 1 | 13 |
| EPS | 3 years | 82 | 82 | 2 | 5 | 0 | 3 |
| EPS | 5 years | 81 | 81 | 2 | 5 | 0 | 4 |
| EPS | 10 years | 73 | 73 | 2 | 3 | 1 | 13 |

Audit totals:

- source P&L rows evaluated: **1,073**;
- companies evaluated: **92**;
- duplicate company outputs: **0**;
- non-finite calculated values: **0**.

No `BOTH_NEGATIVE` transition occurred in these nine latest-period windows,
but the behavior is implemented and covered by an automated test.

## Outcome

Day 10 is complete. The CAGR engine handles exact fiscal-year windows, never
calculates through negative-value transitions, preserves flags separately from
values and is ready for insertion into `financial_ratios` during Day 12.
