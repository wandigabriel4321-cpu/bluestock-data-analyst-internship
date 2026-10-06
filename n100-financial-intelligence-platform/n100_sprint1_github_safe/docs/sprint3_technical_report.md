# Sprint 3 Technical Report — Screener & Peer Comparison Engine

**Project:** N100 Financial Intelligence Platform  
**Sprint period:** Days 15–21  
**Final validation:** 6 October 2026, prepared ahead of the Day 21 schedule  
**Technical status:** Complete and reproducible  
**Release status:** Ready with two documented preset-count exceptions

## 1. Executive summary

Sprint 3 converts the financial-ratio foundation from Sprint 2 into a usable
screening and peer-comparison layer. The implementation provides a configurable
15-metric filter engine, six official screeners, a new composite-quality score,
peer percentiles, 92 radar charts and two formatted Excel reports.

The final regression suite contains 256 passing tests and zero failures. SQLite
passes both `PRAGMA foreign_key_check` and `PRAGMA integrity_check`. All 92
companies are represented in `financial_ratios`; 56 are mapped to the 11
official peer groups and 36 use the documented Nifty 100 comparison fallback.

## 2. Architecture

### Screener layer

- `src/screener/engine.py` loads the latest substantive company metrics and
  applies multiple YAML-configured filters.
- `config/screener_config.yaml` defines the 15 filterable metrics and six
  immutable official presets.
- `src/screener/presets.py` evaluates strict preset rules, diagnostics and
  manual evidence.
- `src/screener/composite_score.py` computes the separate Sprint 3 global and
  sector-relative scores.
- `src/screener/excel_report.py` generates the six-sheet screener workbook.

### Peer layer

- `src/analytics/peer.py` loads official group membership and computes ten
  metric percentiles by group and reporting year.
- `src/analytics/radar.py` generates comparable 0–100 radar profiles.
- `src/analytics/peer_report.py` generates the 11-sheet peer workbook.
- `src/analytics/sprint3_review.py` executes the integrated Day 21 validation.

## 3. Day-by-day delivery

### Day 15 — Filter Engine Core

- Implemented the YAML-driven engine and 15 supported metrics.
- Selected the latest substantive value without replacing nulls with zero.
- Treated `Debt Free` ICR as infinite for minimum-ICR filtering.
- Exempted Financials only from the common maximum D/E rule.

### Day 16 — Six preset screeners

- Implemented Quality Compounder, Value Pick, Growth Accelerator, Dividend
  Champion, Debt-Free Blue Chip and Turnaround Watch.
- Preserved strict official operators and thresholds.
- Generated count, missing-value, sequential-rule and manual-check evidence.

### Day 17 — Composite score and screener Excel

- Implemented the official 35% Profitability, 30% Cash Quality, 20% Growth and
  15% Leverage formula.
- Applied P10/P90 winsorisation and 0–100 scaling.
- Kept the Sprint 2 score in a separate legacy column.
- Generated `output/screener_output.xlsx` with exactly six non-empty sheets.

### Day 18 — Peer percentile rankings

- Added `peer_group_assignments` and `peer_percentiles` to SQLite.
- Preserved 56 assignments, 11 groups and 11 official benchmarks.
- Generated 7,060 metric rows: 5,589 ranked values and 1,471 retained nulls.
- Inverted the D/E percentile so lower leverage is better.

### Day 19 — Radar charts

- Generated 92 unique, non-empty PNG charts.
- Compared 56 companies with their peer-group average.
- Compared 36 unassigned companies with the Nifty 100 average.
- Used eight consistently scaled axes and documented nine render-only
  missing-axis fallbacks affecting six companies.

### Day 20 — Peer comparison Excel

- Generated `output/peer_comparison.xlsx` with exactly 11 sheets.
- Used 20 raw KPIs plus the ten officially classified percentiles.
- Added one gold benchmark row and one final median row per group.
- Applied green/yellow/red percentile bands, filters and frozen panes.

### Day 21 — Final validation

- Added 35 integrated quality tests.
- Executed 256 total tests with zero failures.
- Verified the database, top-five Quality Compounder results, D/E inversion,
  IT Services, FMCG, all 17 Excel sheets and a representative radar sample.

## 4. Data-quality and edge-case decisions

- Null values remain null and are excluded only where the relevant calculation
  requires an available observation.
- D/E is inverted only for peer ranking and score normalisation; the raw ratio
  is preserved.
- Financial-company D/E exemption applies to the common maximum-D/E screen,
  not to the exact-zero Debt-Free Blue Chip rule.
- Missing radar axes are not written back to the database. They use the
  reference average only for polygon rendering and are disclosed in the chart.
- Official thresholds were not changed to force result counts into a desired
  range.

## 5. Verified production counts

| Item | Verified result |
|---|---:|
| Companies | 92 |
| `financial_ratios` rows | 1,155 |
| Companies in `financial_ratios` | 92 |
| Peer assignments | 56 |
| Companies without peer group | 36 |
| Peer groups | 11 |
| Official benchmarks | 11 |
| Peer percentile rows | 7,060 |
| Radar charts | 92 |
| Screener workbook sheets | 6 |
| Peer workbook sheets | 11 |
| Final tests | 256 PASS |

## 6. Known preset-count exceptions

Four presets produce between 5 and 50 companies. Two remain below the expected
interval under the official rules:

- **Value Pick:** 2 companies. P/E below 20 leaves 15 companies; combining it
  with P/B below 3 reduces the result to 2. Missing values are not the cause.
- **Debt-Free Blue Chip:** 2 companies. Only three companies have exact D/E
  equal to zero; JIOFIN fails ROE above 12%, leaving LICI and SBILIFE.

This is a data-driven outcome, not a filter defect. The exceptions are retained
in `preset_validation_report.csv` and the final validation report.

## 7. Reproduction

```bash
make day21-check PYTHON=python
```

Individual commands are documented in `README.md`. The final review outputs are
stored under `output/sprint3_*`, and the public package excludes all source data,
SQLite databases, backups and generated confidential outputs.

