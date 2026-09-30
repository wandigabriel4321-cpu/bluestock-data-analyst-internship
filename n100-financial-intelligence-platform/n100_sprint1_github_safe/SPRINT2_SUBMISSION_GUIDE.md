# Sprint 2 Submission Guide

## Prepared packages

Two separate packages prevent confidential data from reaching the public
repository:

1. `n100_sprint2_github_safe.zip` contains code, tests, SQL schema,
   configuration templates and approved Markdown documentation.
2. `n100_sprint2_confidential_complete.zip` contains the complete project,
   including the original sources, processed data, SQLite database and
   generated audit evidence.

## GitHub upload

1. Extract `n100_sprint2_github_safe.zip`.
2. Open the existing repository and the folder
   `n100-financial-intelligence-platform`.
3. Upload the extracted contents and allow the Sprint 2 files to update the
   existing project.
4. Confirm that `src/analytics`, `tests/kpi`, `db/schema.sql`, `Makefile`,
   `README.md` and the Sprint 2 Markdown documents are visible.
5. Confirm that GitHub contains no `.xlsx`, `.db`, generated CSV, `.env`,
   checksum file or supplied project PDF.
6. Use the commit message:

   `feat: complete N100 Sprint 2 financial ratio engine`

7. Open the project README on GitHub and confirm that it renders correctly.
8. Copy the complete URL of the project folder.

## Google Drive upload

1. Extract `N100_Sprint2_Final_Submission_Efigenia_Gabriel.zip`.
2. Upload the extracted folder to the existing master submission folder in
   Google Drive.
3. Replace the placeholder in `01_GitHub_Safe_Project/GITHUB_LINK.txt` with
   the real GitHub project URL.
4. Keep the confidential ZIP inside the Google Drive submission only.
5. Set the master folder to **Anyone with the link** and **Viewer**.
6. Test the link in an incognito window.
7. Confirm that the GitHub-safe and confidential packages both download.

## Final checklist

- GitHub opens without authentication.
- GitHub contains no confidential dataset or generated database.
- Google Drive opens in an incognito window.
- `nifty100.db` exists inside the confidential package.
- `screener_preview.csv`, `manual_kpi_validation.csv`,
  `sprint2_final_review_summary.json` and `ratio_edge_cases.log` are present.
- `sprint2_final_test_results.txt` reports 140 tests and zero failures.
- The final review report, technical documentation and retrospective are
  included.

## Suggested Note to Admin

> The Sprint 2 submission contains the completed N100 Financial Ratio Engine,
> a populated SQLite `financial_ratios` table with 1,155 company-year records
> covering all 92 companies, documented sector-specific treatment, a
> reproducible five-company manual validation, a 38-company preliminary
> screener and evidence of 140 passing automated tests. The public GitHub
> package excludes confidential sources and generated data. The complete
> confidential evidence is available in the Google Drive submission folder.
