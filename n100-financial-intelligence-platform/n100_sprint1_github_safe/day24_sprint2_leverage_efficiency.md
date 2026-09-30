# Day 09 — Leverage and Efficiency

Date: 24 September 2026

## Scope completed

The leverage and efficiency layer was added to `src/analytics/ratios.py` with the following calculations and controls:

- Debt-to-Equity: `borrowings / (equity_capital + reserves)`;
- debt-free companies return `0.0` for Debt-to-Equity;
- `high_leverage_flag` is raised only when Debt-to-Equity is greater than `5.0`;
- the high-leverage warning is suppressed dynamically when `broad_sector` is `Financials`;
- Interest Coverage Ratio: `(operating_profit + other_income) / interest`;
- zero interest returns no numeric ICR;
- `icr_label = "Debt Free"` is assigned when both interest and borrowings are zero;
- `icr_warning_flag` is raised when the available ICR is below `1.5`;
- Net Debt: `borrowings - investments`;
- Asset Turnover: `sales / total_assets`;
- missing values and invalid denominators return `None` instead of causing calculation errors.

Thresholds are parameters with documented defaults. The implementation does not contain a fixed number or a fixed list of financial companies. Sector treatment is decided from each company's `broad_sector` value.

## Technical decisions

1. A company with zero borrowings has Debt-to-Equity equal to zero, even when its equity denominator is zero.
2. A company with borrowings but missing or non-positive equity plus reserves receives no valid Debt-to-Equity result.
3. Zero interest alone is not sufficient to label a company debt-free when borrowings are known and positive.
4. A value exactly equal to the threshold is not flagged: high leverage requires `D/E > 5`, and ICR risk requires `ICR < 1.5`.
5. Financial-sector suppression uses normalized, case-insensitive comparison of `broad_sector`; it is not based on company names, IDs, or counts.
6. Asset Turnover is unavailable when total assets are missing, zero, or negative.

## Tests

`tests/kpi/test_leverage.py` contains 16 tests covering:

- normal and debt-free Debt-to-Equity;
- invalid equity denominators;
- high-leverage threshold and boundary behavior;
- dynamic Financials-sector suppression;
- normal, debt-free, and low Interest Coverage scenarios;
- prevention of a false debt-free label when borrowings remain positive;
- positive and negative Net Debt;
- missing Net Debt inputs;
- normal and invalid Asset Turnover denominators;
- invalid configurable thresholds.

Verification result:

- new Day 09 tests: **16 passed**;
- complete project regression suite: **78 passed, 0 failed**.

## Data audit

The new calculations were exercised against the populated Sprint 1 SQLite database and written to the confidential generated output `output/leverage_efficiency_day09.csv`.

| Audit measure | Result |
|---|---:|
| Balance-sheet rows evaluated | 1,140 |
| Companies with eligible balance-sheet data | 91 |
| Eligible Financials companies identified dynamically | 22 |
| Debt-free annual labels | 21 |
| Raw annual D/E values above 5 | 165 |
| Financials-sector warnings suppressed | 146 |
| Final high-leverage warnings | 19 |
| ICR warnings below 1.5 | 105 |
| Invalid Debt-to-Equity results | 0 |
| Unavailable Asset Turnover results | 83 |

The sector master contains 23 Financials companies. The audit reports 22 because it evaluates only companies with eligible balance-sheet rows; the difference is data availability, not a hard-coded carve-out. The Sprint 1 audit already records the company without validated balance-sheet coverage.

## Outcome

Day 09 is complete. Leverage and efficiency metrics are implemented, edge cases are explicit, sector suppression is data-driven, and all previous tests remain green.
