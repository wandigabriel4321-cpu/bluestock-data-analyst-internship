# Day 13 — Financials, ROCE and Anomaly Review

**Execution date:** 28 September 2026  
**Project:** N100 Financial Intelligence Platform  
**Scope:** Financials-sector leverage treatment, ROCE/ROE cross-checks and count reconciliation

## Outcome

Day 13 is complete. The ratio engine now classifies each Financials company by
its supplied subsector and applies the common Debt-to-Equity warning only where
it is economically appropriate.

| Check | Result |
|---|---:|
| Financials companies reviewed | **23** |
| ROCE/ROE comparison rows | **46** |
| Banks | 9 |
| NBFCs | 8 |
| Insurers | 5 |
| Other Financials/holding company | 1 |
| Financial D/E values above 5 incorrectly flagged | **0** |
| Foreign-key violations | **0** |
| SQLite integrity | **ok** |

## Sector treatment

Financial entity types are derived from the official sector master:

| Entity type | Included subsectors | Companies | Common D/E > 5 warning |
|---|---|---:|---|
| Bank | Private Banks; Public Sector Banks | 9 | Suppressed |
| NBFC | Consumer Finance; Speciality Finance; Diversified Financials | 8 | Suppressed |
| Insurance | Life Insurance; General Insurance | 5 | Suppressed |
| Other Financial | Holding Companies | 1 | Retained |

The data contains 146 annual D/E values greater than five among the exempt
banks, NBFCs and insurers. None is incorrectly marked as high leverage. The
ordinary warning remains active for non-financial companies and for any
Financials subsector that does not belong to the explicit carve-out.

ROCE is still calculated as:

```text
(operating_profit - depreciation)
--------------------------------- × 100
equity_capital + reserves + borrowings
```

For banks, NBFCs and insurers, this value is treated as a transparent
calculation rather than an absolute industrial-company health threshold. The
output also records the median and percentile rank within Bank, NBFC,
Insurance or Other Financial peer types.

## ROCE and ROE comparison policy

The fields `companies.roce_percentage` and `companies.roe_percentage` contain
one company-level reference value without a reporting-year field. Each is
therefore compared with the latest annual period for which that metric can be
calculated. A material difference is an absolute difference greater than five
percentage points; exactly five remains within tolerance.

| Classification | Rule |
|---|---|
| `FORMULA_DIFFERENCE` | Financials ROCE differs by more than 5 points because the industrial funded-capital formula requires sector-relative interpretation |
| `VERSION_DIFFERENCE` | ROE differs by more than 5 points and the latest calculable period is older than the latest annual key available |
| `SOURCE_PROBLEM` | Same-period ROE differs materially from its reference and requires source review |
| `INSUFFICIENT_HISTORY` | A calculated annual value or company-level reference is unavailable |
| `WITHIN_TOLERANCE` | Absolute difference is no greater than 5 points |

### Review results

| Classification | Comparisons |
|---|---:|
| Within tolerance | 28 |
| Formula difference | 11 |
| Version difference | 3 |
| Source problem | 1 |
| Insufficient history | 3 |
| **Total** | **46** |

The 15 numeric differences above five percentage points and the three
insufficient-history cases are appended to `output/ratio_edge_cases.log`.

### Material findings

- Eleven Financials ROCE comparisons require formula-relative interpretation.
  The largest divergences occur in insurance companies, where the industrial
  capital-employed denominator does not describe the sector's operating model.
- Three ROE comparisons use a March 2024 calculation while a September 2024
  annual key exists without aligned P&L data. They are classified as version
  differences rather than overwritten.
- PNB's same-period calculated ROE diverges materially from the supplied
  company-level value and is classified as a source problem.
- PNB has no valid calculated ROCE; SBIN has neither a valid calculated ROCE nor
  ROE in the current aligned annual inputs. These are retained as insufficient
  history, not replaced with zero.

## Formal reconciliation: 19 versus 23

The task text mentions 19 Financials companies. The current supplied data
contains 23, a variance of four.

Evidence was checked at three independent stages:

| Evidence | Financials count |
|---|---:|
| Original `data/supporting/sectors.xlsx` | 23 |
| Normalised `data/processed/sectors.csv` | 23 |
| SQLite `sectors` table | 23 |

The official workbook contains 92 sector rows and its SHA-256 checksum is:

```text
34919a77059d1f8d654e45205eb02224042c178fe828919b163439e1d6af8acc
```

The 23 companies span eight supplied subsectors:

| Subsector | Companies |
|---|---:|
| Private Banks | 5 |
| Public Sector Banks | 4 |
| Life Insurance | 4 |
| Consumer Finance | 3 |
| Speciality Finance | 3 |
| Diversified Financials | 2 |
| General Insurance | 1 |
| Holding Companies | 1 |

No separate list identifying the 19 companies accompanies the task. It is
therefore impossible to identify the exact four additions or removals without
guessing. The defensible conclusion is a **source-version difference**, not a
loading error. The engine consequently uses all 23 official current records
and does not delete four valid companies merely to reproduce a stale count.

## Generated outputs

- `output/sector_roce_notes.csv` — all 46 comparisons, sector treatment,
  peer-relative ROCE statistics, classification and count reconciliation;
- `output/ratio_edge_cases.log` — the complete edge-case register, including
  18 Day 13 Financials review entries.

## Reproduction and tests

```bash
make sector-review PYTHON=.venv/bin/python
make test-sector-review PYTHON=.venv/bin/python
make test PYTHON=.venv/bin/python
```

Twelve new tests cover entity classification, D/E carve-outs, the strict
five-point boundary, all four required anomaly classes, database review output
and edge-case integration.

- Day 13 tests: **12 passed, 0 failed**;
- complete regression suite: **132 passed, 0 failed**.

