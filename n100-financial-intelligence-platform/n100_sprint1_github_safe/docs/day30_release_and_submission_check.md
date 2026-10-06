# Day 15 — Release and Submission Check

**Execution date:** 30 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** Final technical verification before GitHub, Google Drive and Workspace submission

## Release decision

The Sprint 2 technical package is approved for submission. No unexpected
failure was found during the final rerun.

| Check | Requirement | Verified result | Status |
|---|---:|---:|---|
| `financial_ratios` rows | At least 1,100 | 1,155 | PASS |
| Distinct companies | 92 | 92 | PASS |
| Completely empty mandatory columns | 0 | 0 | PASS |
| Foreign-key violations | 0 | 0 | PASS |
| SQLite integrity | `ok` | `ok` | PASS |
| Dedicated formula tests | At least 20 | 60 | PASS |
| Complete automated suite | Zero failures | 140 passed, 0 failed | PASS |
| Edge cases without explanation | 0 | 0 of 6,993 | PASS |
| Manual checks below 0.1 pp | At least 3 | 5 | PASS |
| Five-company checks within 2 pp | 5 | 5 | PASS |
| Screener companies | 15–50 | 38 | PASS |
| Cash-flow sign combinations | 8 | 8 | PASS |
| Blank capital-allocation labels | 0 | 0 | PASS |
| Confidential files in public ZIP | 0 | 0 | PASS |

## Mandatory-column coverage

| Column | Non-null rows |
|---|---:|
| `net_profit_margin_pct` | 1,072 |
| `operating_profit_margin_pct` | 1,060 |
| `return_on_equity_pct` | 1,058 |
| `debt_to_equity` | 1,140 |
| `interest_coverage` | 1,030 |
| `asset_turnover` | 1,057 |
| `free_cash_flow_cr` | 1,054 |
| `capex_cr` | 1,054 |
| `earnings_per_share` | 1,069 |
| `book_value_per_share` | 1,127 |
| `dividend_payout_ratio_pct` | 1,069 |
| `total_debt_cr` | 1,140 |
| `cash_from_operations_cr` | 1,054 |
| `revenue_cagr_5yr` | 600 |
| `pat_cagr_5yr` | 537 |
| `eps_cagr_5yr` | 532 |
| `composite_quality_score` | 1,030 |

Missing values remain only in documented row-level cases. No required column
is completely empty.

## Capital-allocation verification

`output/capital_allocation.csv` contains 1,054 eligible company-year rows,
all eight CFO/CFI/CFF sign combinations and zero blank `pattern_label` values.
There are nine displayed labels because the `(+,-,-)` combination is separated
into `Reinvestor` and `Shareholder Returns` using the CFO/PAT quality rule.

## Public-package confidentiality check

The GitHub-safe ZIP was inspected after reconstruction. It contains no source
Excel workbooks, SQLite databases, generated output files, source checksum,
supplied project PDF or local environment file. Confidential sources and
results remain only in the Google Drive package.

## Remaining manual actions

The account owner must now:

1. upload the GitHub-safe ZIP contents to the existing repository;
2. confirm the public repository contains no confidential files;
3. copy the GitHub folder URL into `GITHUB_LINK.txt`;
4. upload the consolidated submission folder to Google Drive;
5. set access to **Anyone with the link — Viewer**;
6. test GitHub and Google Drive in an incognito window;
7. paste the updated Note to Admin and Drive link into the Workspace;
8. submit several hours before the deadline;
9. send the final standup.
