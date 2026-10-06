# Sprint 3 — Day 15 Filter Engine Core

**Execution date:** 1 October 2026  
**Rebuilt and revalidated:** 6 October 2026  
**Status:** PASS

## Scope completed

- Created `src/screener/__init__.py` and `src/screener/engine.py`.
- Created the analyst-editable `config/screener_config.yaml`.
- Created `tests/screener/test_engine.py` with 15 focused tests.
- Created a pre-Sprint-3 backup at
  `db/backups/nifty100_pre_sprint3_day15_20261001.db`.
- Added `screener`, `test-screener` and `day15-check` Makefile targets.
- Generated `output/day15_custom_screener.csv` from the real database.

## Supported filters

The engine supports all 15 required metrics:

1. ROE minimum;
2. Debt-to-Equity maximum;
3. Free Cash Flow minimum;
4. Revenue CAGR 5yr minimum;
5. PAT CAGR 5yr minimum;
6. Operating Profit Margin minimum;
7. P/E maximum;
8. P/B maximum;
9. Dividend Yield minimum;
10. Interest Coverage minimum;
11. Market Capitalisation minimum;
12. Net Profit minimum;
13. EPS CAGR 5yr minimum;
14. Asset Turnover minimum;
15. Sales minimum.

Multiple filters are combined with logical AND. Results are sorted by
`composite_quality_score` descending and then by `company_id` for deterministic
ties.

## Snapshot and period policy

The engine combines `financial_ratios`, `market_cap`, `profitandloss`,
`companies` and `sectors` into one row per company. It selects the latest
substantive financial-ratio row rather than allowing a balance-sheet-only
interim period to replace a row with operating, cash-flow, growth and efficiency
metrics. Market-cap and P&L records use their own latest available periods.

This decision was necessary because 83 companies have a September 2024 interim
ratio row containing D/E but almost none of the other screener KPIs. The final
snapshot uses March 2024 for 91 companies and September 2024 for one company,
while still preserving the latest valid source period per table.

## Missing-value and business-rule policy

- Missing values remain null and are never converted to zero.
- A missing value fails only a filter that explicitly requires that metric.
- Real zero values remain valid numeric values.
- Companies whose `broad_sector` is `Financials` are exempt from the ordinary
  maximum D/E condition.
- `icr_label = "Debt Free"` is treated as infinite Interest Coverage and passes
  any minimum ICR threshold.
- Unknown metric names, invalid YAML, unsupported columns and non-finite or
  non-numeric thresholds raise explicit configuration errors.

## Real-data validation

| Check | Result |
| --- | ---: |
| Companies in current snapshot | 92 |
| Unique company IDs | 92 |
| Duplicate company rows | 0 |
| Financial-ratio rows preserved in SQLite | 1,155 |
| SQLite foreign-key violations | 0 |
| SQLite integrity check | `ok` |
| Default export rows | 92 |
| Default export size | 27,481 bytes |

Representative combined-filter checks were also executed:

- ROE >= 15 and D/E <= 1 returned 49 companies, including the documented
  Financials-sector exemption.
- FCF >= 0 and Revenue CAGR 5yr >= 10 returned 38 companies.
- An ICR minimum of 1,000 returned two companies through valid numeric or
  Debt-Free handling.

The official preset inequalities and preset-level count gates belong to Day 16;
they were not substituted into the Day 15 configuration.

## Automated tests

- Existing Sprint 1 and Sprint 2 tests: 140 passed.
- New Day 15 screener tests: 15 passed.
- Complete suite: **155 passed, 0 failures**.

The focused tests cover configuration loading, all metric definitions, unknown
metrics, invalid thresholds, invalid YAML, latest-period selection, simultaneous
filters, deterministic sorting, missing values, zero values, Debt-Free ICR and
the Financials D/E exemption.

## Execution

```bash
make screener PYTHON=python3
make test-screener PYTHON=python3
make day15-check PYTHON=python3
```

The Day 15 exit criteria are satisfied.
