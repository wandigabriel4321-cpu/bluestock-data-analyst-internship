# Official ETL data-quality rules

These definitions come from Section 14 of the official project specification.

| Rule | Name | Condition | Severity | Required action |
|---|---|---|---|---|
| DQ-01 | Company PK uniqueness | `companies.id` is unique | CRITICAL | Halt the load and investigate duplicate tickers. |
| DQ-02 | Annual PK uniqueness | No duplicate `(company_id, year)` in P&L, balance sheet or cash flow | CRITICAL | Keep the last occurrence and log every duplicate. |
| DQ-03 | FK integrity | Every child `company_id` exists in `companies.id` | CRITICAL | Reject orphan rows and log them. |
| DQ-04 | Balance-sheet balance | `abs(total_assets-total_liabilities)/total_assets < 0.01` | WARNING | Flag for analyst review; do not reject. |
| DQ-05 | OPM cross-check | Difference between source OPM and computed OPM is below 1 percentage point | WARNING | Keep the source; use computed OPM in the Ratio Engine and log the difference. |
| DQ-06 | Positive sales | Sales are positive for non-bank companies | WARNING | Flag non-positive sales and exclude them from CAGR. |
| DQ-07 | Year format | Normalised years match `^\\d{4}-\\d{2}$` | CRITICAL | Reject unparseable rows and log the raw value. |
| DQ-08 | Ticker format | Uppercase, trimmed ticker with 2–12 characters | CRITICAL | Normalise silently; reject invalid lengths or missing tickers. |
| DQ-09 | Net-cash check | Difference from CFO + CFI + CFF is at most ₹10 crore | WARNING | Flag the row and compute net cash from its components. |
| DQ-10 | Non-negative fixed assets | `fixed_assets >= 0` | WARNING | Coerce negatives to zero and log the correction. |
| DQ-11 | Tax-rate range | `0 <= tax_percentage <= 60` | WARNING | Flag values outside the range for analyst review. |
| DQ-12 | Dividend-payout cap | `dividend_payout <= 200` | WARNING | Flag values above 200% for confirmation. |
| DQ-13 | Annual-report URL validity | HTTP HEAD returns status 200 | WARNING | Log inaccessible URLs; do not reject because link decay is expected. |
| DQ-14 | EPS sign consistency | EPS is positive when net profit is positive | WARNING | Flag mismatches and retain the source value for review. |
| DQ-15 | Strict balance counter | `total_assets == total_liabilities` after DQ-04 | INFO | Record the count in the load audit only. |
| DQ-16 | Coverage check | Each company has at least five years of P&L, balance-sheet and cash-flow records | WARNING | Flag limited histories; exclude companies with fewer than three years from CAGR. |

## Year normalisation

The official output is `YYYY-MM`.

| Raw value | Output |
|---|---|
| `Mar-23`, `Mar 23`, `March-2023` | `2023-03` |
| `2023`, `FY23` | `2023-03` |
| `Dec-22` | `2022-12` |
| `Jun-23` | `2023-06` |
| `2023-03` | `2023-03` |
| Unsupported text, `TTM`, decimal period | `PARSE_ERROR` |
