# Sprint 3 Submission Guide

## Package roles

1. **GitHub Safe Project** — public code, tests, configuration, schema and
   documentation. It excludes source data, processed data, databases, backups,
   generated outputs and radar images.
2. **Confidential Project** — full recoverable project, including the current
   SQLite database, source/supporting data, outputs and radar charts. Upload it
   only to the private/consolidated Google Drive folder.
3. **Documentation** — technical report, validation report, retrospective and
   daily implementation notes.
4. **Test Evidence** — complete Day 21 test summary and machine-readable review
   files.
5. **Excel Outputs** — the six-sheet screener workbook and 11-sheet peer
   comparison workbook.
6. **Radar Charts** — all 92 company PNG files and their audit.
7. **Database** — final `nifty100.db` separately for easy verification.

## GitHub update

1. Extract `N100_Sprint3_GitHub_Safe_Efigenia_Gabriel.zip`.
2. Open the extracted `n100-financial-intelligence-platform` folder.
3. Upload its contents to the existing GitHub project folder.
4. Use the commit message:

   `feat: complete N100 Sprint 3 screener and peer engine`

5. Confirm that GitHub contains the new Sprint 3 source, tests and docs.
6. Confirm that GitHub does **not** contain `data/raw`, `data/processed`,
   `data/supporting`, SQLite databases, database backups or generated outputs.
7. Copy the complete GitHub folder URL into `GITHUB_LINK.txt` in the master
   submission folder.

## Google Drive update

1. Upload the complete master folder
   `N100_Sprint3_Final_Submission_Efigenia_Gabriel` to the consolidated Drive
   location used for previous sprints.
2. Keep the master folder permission as **Anyone with the link — Viewer**.
3. Open the shared link in an incognito/private browser window.
4. Confirm that the index, GitHub-safe package, confidential package,
   documentation, test evidence, Excel files, radar package and database can be
   opened or downloaded.

## Final warning

Do not upload the confidential package, SQLite database or source data to the
public GitHub repository. Keep the documented Value Pick and Debt-Free Blue
Chip count exceptions visible in the validation report.

