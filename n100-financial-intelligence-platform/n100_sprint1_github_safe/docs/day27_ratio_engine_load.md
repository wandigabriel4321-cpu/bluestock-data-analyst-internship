# Day 12 — Financial Ratio Engine Database Population

**Execution date:** 27 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** complete company-year KPI calculation, SQLite publication and audit

## Outcome

Day 12 is complete. `src/analytics/ratio_engine.py` now orchestrates the
profitability, leverage, CAGR and cash-flow modules, calculates one row per
authoritative company-year key and atomically populates `financial_ratios`.

| Exit check | Expected | Actual | Result |
|---|---:|---:|---|
| `COUNT(*)` | at least 1,100 | **1,155** | PASS |
| `COUNT(DISTINCT company_id)` | 92 | **92** | PASS |
| Duplicate `(company_id, year)` keys | 0 | **0** | PASS |
| Required columns entirely null | 0 | **0** | PASS |
| Foreign-key violations | 0 | **0** | PASS |
| SQLite integrity | `ok` | **`ok`** | PASS |

The pre-task forecast of approximately 1,155 rows was therefore exact.

## Authoritative company-year universe

The engine uses SQL `UNION`, not a single source table and not the
pre-computed workbook, to preserve every validated annual key found in P&L,
Balance Sheet or Cash Flow.

| Source presence | Rows |
|---|---:|
| P&L + Balance Sheet + Cash Flow | 1,044 |
| P&L + Balance Sheet | 14 |
| P&L + Cash Flow | 12 |
| P&L only | 3 |
| Balance Sheet only | 82 |
| **Total union** | **1,155** |

This design explains legitimate row-level nulls: an annual Balance Sheet-only
key cannot receive a P&L margin, while a missing or invalid denominator also
retains `None` under its documented business rule.

## Calculations and loading decisions

- OPM is calculated from `operating_profit / sales * 100`; the source OPM is
  retained separately for the greater-than-one-percentage-point audit.
- EBIT for ROCE is `operating_profit - depreciation`, as specified in the
  source data dictionary.
- Book Value Per Share follows
  `(equity_capital + reserves) / (equity_capital / face_value)`.
- Five-year CAGR values require exact matching annual endpoints; their flags
  remain separate from numeric values.
- The composite quality score uses the documented weights: 30% ROE, 25% FCF,
  25% ROCE and 20% D/E. Components are P10/P90 winsorised to 0–100 and D/E is
  inverted so lower leverage scores higher.
- Composite scores remain `None` when any required component is unavailable.
- The load is idempotent: the table is replaced in a single SQLite transaction
  and repeated execution does not duplicate rows.

The Financials flag is derived from `sectors.broad_sector`; no fixed ticker
list or fixed company count is embedded in the code. The current data contains
23 Financials companies and 272 Financials company-year rows.

## Required-column coverage

All explicitly required fields contain valid data. `None` is preserved only
where a source row or permitted denominator is unavailable.

| KPI | Non-null rows |
|---|---:|
| Net Profit Margin | 1,072 |
| Operating Profit Margin | 1,060 |
| ROE | 1,058 |
| Debt-to-Equity | 1,140 |
| Interest Coverage | 1,030 |
| Asset Turnover | 1,057 |
| Free Cash Flow | 1,054 |
| CapEx | 1,054 |
| EPS | 1,069 |
| Book Value Per Share | 1,127 |
| Dividend Payout Ratio | 1,069 |
| Total Debt | 1,140 |
| Cash from Operations | 1,054 |
| Revenue CAGR — 5 years | 600 |
| PAT CAGR — 5 years | 537 |
| EPS CAGR — 5 years | 532 |
| Composite Quality Score | 1,030 |

Complete per-column evidence is in
`output/financial_ratios_null_audit.csv`.

## Comparison with `financial_ratios.xlsx`

The official workbook contains 1,184 rows, 92 companies and 1,065 unique
normalised company-year keys. It also contains 83 duplicated keys, so the
comparison does not choose an arbitrary duplicate. For each key and KPI, the
engine value is compared with the closest distinct reference candidate using
`rel_tol=0.001` and `abs_tol=0.05`.

| Comparison measure | Result |
|---|---:|
| Engine/reference overlapping keys | 1,041 |
| Engine keys absent from reference | 114 |
| Reference keys absent from engine union | 24 |
| Metric comparisons marked `MATCH` | 11,476 |
| Both null/unavailable | 1,019 |
| Engine null while reference is present | 12 |
| Reference null/key absent | 535 |
| Comparisons marked `DIFFERENT` | 1,973 |

Eleven of the thirteen comparable KPI fields have no conflicting values at
all where both sides are available. The 1,973 differences are fully explained
by two documented formula choices:

1. **Operating Profit Margin — 944 differences.** The workbook stores the
   supplied `opm_percentage`, while Day 12 must use the calculated
   `operating_profit / sales * 100`. The 216 differences above one percentage
   point remain explicitly flagged by the engine.
2. **Book Value Per Share — 1,029 differences.** The workbook uses a different
   share/unit scale that varies with face value. The engine follows the exact
   formula printed in the project document and retains the reference result
   only for audit comparison.

No workbook value overwrites a value derived from validated Sprint 1 sources.
The complete long-form comparison is stored in
`output/financial_ratios_reference_comparison.csv`; its summary is stored in
`output/financial_ratios_comparison_summary.json`.

## Edge-case audit

`output/ratio_edge_cases.log` records every permitted exceptional result:

| Category | Entries |
|---|---:|
| CAGR special/insufficient-history flags | 6,113 |
| Permitted null denominator/source cases | 625 |
| OPM mismatches above one percentage point | 216 |
| Debt-free Interest Coverage labels | 21 |

## Reproduction

```bash
make ratio-engine PYTHON=.venv/bin/python
make test-ratio-engine PYTHON=.venv/bin/python
make test PYTHON=.venv/bin/python
```

Generated Day 12 evidence:

- `output/ratio_engine_load_audit.csv`;
- `output/financial_ratios_null_audit.csv`;
- `output/financial_ratios_reference_comparison.csv`;
- `output/financial_ratios_comparison_summary.json`;
- `output/ratio_edge_cases.log`.

## Automated verification

Ten new Day 12 tests cover the union grain, Book Value Per Share, P10/P90
composite score, required-column exit gate, integrated metric calculation,
idempotent publication and null-audit output.

- Day 12 tests: **10 passed, 0 failed**;
- complete regression suite: **120 passed, 0 failed**.

