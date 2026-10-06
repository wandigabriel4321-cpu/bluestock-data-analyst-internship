"""Tests for the Sprint 2 Day 14 final review helpers."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.analytics.sprint2_review import (
    Sprint2ReviewError,
    audit_edge_case_log,
    build_screener_rows,
    manual_cagr,
    manual_roe,
    select_reproducible_ids,
)


class Sprint2ReviewTests(unittest.TestCase):
    def test_01_manual_roe_uses_profit_and_total_equity(self) -> None:
        self.assertAlmostEqual(manual_roe(20, 25, 75), 20.0)

    def test_02_manual_roe_rejects_nonpositive_capital_base(self) -> None:
        self.assertIsNone(manual_roe(20, 25, -25))

    def test_03_manual_cagr_uses_exact_elapsed_years(self) -> None:
        self.assertAlmostEqual(manual_cagr(100, 161.051, 5), 10.0, places=4)

    def test_04_manual_cagr_rejects_nonpositive_values(self) -> None:
        self.assertIsNone(manual_cagr(0, 100, 5))
        self.assertIsNone(manual_cagr(100, -1, 5))

    def test_05_sample_is_reproducible_and_order_independent(self) -> None:
        ids = ["DDD", "AAA", "CCC", "BBB", "EEE", "FFF"]
        first = select_reproducible_ids(ids, 5, "seed")
        second = select_reproducible_ids(reversed(ids), 5, "seed")
        self.assertEqual(first, second)

    def test_06_sample_rejects_insufficient_eligible_companies(self) -> None:
        with self.assertRaises(Sprint2ReviewError):
            select_reproducible_ids(["AAA"], 5, "seed")

    def test_07_edge_case_audit_rejects_blank_explanations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "edge.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("company_id", "year", "category", "metric", "detail"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "company_id": "AAA",
                        "year": "2024-03",
                        "category": "TEST",
                        "metric": "roe",
                        "detail": "",
                    }
                )
            result = audit_edge_case_log(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["unexplained_entries"], 1)

    def test_08_screener_uses_latest_calculable_company_row(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE companies (id TEXT PRIMARY KEY, company_name TEXT);
            CREATE TABLE financial_ratios (
                company_id TEXT,
                year TEXT,
                broad_sector TEXT,
                return_on_equity_pct REAL,
                debt_to_equity REAL
            );
            INSERT INTO companies VALUES ('AAA', 'A Ltd'), ('BBB', 'B Ltd');
            INSERT INTO financial_ratios VALUES
                ('AAA', '2023-03', 'Industrials', 20, 0.5),
                ('AAA', '2024-03', 'Industrials', 14, 0.4),
                ('BBB', '2024-03', 'Industrials', 25, 0.8);
            """
        )
        try:
            rows = build_screener_rows(connection)
        finally:
            connection.close()
        self.assertEqual([row["company_id"] for row in rows], ["BBB"])


if __name__ == "__main__":
    unittest.main()
