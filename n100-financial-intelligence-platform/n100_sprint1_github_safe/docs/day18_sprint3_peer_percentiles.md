# Sprint 3 Day 18 — Peer Percentile Rankings

Date: 4 October 2026  
Recovery execution: 6 October 2026  
Status: Complete

## Scope completed

- Added `peer_group_assignments` to SQLite.
- Added `peer_percentiles` to SQLite.
- Loaded the 56 official company-to-group assignments from
  `data/supporting/peer_groups.xlsx`.
- Preserved the one official `is_benchmark` designation in each of the 11
  peer groups.
- Calculated ten metric rankings for every available assigned company-year.
- Preserved source nulls and excluded them only from their metric-level
  distribution.
- Inverted the Debt-to-Equity rank so lower leverage is better.
- Implemented a non-error fallback for the 36 companies without an official
  peer group.
- Generated four CSV evidence files and 57 reproducible manual checks.

## SQLite schema

`peer_group_assignments` has one row per officially assigned company:

- `company_id` — primary key and foreign key to `companies.id`;
- `peer_group_name` — official group label;
- `is_benchmark` — constrained to 0 or 1.

`peer_percentiles` uses the composite primary key
`(company_id, peer_group_name, metric, year)` and stores:

- `company_id`;
- `peer_group_name`;
- `metric`;
- `value`;
- `percentile_rank`;
- `year`.

The composite foreign key requires every percentile row to match an official
assignment. Percentile values are constrained to the inclusive range 0–100.

## Metrics

1. Return on Equity;
2. Return on Capital Employed;
3. Net Profit Margin;
4. Debt-to-Equity;
5. Free Cash Flow;
6. PAT CAGR 5yr;
7. Revenue CAGR 5yr;
8. EPS CAGR 5yr;
9. Interest Coverage;
10. Asset Turnover.

The stored metric keys are the corresponding `financial_ratios` column names,
which avoids a second translation layer in later reports.

## Ranking method

For each `(peer_group_name, year, metric)` distribution:

1. coerce the selected metric to a finite numeric value;
2. retain missing/non-finite observations as null;
3. rank only available values using SQL-style `RANK()` tie handling;
4. compute `(rank - 1) / (n - 1) × 100`;
5. assign 100 to the only available observation in a singleton distribution;
6. calculate `100 - percentile_rank` for Debt-to-Equity.

Tied values receive the same rank. Missing values receive neither a fabricated
zero nor a percentile.

## Verified results

| Check | Result |
|---|---:|
| Companies in SQLite | 92 |
| Official assignments | 56 |
| Companies without official group | 36 |
| Peer groups | 11 |
| Official benchmarks | 11 |
| Assigned company-year rows | 706 |
| Metrics per company-year | 10 |
| `peer_percentiles` rows | 7,060 |
| Ranked values | 5,589 |
| Missing values retained | 1,471 |
| Duplicate composite keys | 0 |
| Foreign-key violations | 0 |
| SQLite integrity check | ok |
| Manual checks | 57/57 PASS |
| New Day 18 tests | 12/12 PASS |
| Complete regression suite | 196/196 PASS |

## Required manual checks

The latest available year is selected independently for each metric, because
the interim 2024-09 records contain leverage data but not all profitability
metrics.

| Group | Check | Year | Verified company |
|---|---|---:|---|
| IT Services | Highest ROE | 2024-03 | TCS |
| IT Services | Lowest D/E | 2024-09 | TECHM |
| FMCG | Highest ROE | 2024-03 | NESTLEIND |
| FMCG | Lowest D/E | 2024-09 | ITC |

The manual-check file also confirms every official benchmark, both requested
focus groups, all ten metrics in each focus group and ROE/D/E extrema across
all 11 groups.

## Companies without peer group

The 36 companies absent from the official source are not assigned to invented
groups. Calling `peer_group_for_company()` for any of them returns exactly:

`No peer group assigned`

No exception is raised and no percentile row is fabricated.

## Outputs

- `output/peer_group_assignments.csv` — official memberships and benchmarks;
- `output/peer_percentiles.csv` — complete long-form ranking output;
- `output/peer_group_audit.csv` — group-level counts and null coverage;
- `output/peer_percentile_manual_checks.csv` — 57 reproducible checks;
- `output/day18_test_results.txt` — focused and complete test evidence.

## Reproduction

```bash
python -m src.analytics.peer \
  --database db/nifty100.db \
  --schema db/schema.sql \
  --peer-groups data/supporting/peer_groups.xlsx \
  --output-dir output

python -m unittest tests.analytics.test_peer -v
python -m unittest discover -s tests -p "test_*.py" -v
```

A timestamped database backup is created in `db/backups/` before the Day 18
tables are replaced.
