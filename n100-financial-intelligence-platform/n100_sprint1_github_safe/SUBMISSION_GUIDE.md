# N100 Sprint 1 — GitHub and Google Drive Submission Guide

## Files already prepared

Two separate deliverables are used to prevent confidential data from being
published accidentally:

1. `n100_sprint1_github_safe.zip` — code, tests, schema, SQL and documentation.
2. `n100_sprint1_confidential_results.zip` — SQLite database and generated
   validation/audit outputs.

The complete Drive package is `N100_Final_Submission_Efigenia_Gabriel.zip`.

## Part 1 — Publish the project on GitHub

Use only `n100_sprint1_github_safe.zip` for GitHub.

1. Extract `n100_sprint1_github_safe.zip` on the computer.
2. Open the existing `bluestock-data-analyst-internship` repository.
3. Create a new top-level folder named:

   `n100-financial-intelligence-platform`

4. Upload the extracted contents into that folder.
5. Confirm that the following are present:

   - `.gitignore`
   - `.env.example`
   - `Makefile`
   - `README.md`
   - `requirements.txt`
   - `db/schema.sql`
   - `notebooks/exploratory_queries.sql`
   - `src/`
   - `tests/`
   - the approved Markdown files in `docs/`

6. Confirm that none of the following appear in GitHub:

   - any `.xlsx` source workbook;
   - `nifty100.db`;
   - files from `data/processed/`;
   - files from `output/`;
   - `.env`;
   - `Nifty100_Project_Document_FINAL.pdf`;
   - `source_checksums.sha256`.

7. Use this commit message:

   `feat: complete N100 Sprint 1 data foundation`

8. Commit the files directly to `main`, or create a branch and merge a pull
   request if the internship requires PR evidence.
9. Open the uploaded folder on GitHub and verify that the README renders.
10. Copy the URL of the `n100-financial-intelligence-platform` folder.

## Part 2 — Prepare the Google Drive folder

1. Extract `N100_Final_Submission_Efigenia_Gabriel.zip`.
2. Upload the extracted folder to Google Drive without renaming its internal
   files or folders.
3. The Drive folder must contain:

   - `00_SUBMISSION_INDEX.md`
   - `01_GitHub_Safe_Project/`
   - `02_Database_and_Reports/`
   - `03_Documentation/`
   - `04_Test_Evidence/`

4. Open `01_GitHub_Safe_Project/GITHUB_LINK.txt`.
5. Replace the placeholder with the actual GitHub folder URL copied in Part 1.
6. Return to the main Google Drive folder.
7. Right-click the folder and select **Share**.
8. Under **General access**, change **Restricted** to
   **Anyone with the link**.
9. Keep the role as **Viewer**.
10. Copy the Google Drive folder link.
11. Open the copied link in a private/incognito browser window.
12. Confirm that the folder and its files open without requesting permission.

## Part 3 — Final submission check

Before submitting, verify all of the following:

- The GitHub link opens the N100 project folder.
- The GitHub repository does not expose source workbooks or generated data.
- The Google Drive link works in an incognito window.
- `db/nifty100.db` exists inside `02_Database_and_Reports/`.
- `load_audit.csv`, `manual_review.csv` and `validation_failures.csv` are
  present.
- `notebooks/exploratory_queries.sql` contains Q01 through Q10.
- The test evidence states `49 tests` and `OK`.
- The Day 20 and Day 21 reports are included.

## Suggested note to admin

> The final N100 Sprint 1 submission includes the validated SQLite database,
> load audit, initial and final validation reports, reproducible five-company
> manual review, year-coverage analysis, ten executed exploratory SQL queries,
> complete source code and evidence of 49 passing automated tests. The Google
> Drive folder is accessible to anyone with the link as a Viewer. The GitHub
> project excludes confidential source workbooks and generated data files.
