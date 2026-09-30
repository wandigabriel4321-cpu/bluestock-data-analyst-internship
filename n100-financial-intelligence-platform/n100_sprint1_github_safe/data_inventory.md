# N100 source-data inventory

## Package status

The official package contains 12 Excel workbooks and one project-specification
PDF. All 13 files were received and inspected. The original workbooks remain
unchanged.

## Core datasets

Core workbooks use row 1 as metadata and row 2 as the real header
(`pandas.read_excel(..., header=1)`).

| Source | Worksheet | Rows | Columns | Company codes |
|---|---|---:|---:|---:|
| `companies.xlsx` | Companies | 92 | 12 | 92 |
| `profitandloss.xlsx` | Profit & Loss | 1,276 | 15 | 100 |
| `balancesheet.xlsx` | Balance Sheet | 1,312 | 13 | 98 |
| `cashflow.xlsx` | Cash Flow | 1,187 | 7 | 100 |
| `analysis.xlsx` | Analysis | 20 | 6 | 5 |
| `documents.xlsx` | Documents | 1,585 | 4 | 99 |
| `prosandcons.xlsx` | Pros & Cons | 16 | 4 | 5 |

## Supplementary datasets

Supplementary workbooks use their first row as the header
(`pandas.read_excel(..., header=0)`).

| Source | Worksheet | Rows | Columns | Coverage |
|---|---|---:|---:|---|
| `sectors.xlsx` | Sheet1 | 92 | 6 | 92 companies |
| `stock_prices.xlsx` | Sheet1 | 5,520 | 9 | 92 companies × 60 months |
| `market_cap.xlsx` | Sheet1 | 552 | 9 | 92 companies × 6 years |
| `financial_ratios.xlsx` | Sheet1 | 1,184 | 16 | 92 company codes |
| `peer_groups.xlsx` | Sheet1 | 56 | 4 | 11 groups; 56 members |

## Confirmed table decision

Sprint 1 loads ten SQLite tables:

1. `companies`
2. `profitandloss`
3. `balancesheet`
4. `cashflow`
5. `analysis`
6. `documents`
7. `prosandcons`
8. `sectors`
9. `market_cap`
10. `stock_prices`

`financial_ratios.xlsx` is the reference table for Sprint 2 and
`peer_groups.xlsx` is the reference membership file for Sprint 3. They are
read and validated during the full 12-file audit, but they are not two of the
ten initial Sprint 1 SQLite tables.

## Initial data-quality findings

- Every workbook-level `id` column is unique.
- `companies`, `sectors`, `market_cap` and `stock_prices` agree on the
  same 92-company universe.
- Nine non-master ticker values occur in core child data:
  `AGTL`, `ULTRACEMCO`, `UNIONBANK`, `UNITDSPR`, `VBL`, `VEDL`,
  `WIPRO`, `ZOMATO` and `ZYDUSLIFE`.
- The orphan values affect 414 child rows before rejection.
- Official year normalisation creates duplicate natural keys: 12 P&L rows,
  87 balance-sheet rows and 35 cash-flow rows must be deduplicated and logged.
- Year parsing rejects 100 `TTM` P&L rows and five decimal
  `2024.5` balance-sheet rows.
- All balance-sheet rows satisfy both the 1% tolerance and strict equality.
- One cash-flow row differs from CFO + CFI + CFF by more than ₹10 crore.
- `financial_ratios.xlsx` contains 119 duplicate
  `(company_id, year)` rows and does not match the 92-company master exactly;
  it must be treated as a cross-check, not the authoritative Sprint 1 load.
- Every peer group has exactly one benchmark. All 56 peer-membership tickers
  exist in the company master.

## Confidentiality

The project document classifies the material as confidential and for internal
use only. Raw and supplementary workbooks are excluded from Git and must not
be uploaded to a public repository.
