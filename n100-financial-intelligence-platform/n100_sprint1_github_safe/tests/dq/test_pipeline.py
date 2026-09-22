"""Tests for the atomic Day 20 database pipeline."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.etl.loader import DATASET_SPECS, LoadResult
from src.etl.pipeline import (
    REFERENCE_TABLES,
    SPRINT1_TABLE_ORDER,
    DatabaseLoadResult,
    PipelineError,
    build_load_audit,
    create_database,
)
from src.etl.validator import ValidationResult


ROOT = Path(__file__).resolve().parents[2]


def minimal_tables() -> dict[str, pd.DataFrame]:
    """Return one FK-consistent row for every Sprint 1 table."""
    return {
        "companies": pd.DataFrame([{"id": "ABC", "company_name": "ABC Ltd"}]),
        "profitandloss": pd.DataFrame([{
            "id": 1, "company_id": "ABC", "year": "2025-03", "sales": 10.0,
        }]),
        "balancesheet": pd.DataFrame([{
            "id": 2, "company_id": "ABC", "year": "2025-03",
            "total_assets": 5.0, "total_liabilities": 5.0,
        }]),
        "cashflow": pd.DataFrame([{
            "id": 3, "company_id": "ABC", "year": "2025-03",
            "net_cash_flow": 1.0,
        }]),
        "analysis": pd.DataFrame([{"id": 4, "company_id": "ABC"}]),
        "documents": pd.DataFrame([{
            "id": 5, "company_id": "ABC", "year": "2025-03",
        }]),
        "prosandcons": pd.DataFrame([{"id": 6, "company_id": "ABC"}]),
        "sectors": pd.DataFrame([{
            "id": 7, "company_id": "ABC", "broad_sector": "Technology",
        }]),
        "market_cap": pd.DataFrame([{
            "id": 8, "company_id": "ABC", "year": "2025-03",
        }]),
        "stock_prices": pd.DataFrame([{
            "id": 9, "company_id": "ABC", "date": "2025-09-20",
        }]),
    }


class PipelineDatabaseTests(unittest.TestCase):
    def test_create_database_loads_in_fk_safe_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "nifty100.db"
            result = create_database(
                minimal_tables(), ROOT / "db/schema.sql", database_path
            )

            self.assertEqual(result.integrity_check, "ok")
            self.assertEqual(result.foreign_key_violations, 0)
            self.assertEqual(result.row_counts, {name: 1 for name in SPRINT1_TABLE_ORDER})
            with sqlite3.connect(database_path) as connection:
                self.assertEqual(connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall(), [])

    def test_create_database_replaces_previous_database_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "nifty100.db"
            database_path.write_text("old placeholder", encoding="utf-8")
            create_database(minimal_tables(), ROOT / "db/schema.sql", database_path)

            with sqlite3.connect(database_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            self.assertEqual(count, 1)
            self.assertFalse(list(Path(directory).glob("*.pending.db")))

    def test_create_database_rejects_missing_table(self) -> None:
        tables = minimal_tables()
        tables.pop("companies")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PipelineError):
                create_database(
                    tables, ROOT / "db/schema.sql", Path(directory) / "nifty100.db"
                )

    def test_load_audit_contains_all_twelve_sources_and_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = []
            paths = {}
            for spec in DATASET_SPECS:
                source = root / spec.source_name
                source.write_bytes(spec.source_name.encode("utf-8"))
                paths[spec.table_name] = source
                results.append(LoadResult(
                    spec.source_name, spec.table_name, pd.DataFrame({"x": [1]})
                ))
            empty = ValidationResult({}, [], {}, False)
            database = DatabaseLoadResult(
                {name: 1 for name in SPRINT1_TABLE_ORDER}, 0, "ok"
            )

            audit = build_load_audit(results, paths, empty, empty, database, "run")

            self.assertEqual(len(audit), 13)
            self.assertEqual(audit.iloc[-1]["source_file"], "TOTAL")
            self.assertEqual(int(audit.iloc[-1]["source_rows"]), 12)
            reference = audit[audit["table_name"].isin(REFERENCE_TABLES)]
            self.assertEqual(set(reference["load_status"]), {"REFERENCE_ONLY"})
            self.assertEqual(int(reference["rows_loaded_to_db"].sum()), 0)


if __name__ == "__main__":
    unittest.main()
