# Sprint 2 Retrospective — Financial Ratio Engine

**Sprint period:** 23–29 September 2026  
**Project:** N100 Financial Intelligence Platform

## Sprint goal outcome

Sprint 2 achieved its primary goal. The engine calculates profitability,
leverage, efficiency, growth and cash-flow KPIs for all 92 companies and
stores the results in SQLite. The final `financial_ratios` table contains
1,155 company-year rows and no required KPI column is completely empty.

## Completed work

- Implemented profitability ratios: Net Profit Margin, OPM, ROE, ROCE and ROA.
- Implemented Debt-to-Equity, Interest Coverage, Net Debt and Asset Turnover.
- Implemented Revenue, PAT and EPS CAGR for 3-, 5- and 10-year windows.
- Implemented Free Cash Flow, CFO/PAT quality, CapEx Intensity and FCF
  Conversion.
- Implemented all eight CFO/CFI/CFF capital-allocation patterns.
- Built an idempotent engine that populates `financial_ratios` from validated
  Sprint 1 tables.
- Applied a dynamic sector carve-out for banks, NBFCs and insurers.
- Compared ROE and ROCE with supplied reference values and documented material
  differences.
- Added a reproducible manual validation against the original Excel sources.
- Completed 140 automated tests with zero failures.

## What worked well

- Safe division and explicit `None` handling prevented false zero values.
- CAGR flags kept invalid negative-value cases separate from valid growth
  calculations.
- Building the company-year population from the union of annual tables
  preserved all valid records.
- Atomic replacement made repeated engine runs stable and idempotent.
- Dynamic sector classification avoided hard-coded company counts.
- Separate public and confidential delivery packages reduced disclosure risk.

## Difficulties and resolutions

### Financials company count

The task referred to 19 Financials companies, but every supplied current source
contained 23. The engine retained all 23 authoritative records and documented
the variance as a source-version difference.

### Financial-sector formulas

Ordinary D/E and industrial ROCE interpretation can misrepresent banks, NBFCs
and insurers. The engine suppresses the common high-leverage warning for those
entity types and interprets ROCE relative to peers.

### Reference-period differences

Some company-level ROE and ROCE references did not align with the latest
calculable annual source period. The review separates version differences,
formula differences, source problems and insufficient history.

### Extreme screener ROE values

Four screener results exceeded 100% because the supplied equity and reserves
base was small relative to net profit. The calculations were preserved and the
results were marked for source review.

## Technical decisions retained

- Percentage metrics remain in percentage-point form.
- CAGR uses exact elapsed reporting periods, not row positions.
- Negative and zero CAGR bases produce explicit flags rather than artificial
  numeric values.
- Missing denominators remain `None` only where documented.
- Source reference workbooks are used for comparison, not as the source of
  computed database values.
- Financial-company classification is derived from current sector data.
- Public GitHub packages exclude source data, databases and generated outputs.

## Improvements for the next sprint

- Add source-provenance fields to make period and formula comparisons faster.
- Add configurable outlier thresholds for screener presentation.
- Convert the final review summary into a reusable release checklist.
- Expand peer-relative scoring before the screener and comparison engine are
  exposed to end users.
- Keep the formula registry central so later APIs and dashboards reuse the same
  definitions.

## Exit criteria

| Criterion | Result |
|---|---|
| At least 1,100 ratio rows | PASS — 1,155 |
| All 92 companies represented | PASS |
| Required KPI columns populated | PASS |
| At least 20 formula tests | PASS — 60 |
| Internal target of 26 Sprint 2 tests | PASS — 90 |
| Complete suite has zero failures | PASS — 140 tests |
| Three manual comparisons below 0.1% | PASS — 5 |
| Five-company sample within 2% | PASS — 5 |
| All edge cases explained | PASS — 6,993 |
| Screener result between 15 and 50 | PASS — 38 |

Sprint 2 is technically complete and ready for delivery review.
