"""Reproducible Day 21 source-to-database manual review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.etl.loader import ExcelLoader
from src.etl.pipeline import SPRINT1_TABLE_ORDER
from src.etl.validator import ANNUAL_TABLES, DataQualityValidator


DEFAULT_SAMPLE_SEED = "20260921"
TABLE_KEYS = {
    "companies": ("id",),
    "profitandloss": ("company_id", "year"),
    "balancesheet": ("company_id", "year"),
    "cashflow": ("company_id", "year"),
    "analysis": ("id",),
    "documents": ("id",),
    "prosandcons": ("id",),
    "sectors": ("id",),
    "market_cap": ("id",),
    "stock_prices": ("id",),
}


class ManualReviewError(RuntimeError):
    """Raised when the final review cannot be completed safely."""


def select_reproducible_sample(
    company_ids: Iterable[str], sample_size: int = 5, seed: str = DEFAULT_SAMPLE_SEED
) -> list[str]:
    """Select stable IDs by ranking SHA-256(seed:company_id)."""
    unique = sorted({str(company_id) for company_id in company_ids})
    if len(unique) < sample_size:
        raise ManualReviewError(
            f"Cannot sample {sample_size} companies from {len(unique)} IDs"
        )
    ranked = sorted(
        unique,
        key=lambda company_id: (
            hashlib.sha256(f"{seed}:{company_id}".encode("utf-8")).hexdigest(),
            company_id,
        ),
    )
    return ranked[:sample_size]


def _canonical_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 8)
    return str(value)


def canonical_records(frame: pd.DataFrame, keys: Iterable[str]) -> list[dict[str, Any]]:
    """Return consistently ordered, JSON-safe records for comparison."""
    columns = list(frame.columns)
    available_keys = [key for key in keys if key in columns]
    ordered = frame.sort_values(available_keys, kind="stable") if available_keys else frame
    return [
        {column: _canonical_value(row[column]) for column in columns}
        for _, row in ordered.reset_index(drop=True).iterrows()
    ]


def canonical_checksum(frame: pd.DataFrame, keys: Iterable[str]) -> str:
    payload = json.dumps(
        canonical_records(frame, keys), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def year_coverage(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    companies = tables["companies"][["id", "company_name"]].copy()
    rows: list[dict[str, Any]] = []
    for _, company in companies.sort_values("id").iterrows():
        company_id = str(company["id"])
        for table_name in ANNUAL_TABLES:
            frame = tables[table_name]
            company_rows = frame[frame["company_id"].astype(str).eq(company_id)]
            years = sorted(company_rows["year"].dropna().astype(str).unique())
            rows.append({
                "company_id": company_id,
                "company_name": company["company_name"],
                "table_name": table_name,
                "unique_year_count": len(years),
                "first_year": years[0] if years else "",
                "last_year": years[-1] if years else "",
                "years": " | ".join(years),
                "coverage_status": "PASS" if len(years) >= 5 else "REVIEW",
                "coverage_note": (
                    "At least five reporting years available"
                    if len(years) >= 5
                    else "Fewer than five reporting years; exclude from CAGR when below three"
                ),
            })
    return pd.DataFrame(rows)


def _filter_company(frame: pd.DataFrame, table_name: str, company_id: str) -> pd.DataFrame:
    column = "id" if table_name == "companies" else "company_id"
    return frame[frame[column].astype(str).eq(company_id)].copy()


def run_manual_review(
    *,
    database_path: str | Path = "db/nifty100.db",
    raw_dir: str | Path = "data/raw",
    supporting_dir: str | Path = "data/supporting",
    output_dir: str | Path = "output",
    seed: str = DEFAULT_SAMPLE_SEED,
    sample_size: int = 5,
) -> tuple[Path, Path, Path]:
    """Compare five sampled companies from source through the final database."""
    database = Path(database_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="n100_manual_review_") as temporary:
        loader = ExcelLoader(Path(temporary))
        results, failures = loader.load_directories(
            (raw_dir, supporting_dir), maximum_sprint=1, strict_schema=True
        )
        if failures:
            raise ManualReviewError(f"Source reload failed: {failures}")
        raw_tables = {result.table_name: result.dataframe for result in results}
        loader_errors = (
            pd.read_csv(loader.error_path) if loader.error_path.exists() else pd.DataFrame()
        )
        validated = DataQualityValidator(
            raw_tables, loader_errors=loader_errors
        ).validate().tables

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        database_tables = {
            table_name: pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)
            for table_name in SPRINT1_TABLE_ORDER
        }

    sample = select_reproducible_sample(
        database_tables["companies"]["id"], sample_size=sample_size, seed=seed
    )
    names = database_tables["companies"].set_index("id")["company_name"].to_dict()
    coverage = year_coverage(database_tables)
    coverage_lookup = coverage.set_index(["company_id", "table_name"])

    review_rows: list[dict[str, Any]] = []
    for rank, company_id in enumerate(sample, 1):
        for table_name in SPRINT1_TABLE_ORDER:
            raw_frame = _filter_company(raw_tables[table_name], table_name, company_id)
            expected = _filter_company(validated[table_name], table_name, company_id)
            actual = _filter_company(database_tables[table_name], table_name, company_id)
            # Align the DB frame to the documented source column order.
            actual = actual.loc[:, list(expected.columns)]
            keys = TABLE_KEYS[table_name]
            expected_checksum = canonical_checksum(expected, keys)
            actual_checksum = canonical_checksum(actual, keys)
            match = expected_checksum == actual_checksum
            coverage_count: int | str = ""
            coverage_status = "NOT_APPLICABLE"
            year_range = ""
            if table_name in ANNUAL_TABLES:
                coverage_row = coverage_lookup.loc[(company_id, table_name)]
                coverage_count = int(coverage_row["unique_year_count"])
                coverage_status = str(coverage_row["coverage_status"])
                year_range = f"{coverage_row['first_year']} to {coverage_row['last_year']}"
            review_rows.append({
                "sample_seed": seed,
                "sample_rank": rank,
                "company_id": company_id,
                "company_name": names.get(company_id, ""),
                "table_name": table_name,
                "original_source_rows": len(raw_frame),
                "expected_rows_after_dq": len(expected),
                "database_rows": len(actual),
                "rows_removed_by_dq": len(raw_frame) - len(expected),
                "source_checksum_after_dq": expected_checksum,
                "database_checksum": actual_checksum,
                "source_database_match": "PASS" if match else "FAIL",
                "unique_year_count": coverage_count,
                "year_range": year_range,
                "coverage_status": coverage_status,
                "foreign_key_check": "PASS" if not foreign_key_rows else "FAIL",
                "review_status": "PASS" if match and not foreign_key_rows else "FAIL",
                "review_note": (
                    "Validated source values match the published database"
                    if match else "Source-to-database mismatch requires investigation"
                ),
            })

    review = pd.DataFrame(review_rows)
    review_path = destination / "manual_review.csv"
    review.to_csv(review_path, index=False)

    limited = coverage[coverage["coverage_status"].eq("REVIEW")].reset_index(drop=True)
    limited_path = destination / "limited_year_coverage.csv"
    limited.to_csv(limited_path, index=False)

    summary = {
        "sample_method": "Five lowest SHA-256(seed:company_id) rankings",
        "sample_seed": seed,
        "sample_size": sample_size,
        "selected_companies": sample,
        "table_comparisons": len(review),
        "source_database_matches": int(review["source_database_match"].eq("PASS").sum()),
        "source_database_mismatches": int(review["source_database_match"].eq("FAIL").sum()),
        "companies_with_limited_coverage": sorted(limited["company_id"].unique()),
        "limited_coverage_findings": len(limited),
        "foreign_key_violations": len(foreign_key_rows),
        "manual_review_status": (
            "PASS"
            if review["review_status"].eq("PASS").all() and not foreign_key_rows
            else "FAIL"
        ),
    }
    summary_path = destination / "manual_review_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return review_path, limited_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible N100 manual review")
    parser.add_argument("--database", type=Path, default=Path("db/nifty100.db"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--supporting-dir", type=Path, default=Path("data/supporting"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--seed", default=DEFAULT_SAMPLE_SEED)
    parser.add_argument("--sample-size", type=int, default=5)
    args = parser.parse_args()
    review, coverage, summary = run_manual_review(
        database_path=args.database,
        raw_dir=args.raw_dir,
        supporting_dir=args.supporting_dir,
        output_dir=args.output_dir,
        seed=args.seed,
        sample_size=args.sample_size,
    )
    print(f"Manual review: {review}")
    print(f"Limited coverage: {coverage}")
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
