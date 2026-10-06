# Sprint 3 Retrospective

**Sprint:** Screener & Peer Comparison Engine  
**Final review:** 6 October 2026

## What went well

- The Sprint 2 database and 140-test baseline remained stable while the
  screener, composite score and peer modules were added.
- Business rules were moved into editable YAML configuration instead of being
  scattered through hard-coded branches.
- Global and sector-relative scores were kept separate from the legacy Sprint
  2 score, avoiding a breaking historical change.
- Missing values were preserved and audited rather than converted to zeros.
- Peer rankings, Excel reports and radar charts share the same 0–100 direction:
  a higher score is better, including inverted D/E.
- Final integration testing exceeded the internal target: 35 new Day 21 tests
  and 256 total passing tests.
- Direct Excel deliverables, detailed audits and a full recovery checkpoint
  reduce the risk of losing work between sessions.

## Challenges encountered

- The task text was ambiguous about whether all 20 peer-report KPIs required
  percentiles, while only ten official metrics were defined. The implementation
  uses 20 raw KPIs plus ten official percentile columns and documents the choice.
- Two preset counts fall below the 5–50 guideline. Investigation showed this is
  produced by the strict official P/E/P/B and exact-zero D/E conditions.
- Different financial metrics have different latest substantive periods, so
  the system selects the latest available value per metric and preserves audit
  context rather than forcing a single incomplete period.
- Wide 26–32-column Excel reports required landscape A3 fit-to-width settings
  as well as ordinary interactive widths, filters and frozen panes.
- Six radar profiles contain missing source axes. The visualization uses a
  disclosed render-only reference fallback without altering stored data.

## Decisions retained

- Never change official thresholds solely to obtain a desired number of rows.
- Never invent zero values for missing financial observations.
- Keep public GitHub packages free from raw data, processed data, databases,
  backups and confidential generated outputs.
- Preserve evidence for every manual or visual claim in machine-readable CSV.
- Treat preset-count deviations as documented exceptions, not hidden passes.

## Improvements for the next sprint

- Add a release manifest with file hashes at the beginning of the submission
  process, not only at packaging time.
- Add schema/data-version identifiers to generated workbooks.
- Add a small HTML summary dashboard for the preset and peer audit outputs.
- Separate automated validation from human visual confirmation in the command
  interface more explicitly.
- Run the final packaging rehearsal at least one full day before submission.

## Final outcome

Sprint 3 is technically complete and reproducible. All 256 tests pass, the
database is valid, 17 Excel sheets and the radar sample passed review, and all
required public/confidential deliverables are prepared. The only qualification
is the transparent, data-driven count variance in two official presets.

