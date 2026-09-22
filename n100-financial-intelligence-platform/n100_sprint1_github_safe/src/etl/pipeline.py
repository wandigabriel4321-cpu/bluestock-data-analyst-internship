"""End-to-end Sprint 1 load for the N100 SQLite database.

The pipeline reads and audits all twelve official workbooks.  Ten Sprint 1
datasets are validated and loaded into SQLite in dependency-safe order;
``financial_ratios.xlsx`` and ``peer_groups.xlsx`` are retained as audited
reference inputs for Sprints 2 and 3.

Critical findings are preserved in ``validation_failures_initial.csv``.  The
validator then applies the documented rejection/correction actions and runs a
second pass.  Database publication is atomic and is allowed only when the
second pass contains zero CRITICAL failures and SQLite reports no FK errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.etl.loader import DATASET_SPECS, ExcelLoader, LoadResult, detect_dataset
from src.etl.validator import (
    FAILURE_FIELDS,
    DataQualityValidator,
    ValidationResult,
    write_validation_outputs,
)


SPRINT1_TABLE_ORDER = (
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "sectors",
    "market_cap",
    "stock_prices",
)

REFERENCE_TABLES = {
    "financial_ratios": "Sprint 2 reference input",
    "peer_groups": "Sprint 3 reference input",
}


class PipelineError(RuntimeError):
    """Raised when publication cannot safely continue."""


@dataclass(frozen=True)
class DatabaseLoadResult:
    row_counts: dict[str, int]
    foreign_key_violations: int
    integrity_check: str


@dataclass(frozen=True)
class PipelineResult:
    database_path: Path
    audit_path: Path
    initial_failures_path: Path
    final_failures_path: Path
    final_summary_path: Path
    summary_path: Path
    source_file_count: int
    database_row_count: int
    initial_critical_failures: int
    final_critical_failures: int
    final_warning_failures: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_failures(result: ValidationResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [failure.as_dict() for failure in result.failures], columns=FAILURE_FIELDS
    )
    frame.to_csv(path, index=False)
    return path


def _failure_counts(result: ValidationResult) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for failure in result.failures:
        key = (failure.table_name, failure.severity)
        counts[key] = counts.get(key, 0) + 1
    return counts


def create_database(
    tables: dict[str, pd.DataFrame], schema_path: str | Path, database_path: str | Path
) -> DatabaseLoadResult:
    """Load validated tables into an atomically published SQLite database."""
    missing = [name for name in SPRINT1_TABLE_ORDER if name not in tables]
    if missing:
        raise PipelineError(f"Missing validated tables: {', '.join(missing)}")

    schema = Path(schema_path)
    target = Path(database_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_handle = tempfile.NamedTemporaryFile(
        prefix="nifty100_", suffix=".pending.db", dir=target.parent, delete=False
    )
    temporary_path = Path(temporary_handle.name)
    temporary_handle.close()

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temporary_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema.read_text(encoding="utf-8"))
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise PipelineError("SQLite foreign-key enforcement is not enabled")

        for table_name in SPRINT1_TABLE_ORDER:
            tables[table_name].to_sql(
                table_name, connection, if_exists="append", index=False
            )
        connection.commit()

        row_counts = {
            table_name: int(
                connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            )
            for table_name in SPRINT1_TABLE_ORDER
        }
        fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if fk_rows:
            raise PipelineError(f"SQLite reported {len(fk_rows)} FK violation(s)")
        if integrity.lower() != "ok":
            raise PipelineError(f"SQLite integrity check failed: {integrity}")

        connection.close()
        connection = None
        temporary_path.replace(target)
        return DatabaseLoadResult(row_counts, len(fk_rows), integrity)
    except Exception:
        if connection is not None:
            connection.close()
        temporary_path.unlink(missing_ok=True)
        raise


def _source_paths(directories: Iterable[str | Path]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for directory in directories:
        for path in Path(directory).glob("*.xlsx"):
            paths[detect_dataset(path).table_name] = path
    return paths


def build_load_audit(
    results: list[LoadResult],
    source_paths: dict[str, Path],
    initial: ValidationResult,
    final: ValidationResult,
    database: DatabaseLoadResult,
    run_id: str,
) -> pd.DataFrame:
    """Create one audit row per official workbook plus a TOTAL row."""
    initial_counts = _failure_counts(initial)
    final_counts = _failure_counts(final)
    by_table = {result.table_name: result for result in results}
    spec_by_table = {spec.table_name: spec for spec in DATASET_SPECS}
    load_order = {name: position for position, name in enumerate(SPRINT1_TABLE_ORDER, 1)}

    rows: list[dict[str, Any]] = []
    for spec in DATASET_SPECS:
        result = by_table[spec.table_name]
        source = source_paths[spec.table_name]
        database_rows = database.row_counts.get(spec.table_name, 0)
        is_reference = spec.table_name in REFERENCE_TABLES
        rows.append({
            "run_id": run_id,
            "load_order": "" if is_reference else load_order[spec.table_name],
            "source_file": spec.source_name,
            "source_sha256": _sha256(source),
            "source_size_bytes": source.stat().st_size,
            "table_name": spec.table_name,
            "sprint": spec.sprint,
            "load_status": "REFERENCE_ONLY" if is_reference else "DB_LOADED",
            "source_rows": result.row_count,
            "conversion_errors": len(result.errors),
            "initial_critical_failures": initial_counts.get(
                (spec.table_name, "CRITICAL"), 0
            ),
            "initial_warning_failures": initial_counts.get(
                (spec.table_name, "WARNING"), 0
            ),
            "rows_rejected_before_db": 0 if is_reference else result.row_count - database_rows,
            "rows_loaded_to_db": database_rows,
            "final_critical_failures": final_counts.get(
                (spec.table_name, "CRITICAL"), 0
            ),
            "final_warning_failures": final_counts.get(
                (spec.table_name, "WARNING"), 0
            ),
            "notes": REFERENCE_TABLES.get(
                spec.table_name,
                "Validated and loaded into the Sprint 1 SQLite database",
            ),
        })

    numeric_columns = (
        "source_size_bytes", "source_rows", "conversion_errors",
        "initial_critical_failures", "initial_warning_failures",
        "rows_rejected_before_db", "rows_loaded_to_db",
        "final_critical_failures", "final_warning_failures",
    )
    total = {column: int(sum(row[column] for row in rows)) for column in numeric_columns}
    total.update({
        "run_id": run_id,
        "load_order": "",
        "source_file": "TOTAL",
        "source_sha256": "",
        "table_name": "12 sources / 10 database tables",
        "sprint": "",
        "load_status": "COMPLETE",
        "notes": "All sources audited; final database passed FK and integrity checks",
    })
    rows.append(total)
    return pd.DataFrame(rows)


def run_pipeline(
    *,
    raw_dir: str | Path = "data/raw",
    supporting_dir: str | Path = "data/supporting",
    schema_path: str | Path = "db/schema.sql",
    database_path: str | Path = "db/nifty100.db",
    output_dir: str | Path = "output",
    processed_dir: str | Path = "data/processed",
    check_urls: bool = False,
) -> PipelineResult:
    """Execute the complete Day 20 load and publish verified artefacts."""
    output = Path(output_dir)
    processed = Path(processed_dir)
    output.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with tempfile.TemporaryDirectory(prefix="n100_full_load_") as temporary:
        temporary_root = Path(temporary)
        loader = ExcelLoader(temporary_root / "loader_output")
        results, read_failures = loader.load_directories(
            (raw_dir, supporting_dir), maximum_sprint=3, strict_schema=True
        )
        if read_failures:
            messages = "; ".join(
                f"{item['source_file']}: {item['error']}" for item in read_failures
            )
            raise PipelineError(f"One or more source workbooks could not be read: {messages}")
        if len(results) != len(DATASET_SPECS):
            raise PipelineError(
                f"Expected {len(DATASET_SPECS)} source workbooks; loaded {len(results)}"
            )

        result_by_table = {result.table_name: result for result in results}
        missing = [name for name in SPRINT1_TABLE_ORDER if name not in result_by_table]
        if missing:
            raise PipelineError(f"Missing Sprint 1 source tables: {', '.join(missing)}")
        sprint1_tables = {
            name: result_by_table[name].dataframe.copy(deep=True)
            for name in SPRINT1_TABLE_ORDER
        }
        read_error_path = loader.error_path
        loader_errors = (
            pd.read_csv(read_error_path) if read_error_path.exists() else pd.DataFrame()
        )

        initial = DataQualityValidator(
            sprint1_tables, check_urls=check_urls, loader_errors=loader_errors
        ).validate()
        initial_failures_path = _write_failures(
            initial, output / "validation_failures_initial.csv"
        )
        if initial.load_blocked:
            raise PipelineError("DQ-01 blocked the load; duplicate company PKs require review")

        # The second pass proves that all CRITICAL rows rejected on pass one are
        # absent from the publication candidate.
        final = DataQualityValidator(
            initial.tables, check_urls=check_urls
        ).validate()
        final_critical = sum(
            failure.severity == "CRITICAL" for failure in final.failures
        )
        if final.load_blocked or final_critical:
            raise PipelineError(
                f"Final validation still contains {final_critical} CRITICAL failure(s)"
            )

        for table_name, frame in final.tables.items():
            frame.to_csv(processed / f"{table_name}.csv", index=False)

        database = create_database(final.tables, schema_path, database_path)

        final_failures_path, final_summary_path = write_validation_outputs(final, output)
        if read_error_path.exists():
            pd.read_csv(read_error_path).to_csv(output / "read_errors.csv", index=False)
        else:
            pd.DataFrame(columns=ExcelLoader.ERROR_FIELDS).to_csv(
                output / "read_errors.csv", index=False
            )

        paths = _source_paths((raw_dir, supporting_dir))
        audit = build_load_audit(results, paths, initial, final, database, run_id)
        audit_path = output / "load_audit.csv"
        audit.to_csv(audit_path, index=False)

        summary = {
            "run_id": run_id,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_files_audited": len(results),
            "database_tables_loaded": len(database.row_counts),
            "database_rows_loaded": sum(database.row_counts.values()),
            "database_row_counts": database.row_counts,
            "initial_critical_failures": sum(
                failure.severity == "CRITICAL" for failure in initial.failures
            ),
            "initial_warning_failures": sum(
                failure.severity == "WARNING" for failure in initial.failures
            ),
            "final_critical_failures": final_critical,
            "final_warning_failures": sum(
                failure.severity == "WARNING" for failure in final.failures
            ),
            "foreign_key_violations": database.foreign_key_violations,
            "sqlite_integrity_check": database.integrity_check,
            "reference_inputs": REFERENCE_TABLES,
            "dq13_live_http_checks": check_urls,
        }
        summary_path = output / "full_load_summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return PipelineResult(
        database_path=Path(database_path),
        audit_path=audit_path,
        initial_failures_path=initial_failures_path,
        final_failures_path=final_failures_path,
        final_summary_path=final_summary_path,
        summary_path=summary_path,
        source_file_count=len(results),
        database_row_count=sum(database.row_counts.values()),
        initial_critical_failures=summary["initial_critical_failures"],
        final_critical_failures=final_critical,
        final_warning_failures=summary["final_warning_failures"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete N100 Sprint 1 load")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--supporting-dir", type=Path, default=Path("data/supporting"))
    parser.add_argument("--schema", type=Path, default=Path("db/schema.sql"))
    parser.add_argument("--database", type=Path, default=Path("db/nifty100.db"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()

    result = run_pipeline(
        raw_dir=args.raw_dir,
        supporting_dir=args.supporting_dir,
        schema_path=args.schema,
        database_path=args.database,
        output_dir=args.output_dir,
        processed_dir=args.processed_dir,
        check_urls=args.check_urls,
    )
    print(f"Audited {result.source_file_count} source workbook(s)")
    print(f"Loaded {result.database_row_count} row(s) into {result.database_path}")
    print(f"Initial CRITICAL failures: {result.initial_critical_failures}")
    print(f"Final CRITICAL failures: {result.final_critical_failures}")
    print(f"Final WARNING failures: {result.final_warning_failures}")
    print(f"Audit: {result.audit_path}")


if __name__ == "__main__":
    main()
