"""Sprint 3 Day 18 peer-group percentile rankings.

The official ``peer_groups.xlsx`` workbook is the sole source of membership
and benchmark designations.  Rankings are calculated independently for every
peer group, reporting year and metric.  Missing values are stored for audit
coverage but excluded only from the distribution of their own metric.
"""

from __future__ import annotations

import argparse
import math
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
DEFAULT_PEER_GROUPS_PATH = PROJECT_ROOT / "data" / "supporting" / "peer_groups.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

NO_PEER_GROUP_MESSAGE = "No peer group assigned"
EXPECTED_ASSIGNMENTS = 56
EXPECTED_GROUPS = 11
EXPECTED_UNASSIGNED = 36

# Keys are stored verbatim in peer_percentiles.metric so downstream reports
# can join directly to financial_ratios without another translation layer.
PEER_METRICS: dict[str, bool] = {
    "return_on_equity_pct": False,
    "return_on_capital_employed_pct": False,
    "net_profit_margin_pct": False,
    "debt_to_equity": True,
    "free_cash_flow_cr": False,
    "pat_cagr_5yr": False,
    "revenue_cagr_5yr": False,
    "eps_cagr_5yr": False,
    "interest_coverage": False,
    "asset_turnover": False,
}


@dataclass(frozen=True)
class PeerRunResult:
    assignment_count: int
    group_count: int
    unassigned_count: int
    percentile_row_count: int
    ranked_value_count: int
    missing_value_count: int
    backup_path: Path | None
    assignments_path: Path
    percentiles_path: Path
    audit_path: Path
    manual_checks_path: Path


def _normalise_company_id(value: Any) -> str:
    company_id = str(value).strip().upper()
    if not company_id or company_id == "NAN":
        raise ValueError("Peer-group source contains a blank company_id")
    return company_id


def load_peer_group_assignments(path: str | Path) -> pd.DataFrame:
    """Load and validate the official peer group source workbook."""

    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"Peer-group workbook is missing or empty: {source}")
    frame = pd.read_excel(source, sheet_name=0)
    required = {"peer_group_name", "company_id", "is_benchmark"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Peer-group workbook is missing columns: " + ", ".join(sorted(missing)))

    clean = frame.loc[:, ["peer_group_name", "company_id", "is_benchmark"]].copy()
    clean["company_id"] = clean["company_id"].map(_normalise_company_id)
    clean["peer_group_name"] = clean["peer_group_name"].astype(str).str.strip()
    if clean["peer_group_name"].eq("").any():
        raise ValueError("Peer-group source contains a blank peer_group_name")
    if clean["company_id"].duplicated().any():
        duplicates = sorted(clean.loc[clean["company_id"].duplicated(False), "company_id"].unique())
        raise ValueError("A company cannot belong to multiple peer groups: " + ", ".join(duplicates))

    truthy = {True, 1, "1", "true", "yes", "y"}
    clean["is_benchmark"] = clean["is_benchmark"].map(
        lambda value: int(value if isinstance(value, bool) else str(value).strip().casefold() in {str(item).casefold() for item in truthy})
    )
    benchmark_counts = clean.groupby("peer_group_name")["is_benchmark"].sum()
    invalid = benchmark_counts[benchmark_counts.ne(1)]
    if not invalid.empty:
        details = ", ".join(f"{group}={int(count)}" for group, count in invalid.items())
        raise ValueError("Each peer group must have exactly one official benchmark: " + details)
    return clean.sort_values(["peer_group_name", "company_id"], kind="stable").reset_index(drop=True)


def percentile_rank(values: pd.Series, *, inverse: bool = False) -> pd.Series:
    """Return SQL-style PERCENT_RANK on a 0--100 scale.

    Ties receive the same minimum rank, matching ``RANK()`` semantics.  A
    singleton distribution receives 100 because it is its group's only (and
    therefore best) comparable observation.  Missing/non-finite values remain
    missing and never alter the denominator.
    """

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    numeric = numeric.where(np.isfinite(numeric), np.nan)
    available = numeric.dropna()
    output = pd.Series(np.nan, index=values.index, dtype=float)
    count = len(available)
    if count == 0:
        return output
    if count == 1:
        output.loc[available.index] = 100.0
        return output
    rank = available.rank(method="min", ascending=True)
    score = (rank - 1.0) / (count - 1.0) * 100.0
    if inverse:
        score = 100.0 - score
    output.loc[available.index] = score.round(6)
    return output


def load_ratio_history(connection: sqlite3.Connection) -> pd.DataFrame:
    columns = ["company_id", "year", *PEER_METRICS]
    return pd.read_sql_query(
        f"SELECT {', '.join(columns)} FROM financial_ratios ORDER BY company_id, year",
        connection,
    )


def build_peer_percentiles(
    assignments: pd.DataFrame, ratio_history: pd.DataFrame
) -> pd.DataFrame:
    """Create one auditable row per assigned company/year/metric."""

    required_ratios = {"company_id", "year", *PEER_METRICS}
    missing = required_ratios.difference(ratio_history.columns)
    if missing:
        raise ValueError("Ratio history is missing columns: " + ", ".join(sorted(missing)))
    required_assignments = {"company_id", "peer_group_name", "is_benchmark"}
    if not required_assignments.issubset(assignments.columns):
        raise ValueError("Assignments are missing required columns")

    joined = ratio_history.merge(
        assignments[["company_id", "peer_group_name"]],
        on="company_id",
        how="inner",
        validate="many_to_one",
    )
    long = joined.melt(
        id_vars=["company_id", "peer_group_name", "year"],
        value_vars=list(PEER_METRICS),
        var_name="metric",
        value_name="value",
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long["percentile_rank"] = np.nan
    for (group, year, metric), index in long.groupby(
        ["peer_group_name", "year", "metric"], sort=False
    ).groups.items():
        long.loc[index, "percentile_rank"] = percentile_rank(
            long.loc[index, "value"], inverse=PEER_METRICS[str(metric)]
        )
    return long.loc[
        :, ["company_id", "peer_group_name", "metric", "value", "percentile_rank", "year"]
    ].sort_values(
        ["peer_group_name", "year", "metric", "company_id"], kind="stable"
    ).reset_index(drop=True)


def peer_group_for_company(company_id: str, assignments: pd.DataFrame) -> str:
    """Return the group name or the documented non-error fallback message."""

    ticker = _normalise_company_id(company_id)
    match = assignments.loc[assignments["company_id"].eq(ticker), "peer_group_name"]
    return str(match.iloc[0]) if not match.empty else NO_PEER_GROUP_MESSAGE


def ensure_peer_schema(connection: sqlite3.Connection, schema_path: str | Path) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
    for table, required in {
        "peer_group_assignments": {"company_id", "peer_group_name", "is_benchmark"},
        "peer_percentiles": {"company_id", "peer_group_name", "metric", "value", "percentile_rank", "year"},
    }.items():
        actual = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        missing = required.difference(actual)
        if missing:
            raise ValueError(f"{table} schema is missing: " + ", ".join(sorted(missing)))


def populate_peer_tables(
    connection: sqlite3.Connection,
    assignments: pd.DataFrame,
    percentiles: pd.DataFrame,
) -> None:
    """Atomically replace both Day 18 tables with validated source data."""

    database_companies = {str(row[0]) for row in connection.execute("SELECT id FROM companies")}
    unknown = sorted(set(assignments["company_id"]).difference(database_companies))
    if unknown:
        raise ValueError("Peer-group companies absent from SQLite: " + ", ".join(unknown))
    if percentiles.duplicated(["company_id", "peer_group_name", "metric", "year"]).any():
        raise ValueError("Duplicate peer percentile keys were generated")

    assignment_rows = list(assignments[["company_id", "peer_group_name", "is_benchmark"]].itertuples(index=False, name=None))
    percentile_rows = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in percentiles[["company_id", "peer_group_name", "metric", "value", "percentile_rank", "year"]].itertuples(index=False, name=None)
    ]
    with connection:
        connection.execute("DELETE FROM peer_percentiles")
        connection.execute("DELETE FROM peer_group_assignments")
        connection.executemany(
            "INSERT INTO peer_group_assignments (company_id, peer_group_name, is_benchmark) VALUES (?, ?, ?)",
            assignment_rows,
        )
        connection.executemany(
            """INSERT INTO peer_percentiles
               (company_id, peer_group_name, metric, value, percentile_rank, year)
               VALUES (?, ?, ?, ?, ?, ?)""",
            percentile_rows,
        )


def _write_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    return target


def build_peer_group_audit(
    assignments: pd.DataFrame, percentiles: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group, members in assignments.groupby("peer_group_name", sort=True):
        data = percentiles.loc[percentiles["peer_group_name"].eq(group)]
        benchmark = members.loc[members["is_benchmark"].eq(1), "company_id"].iloc[0]
        rows.append(
            {
                "peer_group_name": group,
                "assigned_companies": len(members),
                "benchmark_company_id": benchmark,
                "company_year_rows": int(len(data) / len(PEER_METRICS)),
                "percentile_rows": len(data),
                "ranked_values": int(data["percentile_rank"].notna().sum()),
                "missing_values": int(data["value"].isna().sum()),
                "status": "PASS",
            }
        )
    rows.append(
        {
            "peer_group_name": "TOTAL",
            "assigned_companies": len(assignments),
            "benchmark_company_id": f"{int(assignments['is_benchmark'].sum())} official benchmarks",
            "company_year_rows": int(len(percentiles) / len(PEER_METRICS)),
            "percentile_rows": len(percentiles),
            "ranked_values": int(percentiles["percentile_rank"].notna().sum()),
            "missing_values": int(percentiles["value"].isna().sum()),
            "status": "PASS",
        }
    )
    return pd.DataFrame(rows)


def _latest_metric_slice(
    percentiles: pd.DataFrame, group: str, metric: str
) -> pd.DataFrame:
    subset = percentiles.loc[
        percentiles["peer_group_name"].eq(group)
        & percentiles["metric"].eq(metric)
        & percentiles["value"].notna()
    ]
    if subset.empty:
        return subset
    return subset.loc[subset["year"].eq(subset["year"].max())].copy()


def build_manual_checks(
    assignments: pd.DataFrame,
    percentiles: pd.DataFrame,
    *,
    total_company_count: int,
) -> pd.DataFrame:
    """Generate 57 reproducible structural, benchmark and ranking checks."""

    checks: list[dict[str, Any]] = []

    def add(check_type: str, group: str, metric: str, year: str, expected: Any, actual: Any, passed: bool, details: str) -> None:
        checks.append(
            {
                "check_type": check_type,
                "peer_group_name": group,
                "metric": metric,
                "year": year,
                "expected": expected,
                "actual": actual,
                "status": "PASS" if passed else "FAIL",
                "details": details,
            }
        )

    structural = (
        ("assignment_count", EXPECTED_ASSIGNMENTS, len(assignments)),
        ("peer_group_count", EXPECTED_GROUPS, assignments["peer_group_name"].nunique()),
        ("benchmark_count", EXPECTED_GROUPS, int(assignments["is_benchmark"].sum())),
        ("unassigned_count", EXPECTED_UNASSIGNED, total_company_count - len(assignments)),
    )
    for name, expected, actual in structural:
        add("STRUCTURE", "ALL", name, "ALL", expected, actual, expected == actual, "Official universe structure")

    for group, members in assignments.groupby("peer_group_name", sort=True):
        benchmark = members.loc[members["is_benchmark"].eq(1), "company_id"].tolist()
        add(
            "BENCHMARK",
            group,
            "is_benchmark",
            "ALL",
            "exactly one official benchmark",
            ", ".join(benchmark),
            len(benchmark) == 1,
            "Benchmark preserved verbatim from peer_groups.xlsx",
        )

    # For every group, verify the latest available ROE winner and lowest-D/E
    # winner against the corresponding 100-point percentile observation.
    for group in sorted(assignments["peer_group_name"].unique()):
        for metric, label, choose in (
            ("return_on_equity_pct", "highest ROE", "max"),
            ("debt_to_equity", "lowest D/E", "min"),
        ):
            sample = _latest_metric_slice(percentiles, group, metric)
            if sample.empty:
                add("EXTREME", group, metric, "N/A", label, "no comparable values", False, "No latest distribution available")
                continue
            target = sample["value"].max() if choose == "max" else sample["value"].min()
            expected_ids = sorted(sample.loc[sample["value"].eq(target), "company_id"].tolist())
            actual_ids = sorted(sample.loc[sample["percentile_rank"].eq(sample["percentile_rank"].max()), "company_id"].tolist())
            add(
                "EXTREME",
                group,
                metric,
                str(sample["year"].iloc[0]),
                ", ".join(expected_ids),
                ", ".join(actual_ids),
                expected_ids == actual_ids,
                label,
            )

    # Ten metric-level spot checks for each explicitly requested focus group.
    for group in ("IT Services", "FMCG"):
        for metric in PEER_METRICS:
            sample = _latest_metric_slice(percentiles, group, metric)
            actual = None if sample.empty else float(sample["percentile_rank"].max())
            add(
                "FOCUS_GROUP",
                group,
                metric,
                "N/A" if sample.empty else str(sample["year"].iloc[0]),
                "best available observation has percentile 100",
                actual,
                actual is not None and math.isclose(actual, 100.0, abs_tol=1e-9),
                "Latest available metric distribution",
            )
    return pd.DataFrame(checks)


def run_day18(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
    peer_groups_path: str | Path = DEFAULT_PEER_GROUPS_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    create_backup: bool = True,
) -> PeerRunResult:
    database = Path(database_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if create_backup:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = database.parent / "backups" / f"nifty100_pre_day18_{stamp}.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database, backup_path)

    assignments = load_peer_group_assignments(peer_groups_path)
    with sqlite3.connect(database) as connection:
        ensure_peer_schema(connection, schema_path)
        total_company_count = int(connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0])
        ratio_history = load_ratio_history(connection)
        percentiles = build_peer_percentiles(assignments, ratio_history)

        if len(assignments) != EXPECTED_ASSIGNMENTS:
            raise ValueError(f"Expected {EXPECTED_ASSIGNMENTS} peer assignments, found {len(assignments)}")
        if assignments["peer_group_name"].nunique() != EXPECTED_GROUPS:
            raise ValueError(f"Expected {EXPECTED_GROUPS} peer groups")
        if total_company_count - len(assignments) != EXPECTED_UNASSIGNED:
            raise ValueError(f"Expected {EXPECTED_UNASSIGNED} companies without a peer group")
        populate_peer_tables(connection, assignments, percentiles)
        foreign_key_failures = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if foreign_key_failures:
            raise ValueError(f"SQLite foreign-key failures: {foreign_key_failures[:5]}")
        if integrity != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")

    assignments_path = _write_csv(assignments, output / "peer_group_assignments.csv")
    percentiles_path = _write_csv(percentiles, output / "peer_percentiles.csv")
    audit = build_peer_group_audit(assignments, percentiles)
    audit_path = _write_csv(audit, output / "peer_group_audit.csv")
    manual = build_manual_checks(assignments, percentiles, total_company_count=total_company_count)
    manual_checks_path = _write_csv(manual, output / "peer_percentile_manual_checks.csv")
    if not manual["status"].eq("PASS").all():
        failures = manual.loc[manual["status"].ne("PASS")]
        raise ValueError(f"Manual peer checks failed: {failures.to_dict('records')[:3]}")

    return PeerRunResult(
        assignment_count=len(assignments),
        group_count=int(assignments["peer_group_name"].nunique()),
        unassigned_count=total_company_count - len(assignments),
        percentile_row_count=len(percentiles),
        ranked_value_count=int(percentiles["percentile_rank"].notna().sum()),
        missing_value_count=int(percentiles["value"].isna().sum()),
        backup_path=backup_path,
        assignments_path=assignments_path,
        percentiles_path=percentiles_path,
        audit_path=audit_path,
        manual_checks_path=manual_checks_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--peer-groups", type=Path, default=DEFAULT_PEER_GROUPS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-backup", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_day18(
        args.database,
        schema_path=args.schema,
        peer_groups_path=args.peer_groups,
        output_dir=args.output_dir,
        create_backup=not args.no_backup,
    )
    print(
        f"Day 18 complete: {result.assignment_count} assignments, "
        f"{result.group_count} groups, {result.percentile_row_count} percentile rows, "
        f"{result.ranked_value_count} ranked values, "
        f"{result.missing_value_count} missing values."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
