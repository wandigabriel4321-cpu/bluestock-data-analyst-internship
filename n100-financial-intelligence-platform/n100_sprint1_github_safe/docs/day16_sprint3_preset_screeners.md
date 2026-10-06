# Sprint 3 — Day 16 Six Preset Screeners

**Scheduled date:** 2 October 2026  
**Rebuilt and revalidated:** 6 October 2026  
**Implementation status:** COMPLETE  
**Count-gate status:** 4 PASS, 2 investigated FAIL

## Scope completed

- Implemented the six official preset definitions in
  `config/screener_config.yaml`.
- Created `src/screener/presets.py` for strict rule evaluation, diagnostics,
  manual samples and CSV exports.
- Extended the Day 15 snapshot with Revenue CAGR 3yr, dividend payout and the
  preceding substantive D/E observation.
- Preserved the Financials exemption only for the ordinary maximum D/E rules;
  the exact-zero Debt-Free rule remains applicable to every company.
- Created 15 focused tests in `tests/screener/test_presets.py`.
- Added the `presets`, `test-presets` and `day16-check` Makefile targets.

## Official thresholds and results

| Preset | Official rules | Companies | 5–50 gate |
| --- | --- | ---: | --- |
| Quality Compounder | ROE > 15%; D/E < 1; FCF > 0; Revenue CAGR 5yr > 10% | 21 | PASS |
| Value Pick | P/E < 20; P/B < 3; D/E < 2; Dividend Yield > 1% | 2 | FAIL |
| Growth Accelerator | PAT CAGR 5yr > 20%; Revenue CAGR 5yr > 15%; D/E < 2 | 19 | PASS |
| Dividend Champion | Dividend Yield > 2%; Dividend Payout < 80%; FCF > 0 | 30 | PASS |
| Debt-Free Blue Chip | D/E = 0; ROE > 12%; Revenue > INR 5,000 crore | 2 | FAIL |
| Turnaround Watch | Revenue CAGR 3yr > 10%; latest FCF > 0; D/E declining YoY | 31 | PASS |

The execution universe contains exactly 92 unique companies. Strict `>` and
`<` operators are used; equality at a boundary does not pass. The Debt-Free
screen uses numeric equality to zero and does not treat small positive values
as zero.

## Investigation of the two count-gate failures

### Value Pick

The rules are applied cumulatively:

| Step | Remaining companies |
| --- | ---: |
| P/E < 20 | 15 |
| P/B < 3 | 2 |
| D/E < 2 | 2 |
| Dividend Yield > 1% | 2 |

The limiting condition is therefore the combination of the official P/E and
P/B valuation ceilings, not missing values or a software defect. The two valid
results are `M&M` and `MOTHERSON`; both also satisfy the leverage and dividend
conditions. All 92 companies have P/E, P/B and Dividend Yield values in the
latest snapshot. The one missing D/E value does not affect these two results.

### Debt-Free Blue Chip

The exact D/E = 0 condition returns only three companies: `JIOFIN`, `LICI` and
`SBILIFE`. The ROE > 12% rule excludes `JIOFIN` because its ROE is approximately
1.15%. `LICI` and `SBILIFE` both have revenue above INR 5,000 crore, leaving two
final results.

The official exact-zero definition is the limiting factor. It was not relaxed
to a near-zero threshold, and the Financials-sector maximum-D/E exemption was
not incorrectly applied to this equality rule.

## Missing-value policy

- Missing values remain null; no missing metric is converted to zero.
- A company with a missing value fails the rule that requires that value.
- For Turnaround Watch, both current and previous D/E must exist.
- Missing-value counts for every preset rule are recorded in
  `output/preset_validation_report.csv` and
  `output/preset_diagnostics.csv`.

## Manual verification

`output/preset_manual_checks.csv` independently re-evaluates every rule for up
to three companies per preset. The file contains 16 checks because the two
failing-count presets have only two results each. All 16 checks are PASS.

Representative results include:

- Quality Compounder: `INDIGO`, `LT`, `TCS`;
- Value Pick: `MOTHERSON`, `M&M`;
- Growth Accelerator: `INDIGO`, `IRCTC`, `TRENT`;
- Dividend Champion: `INDIGO`, `COALINDIA`, `NESTLEIND`;
- Debt-Free Blue Chip: `LICI`, `SBILIFE`;
- Turnaround Watch: `BPCL`, `ADANIPOWER`, `TATAMOTORS`.

## Evidence files

| File | Purpose |
| --- | --- |
| `output/preset_screener_results.csv` | Combined company-level results for all presets |
| `output/preset_validation_report.csv` | Count, thresholds, missing values and PASS/FAIL status |
| `output/preset_diagnostics.csv` | Cumulative population after every official rule |
| `output/preset_manual_checks.csv` | Independently recomputed rule evidence for sampled companies |
| `output/day16_test_results.txt` | Focused and full regression results |

## Execution

```bash
make presets PYTHON=python3
make test-presets PYTHON=python3
make day16-check PYTHON=python3
```

No official threshold was changed to manufacture a target count. The two
out-of-range results are reproducible, explained and retained as FAIL in the
validation report, as required by the assignment.
