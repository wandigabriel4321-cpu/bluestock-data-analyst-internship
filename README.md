# Bluestock FinTech - Data Analyst Internship Assignments

This repository contains the assignments completed during the Bluestock FinTech Data Analyst Internship prerequisite programme.

**Intern:** Efigénia Wandi Filipe Gabriel  
**Programme:** Data Analyst Internship (FinTech)  
**Start date:** 1 September 2026  
**Purpose:** Document practical learning in spreadsheets, SQL, Python, data cleaning, exploratory analysis, visualization, financial analysis, REST APIs and Git/GitHub.

## Repository contents

| Week | Task | Main deliverable | Status |
|---|---|---|---|
| 1 | Excel / Google Sheets | Retail sales analytics dashboard | Completed |
| 1 | SQL | Customer, revenue and product analysis queries | Completed |
| 1 | Python for Data Analysis | Jupyter notebook with cleaning, KPIs and visualizations | Completed |
| 1 | Data Cleaning and EDA | Clean dataset and exploratory analysis report | Completed |
| 1 | Data Visualization | Interactive business performance dashboard | Completed |
| 2 | Stock Market Fundamentals | One-page summary and TCS financial statement analysis | Completed |
| 2 | REST APIs and JSON | Exchange-rate API extraction, JSON validation and CSV conversion | Completed |
| 2 | Git and GitHub | Organized repository with version history | In progress |

## Folder structure

```text
.
├── week-1
│   ├── task-01-excel-dashboard
│   ├── task-02-sql
│   ├── task-03-python
│   ├── task-04-data-cleaning-eda
│   └── task-05-data-visualization
├── week-2
│   ├── task-01-stock-market-fundamentals
│   └── task-02-rest-api-json
└── docs
    └── GIT_GITHUB_BEGINNER_GUIDE_PT.md
```

## Selected project highlights

### Retail sales analysis

- Cleaned a sample retail sales dataset.
- Built an Excel dashboard with business KPIs and charts.
- Wrote SQL queries for customer, revenue and product performance.
- Created a Python notebook for cleaning, KPI calculation and visualization.
- Prepared an EDA report and an interactive browser-based dashboard.

### Financial domain analysis

- Summarized core Indian stock-market concepts.
- Analysed Tata Consultancy Services Limited using audited consolidated financial statements for FY2025-26 and FY2024-25.
- Reviewed profitability, liquidity, cash flow, exceptional items and financial ratios.

### REST API and JSON extraction

- Called the public Frankfurter exchange-rate API using HTTP GET.
- Inspected and validated the JSON response.
- Converted 93 exchange-rate observations into an analysis-ready CSV.
- Included an importable Postman Collection with automated response tests.

## Reproducing the API extraction

Python 3 is required. No API key or external Python package is needed.

```bash
cd week-2/task-02-rest-api-json
python extract_exchange_rates.py
```

The script recreates the raw JSON response and the cleaned CSV file in the same folder.

## Git workflow used

This repository uses separate commits for initialization, Week 1 assignments, Week 2 assignments and documentation. This makes the development history easy to inspect and demonstrates version control rather than a single bulk upload.

For a beginner-friendly explanation of repositories, commits, branches, pull requests and the exact commands used, read [the Portuguese Git and GitHub guide](docs/GIT_GITHUB_BEGINNER_GUIDE_PT.md).

## Notes

- Financial content is educational and is not investment or trading advice.
- Public API data may change when the extraction script is run for a different period.
- Large generated or temporary files are excluded through `.gitignore`.

