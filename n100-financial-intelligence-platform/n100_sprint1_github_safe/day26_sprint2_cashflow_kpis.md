# Day 11 — Cash Flow KPIs and Capital Allocation

Date: 26 September 2026

## Scope completed

The cash-flow KPI engine was implemented in
`src/analytics/cashflow_kpis.py` with:

- Free Cash Flow;
- annual CFO/PAT ratio;
- exact five-year average CFO/PAT ratio;
- CFO quality classification;
- CapEx Intensity and classification;
- FCF Conversion Rate;
- CFO, CFI and CFF signs;
- exhaustive capital-allocation classification;
- reproducible SQLite-to-CSV execution.

## KPI formulas and classifications

| KPI | Formula | Invalid denominator behavior |
|---|---|---|
| Free Cash Flow | `operating_activity + investing_activity` | Missing component returns `None`; negative FCF remains valid |
| CFO/PAT Ratio | `operating_activity / net_profit` | PAT equal to zero or unavailable returns `None` |
| CFO Quality Score | Mean of five exact consecutive annual CFO/PAT ratios | Partial history or any invalid annual ratio returns no five-year score |
| CapEx Intensity | `abs(investing_activity) / sales * 100` | Non-positive or unavailable sales returns `None` |
| FCF Conversion Rate | `FCF / operating_profit * 100` | Operating profit equal to zero or unavailable returns `None` |

CFO Quality classifications:

- greater than `1.0`: `High Quality`;
- from `0.5` through `1.0`: `Moderate`;
- below `0.5`: `Accrual Risk`.

CapEx Intensity classifications:

- below `3%`: `Asset Light`;
- from `3%` through `8%`: `Moderate`;
- above `8%`: `Capital Intensive`.

## Capital-allocation matrix

The three finite cash-flow components are converted into a binary sign matrix.
Zero is assigned `+` as the non-negative bin so every finite record belongs to
one of exactly eight combinations.

| CFO | CFI | CFF | Pattern label |
|:---:|:---:|:---:|---|
| + | + | + | Cash Accumulator |
| + | + | - | Liquidating Assets |
| + | - | + | Mixed |
| + | - | - | Reinvestor |
| - | + | + | Distress Signal |
| - | + | - | Asset Sale Survival |
| - | - | + | Growth Funded by Debt |
| - | - | - | Pre-Revenue |

For the `(+,-,-)` signature, a valid five-year CFO/PAT average above `1.0`
subclassifies the record as `Shareholder Returns`; otherwise it remains
`Reinvestor`, following the project specification.

The source document names seven signatures but omits a name for `(-,+,-)`.
`Asset Sale Survival` was adopted as the explicit descriptive label because
operations consume cash, investing produces cash through disposals and
financing is also an outflow. This closes the matrix without leaving an
eligible record unclassified.

## Automated tests

`tests/kpi/test_cashflow_kpis.py` contains 16 tests covering:

- positive and negative FCF;
- missing cash-flow components;
- normal and zero-PAT CFO/PAT cases;
- CFO quality thresholds and exact five-year coverage;
- invalidated five-year quality when PAT is zero;
- CapEx Intensity calculation and threshold boundaries;
- FCF Conversion and zero operating profit;
- positive, negative and zero sign handling;
- all eight binary sign combinations;
- `Shareholder Returns` subclassification;
- exclusion of ineligible missing-component records;
- required CSV columns and non-empty labels.

Verification result:

- Day 11 tests: **16 passed**;
- complete project regression suite: **110 passed, 0 failed**.

## Real-data outputs

The outputs are reproducible with:

```bash
make cashflow-audit PYTHON=.venv/bin/python
```

Generated confidential files:

- `output/capital_allocation.csv` — the six required fields for every eligible row;
- `output/cashflow_kpis_day11.csv` — full annual KPI audit for Day 12 integration.

### Eligibility and coverage

| Measure | Result |
|---|---:|
| Source cash-flow rows audited | 1,056 |
| Eligible rows with finite CFO, CFI and CFF | 1,054 |
| Ineligible rows with all three components unavailable | 2 |
| Companies represented in eligible output | 91 |
| Eligible rows without `pattern_label` | **0** |
| Required output columns | **6 of 6** |

The two excluded rows are `HDFCLIFE` for `2013-03` and `2014-03`; all three
cash-flow components are absent in the validated source. They are not eligible
for sign classification and are retained in the full KPI audit for traceability.

### Pattern distribution

| Pattern label | Rows |
|---|---:|
| Cash Accumulator | 5 |
| Liquidating Assets | 95 |
| Mixed | 205 |
| Reinvestor | 318 |
| Shareholder Returns | 269 |
| Distress Signal | 41 |
| Asset Sale Survival | 15 |
| Growth Funded by Debt | 98 |
| Pre-Revenue | 8 |

All eight binary signatures are present in the eligible data. The ninth label
is the documented CFO/PAT-based subclass of the `(+,-,-)` signature.

### KPI audit summary

| Classification | Rows |
|---|---:|
| CFO High Quality | 411 |
| CFO Moderate | 105 |
| CFO Accrual Risk | 159 |
| CFO five-year score unavailable | 381 |
| CapEx Asset Light | 287 |
| CapEx Moderate | 264 |
| CapEx Capital Intensive | 502 |
| CapEx classification unavailable | 3 |
| FCF Conversion Rate available | 1,041 |

Free Cash Flow was positive in 714 rows, zero in 2, negative in 338 and
unavailable in the 2 source rows with missing components.

## Outcome

Day 11 is complete. Cash-flow KPIs are deterministic, zero denominators are
safe, the five-year quality score requires complete history, all eight sign
combinations are covered, and no eligible output row lacks a pattern label.
