# Sprint 2 Technical Documentation

## Purpose

Sprint 2 extends the validated Sprint 1 SQLite database with a reproducible
financial-ratio engine. All computed values originate from the validated
`profitandloss`, `balancesheet`, `cashflow`, `companies` and `sectors` tables.
The supplied `financial_ratios.xlsx` file is used only for comparison.

## Main modules

| Module | Responsibility |
|---|---|
| `src/analytics/ratios.py` | Profitability, leverage and efficiency formulas |
| `src/analytics/cagr.py` | 3-, 5- and 10-year Revenue, PAT and EPS CAGR |
| `src/analytics/cashflow_kpis.py` | Cash-flow KPIs and capital-allocation labels |
| `src/analytics/ratio_engine.py` | Company-year construction, calculations and SQLite loading |
| `src/analytics/sector_roce.py` | Financials carve-out and ROCE/ROE anomaly classification |
| `src/analytics/sprint2_review.py` | Final screener, edge-log audit and manual source validation |

## Database design

`db/schema.sql` defines `financial_ratios` with a unique `(company_id, year)`
key and a foreign key to `companies(id)`. CAGR values and their flags occupy
separate columns. The table stores formula results and classifications without
replacing permitted missing values with zero.

The engine builds its company-year population using the union of annual keys
from P&L, Balance Sheet and Cash Flow. Repeated executions atomically replace
the calculated table and retain one row per company and reporting period.

## Formula policy

- Safe division returns `None` for missing or invalid denominators.
- ROE uses `net_profit / (equity_capital + reserves) × 100`.
- ROCE uses EBIT divided by equity, reserves and borrowings.
- Debt-free companies receive D/E of zero when borrowings are zero.
- Interest Coverage remains `None` when interest is zero and receives a
  separate label when the company is debt free.
- CAGR uses exact year-month endpoints and stores special-case flags.
- Free Cash Flow permits negative results.
- CapEx Intensity uses the absolute investing cash-flow amount.
- Capital-allocation classification covers all eight sign combinations.
- Banks, NBFCs and insurers do not receive the ordinary D/E greater-than-five
  warning.

## Principal outputs

| Output | Purpose |
|---|---|
| `db/nifty100.db` | Final relational database |
| `output/ratio_engine_load_audit.csv` | Ratio-table load evidence |
| `output/financial_ratios_null_audit.csv` | Required-column coverage |
| `output/financial_ratios_reference_comparison.csv` | Calculated versus supplied reference values |
| `output/capital_allocation.csv` | CFO/CFI/CFF pattern labels |
| `output/sector_roce_notes.csv` | Financials ROCE/ROE review |
| `output/ratio_edge_cases.log` | Documented exceptions and permitted missing values |
| `output/screener_preview.csv` | Preliminary ROE and D/E screen |
| `output/manual_kpi_validation.csv` | Independent five-company formula validation |
| `output/sprint2_final_review_summary.json` | Final machine-readable exit result |

## Verification

The 29 September 2026 release contains:

- 1,155 `financial_ratios` rows;
- 92 distinct companies;
- zero foreign-key violations;
- SQLite integrity result `ok`;
- 6,993 edge cases with written explanations;
- 38 preliminary screener companies;
- five manual ROE and Revenue CAGR validations with zero difference;
- 140 passing automated tests.

## Execution

```bash
make ratio-engine PYTHON=.venv/bin/python
make sprint2-review PYTHON=.venv/bin/python
make test PYTHON=.venv/bin/python
```

Run the three stages together with:

```bash
make sprint2-final-check PYTHON=.venv/bin/python
```

## Confidentiality

Original Excel sources, processed extracts, SQLite databases, generated CSV
results, checksums and the supplied project PDF are confidential. The public
package contains code, tests, schema, configuration templates and approved
Markdown documentation only.
