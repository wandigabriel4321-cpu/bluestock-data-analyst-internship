# Day 08 — Sprint 2 Profitability Foundation

**Execution date:** 23 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** Profitability ratios and the initial `financial_ratios` schema

## Baseline protection and verification

Before any Sprint 2 change, `db/nifty100.db` was copied to
`db/backups/nifty100_sprint1_final_20260922.db`. Both files produced the same
SHA-256 checksum:

```text
a1c2edeb5ac65b436b2e8d36232d72a1cb16038663ab194e3227f41463967069
```

The official Sprint 1 `unittest` command completed with 49 passing tests and
zero failures. The final Sprint 1 validation evidence continues to report zero
CRITICAL failures and zero SQLite foreign-key violations.

## Day 08 implementation

`src/analytics/ratios.py` implements five profitability metrics:

| Metric | Formula | Invalid-denominator action |
|---|---|---|
| Net Profit Margin | `net_profit / sales * 100` | `None` when sales is zero or unavailable |
| Operating Profit Margin | `operating_profit / sales * 100` | `None` when sales is zero or unavailable |
| Return on Equity | `net_profit / (equity_capital + reserves) * 100` | `None` when equity plus reserves is non-positive |
| Return on Capital Employed | `EBIT / (equity_capital + reserves + borrowings) * 100` | `None` when capital employed is non-positive |
| Return on Assets | `net_profit / total_assets * 100` | `None` when assets are zero or unavailable |

The module also provides:

- `safe_divide()` as the shared division guard;
- `cross_check_operating_profit_margin()` with a strict difference threshold
  greater than one percentage point;
- `write_opm_mismatch_log()` for auditable CSV evidence;
- `is_financial_sector()` for the later sector-relative ROCE and leverage rules.

Calculations retain full precision. Rounding is deferred to exports and display
layers to prevent accumulated calculation error.

## Schema decision

`db/schema.sql` now creates `financial_ratios` as the eleventh database table.
The table uses a unique `(company_id, year)` business key, a foreign key to
`companies(id)`, official `YYYY-MM` reporting periods and constrained Boolean
flags. Nullable KPI cells are intentional because the specification requires
`None` for documented edge cases such as zero sales or non-positive equity.

The schema includes the explicitly named downstream Sprint 2 fields so the
following days can populate the table without destructive migrations.

## Financial-sector decision

Financial-sector membership will be determined from the `sectors.broad_sector`
value instead of a hard-coded company list or company count. The current
validated database contains 23 companies whose broad sector is `Financials`;
the task text's reference to 19 will be recorded as a source-version
difference and reviewed during Day 13.

## Test scope

Day 08 tests cover normal profitability calculations, zero denominators,
non-positive equity, the strict OPM mismatch boundary, mismatch CSV logging,
ROCE and Financials-sector identification. The full suite is rerun after the
implementation so the Sprint 1 regression baseline remains protected.

## Final verification

| Check | Result |
|---|---:|
| Sprint 1 baseline before changes | 49 passed, 0 failed |
| New Day 08 profitability tests | 12 passed, 0 failed |
| Complete suite after changes | 62 passed, 0 failed |
| SQLite tables after schema extension | 11 |
| `financial_ratios` schema columns | 50 |
| Foreign-key violations | 0 |
| SQLite integrity check | `ok` |
| Final Sprint 1 CRITICAL failures | 0 |

The Day 08 OPM audit evaluated all 1,073 validated `profitandloss` rows and
recorded 216 differences greater than one percentage point in
`output/opm_mismatches_day08.csv`. The file is retained as confidential output
because it contains company-level results. Large differences for some
Financials records are treated as source anomalies for later categorisation,
not silently overwritten values.

The `financial_ratios` table is intentionally empty at the end of Day 08. Its
population is a Day 12 deliverable after the leverage, CAGR and cash-flow
modules are implemented.
