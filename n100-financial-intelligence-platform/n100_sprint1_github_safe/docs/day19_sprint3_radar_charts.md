# Sprint 3 Day 19 — Radar Charts

Date: 5 October 2026  
Recovery execution: 6 October 2026  
Status: Complete

## Scope completed

- Created `src/analytics/radar.py`.
- Generated one radar chart for each of the 92 Nifty 100 companies available
  in the project database.
- Compared 56 companies with the average of their official peer group.
- Compared 36 companies without a group with the Nifty 100 average.
- Used eight consistently scaled axes from 0 to 100.
- Inverted Debt-to-Equity so higher scores consistently represent a better
  result.
- Added titles, filled company polygons, dashed benchmark outlines, legends,
  readable fonts and explanatory footers.
- Validated all files automatically and visually reviewed both comparison
  categories, including missing-value examples.

## Radar axes

1. ROE;
2. ROCE;
3. Net Profit Margin;
4. Debt-to-Equity, inverted;
5. Free Cash Flow Score;
6. PAT CAGR 5yr;
7. Revenue CAGR 5yr;
8. Sprint 3 Composite Score.

Raw units are not placed directly on the same radar. Each metric is converted
to a percentile score from 0 to 100. For D/E, the percentile is inverted so a
lower leverage ratio produces a higher plot score.

## Comparison logic

### Companies with an official peer group

The company score is calculated inside its assigned group. The dashed line is
the mean of the available percentile scores for all companies in that group.
This applies to 56 companies across 11 official peer groups.

### Companies without an official peer group

No artificial group is created. The company is scored against all 92 companies
and the dashed line is the Nifty 100 average. The title explicitly states:

`No peer group assigned — benchmark: Nifty 100`

This applies to 36 companies.

## Latest-value policy

Each source metric uses the latest available non-null company value. This is
necessary because the supplied interim reporting periods do not contain every
metric. The year used for every source field remains available during profile
construction, while the chart shows the resulting comparable percentile.

The Composite Score is the separate Sprint 3 score created on Day 17; the
legacy Sprint 2 score is not substituted.

## Missing values

Missing source values are never replaced in the financial database or audit.
To keep every eight-axis polygon renderable, the PNG alone places a missing
axis at the relevant peer-group or Nifty 100 reference average. The affected
axis is recorded in `radar_chart_audit.csv` and printed in the chart footer.

Nine render-only fallbacks were required across six companies:

| Company | Reference | Missing axes |
|---|---|---|
| ADANIGREEN | Power & Utilities | PAT CAGR 5yr |
| ATGL | Nifty 100 | FCF Score |
| JINDALSTEL | Steel | PAT CAGR 5yr |
| JIOFIN | Nifty 100 | PAT CAGR 5yr; Revenue CAGR 5yr |
| PNB | Public Sector Banks | ROCE |
| SBIN | Public Sector Banks | ROE; ROCE; D/E |

## Validation results

| Check | Result |
|---|---:|
| Companies profiled | 92 |
| Peer-group comparisons | 56 |
| Nifty 100 comparisons | 36 |
| PNG files generated | 92 |
| Unique filenames | 92 |
| Empty files | 0 |
| Minimum file size | greater than 230 KB |
| Image resolution | approximately 1676 × 1485 px |
| Automated chart validations | 92/92 PASS |
| Visual samples reviewed | 6/6 PASS |
| New Day 19 tests | 12/12 PASS |
| Complete regression suite | 208/208 PASS |

## Visual review sample

The reviewed sample deliberately covers ordinary and missing-value cases in
both reference categories:

- TCS — IT Services peer average;
- NESTLEIND — FMCG peer average;
- SBIN — Public Sector Banks, with a documented missing-axis footer;
- ABB — Nifty 100 average;
- ADANIENT — Nifty 100 average;
- ATGL — Nifty 100 average, with a documented missing-axis footer.

All six charts passed title, axis, polygon, dashed-reference, legend, scale,
footer and general readability checks.

## Outputs

- `reports/radar_charts/` — 92 PNG files;
- `output/radar_chart_audit.csv` — one file-level validation row per company;
- `output/radar_chart_visual_review.csv` — visual inspection evidence;
- `output/day19_test_results.txt` — focused and full test results;
- `src/analytics/radar.py` — reusable chart generator;
- `tests/analytics/test_radar.py` — Day 19 test suite.

## Reproduction

```bash
python -m src.analytics.radar \
  --database db/nifty100.db \
  --chart-dir reports/radar_charts \
  --audit output/radar_chart_audit.csv

python -m unittest tests.analytics.test_radar -v
python -m unittest discover -s tests -p "test_*.py" -v
```
