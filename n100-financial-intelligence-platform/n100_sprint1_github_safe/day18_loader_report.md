# Day 18 — Loader and normalisation report

## Scope completed

- Confirmed and retained `normalize_year()` and `normalize_ticker()`.
- Added deterministic column-name normalisation.
- Added consistent handling of blank cells and textual missing-value markers.
- Added conversion of comma-separated, currency, accounting and percentage values.
- Added Excel worksheet reading with source-specific header rows.
- Added filename-to-table detection for all 12 official workbooks, including
  downloaded filenames with timestamp/hash prefixes.
- Added required-sheet and schema validation.
- Added error logging to `output/read_errors.csv`.
- Implemented the executable `src/etl/loader.py` pipeline.
- Added the `make load` command.

## Automated verification

The suite contains exactly 20 tests and all 20 pass. It covers:

- numeric and textual years;
- Indian financial-year labels;
- ticker spaces and exchange prefixes;
- missing values;
- comma-separated and accounting numbers;
- percentages;
- column-name normalisation;
- core and supplementary source detection;
- invalid formats;
- real core-sheet reading and conversion;
- unexpected columns;
- empty files;
- missing worksheets;
- invalid numeric values and error logging.

Command used:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Result: `Ran 20 tests — OK`.

## Official-file integration result

The loader recognised and read all 12 supplied workbooks with zero
workbook-level failures. Under the Sprint 1 limit it loaded the ten required
tables and 11,652 rows:

| Table | Loaded rows | Conversion errors |
|---|---:|---:|
| analysis | 20 | 0 |
| balancesheet | 1,312 | 5 |
| cashflow | 1,187 | 0 |
| companies | 92 | 0 |
| documents | 1,585 | 0 |
| profitandloss | 1,276 | 100 |
| prosandcons | 16 | 0 |
| market_cap | 552 | 0 |
| sectors | 92 | 0 |
| stock_prices | 5,520 | 0 |
| **Total** | **11,652** | **105** |

The 105 conversion errors are expected source-data findings: 100 `TTM`
periods in Profit & Loss and five decimal `2024.5` periods in Balance Sheet.
They are retained as `PARSE_ERROR` and logged with their raw values in
accordance with DQ-07. They are not workbook-reading failures.

## Confidentiality control

Raw workbooks, processed extracts, generated databases and runtime outputs
remain excluded by `.gitignore`. The code package must not contain the official
source workbooks or the generated confidential CSV extracts.
