"""Unit and integration tests for the Sprint 2 Day 12 ratio orchestrator."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analytics.ratio_engine import (
    MANDATORY_KPI_COLUMNS,
    apply_composite_quality_scores,
    book_value_per_share,
    build_financial_ratio_rows,
    company_year_universe,
    populate_financial_ratios,
    validate_ratio_rows,
    write_null_audit,
)


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def complete_row(company_id: str, year: str) -> dict[str, object]:
    row: dict[str, object] = {
        "company_id": company_id,
        "year": year,
        "broad_sector": "Industrials",
        "is_financials": 0,
        "opm_mismatch_flag": 0,
    }
    row.update({column: 1.0 for column in MANDATORY_KPI_COLUMNS})
    return row


class RatioEngineTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.connection.close()

    def test_01_book_value_per_share_uses_face_value(self):
        self.assertAlmostEqual(book_value_per_share(20, 780, 10), 400.0)

    def test_02_book_value_per_share_rejects_invalid_share_base(self):
        self.assertIsNone(book_value_per_share(0, 780, 10))
        self.assertIsNone(book_value_per_share(20, 780, 0))

    def test_03_company_year_universe_is_a_distinct_union(self):
        self.connection.execute(
            "INSERT INTO companies (id, company_name) VALUES ('AAA', 'Alpha')"
        )
        self.connection.execute(
            "INSERT INTO profitandloss (id, company_id, year) VALUES (1, 'AAA', '2023-03')"
        )
        self.connection.execute(
            "INSERT INTO balancesheet (id, company_id, year) VALUES (1, 'AAA', '2023-03')"
        )
        self.connection.execute(
            "INSERT INTO cashflow (id, company_id, year) VALUES (1, 'AAA', '2024-03')"
        )
        self.assertEqual(
            company_year_universe(self.connection),
            [("AAA", "2023-03"), ("AAA", "2024-03")],
        )

    def test_04_composite_score_is_bounded_and_rewards_quality(self):
        rows = [
            {
                "return_on_equity_pct": value,
                "free_cash_flow_cr": value,
                "return_on_capital_employed_pct": value,
                "debt_to_equity": 11 - value,
            }
            for value in range(1, 11)
        ]
        scored = apply_composite_quality_scores(rows)
        self.assertGreater(
            scored[-1]["composite_quality_score"],
            scored[0]["composite_quality_score"],
        )
        self.assertTrue(
            all(0 <= row["composite_quality_score"] <= 100 for row in scored)
        )

    def test_05_composite_score_preserves_missing_component(self):
        rows = [
            {
                "return_on_equity_pct": 20,
                "free_cash_flow_cr": 100,
                "return_on_capital_employed_pct": 15,
                "debt_to_equity": 1,
            },
            {
                "return_on_equity_pct": 20,
                "free_cash_flow_cr": None,
                "return_on_capital_employed_pct": 15,
                "debt_to_equity": 1,
            },
        ]
        scored = apply_composite_quality_scores(rows)
        self.assertIsNotNone(scored[0]["composite_quality_score"])
        self.assertIsNone(scored[1]["composite_quality_score"])

    def test_06_exit_gate_accepts_1104_rows_and_92_companies(self):
        rows = [
            complete_row(f"C{company:02d}", f"{2013 + year:04d}-03")
            for company in range(92)
            for year in range(12)
        ]
        result = validate_ratio_rows(rows)
        self.assertEqual(result["row_count"], 1104)
        self.assertEqual(result["company_count"], 92)
        self.assertEqual(result["mandatory_all_null_columns"], [])

    def test_07_exit_gate_rejects_completely_empty_required_column(self):
        rows = [
            complete_row(f"C{company:02d}", f"{2013 + year:04d}-03")
            for company in range(92)
            for year in range(12)
        ]
        for row in rows:
            row["composite_quality_score"] = None
        with self.assertRaisesRegex(ValueError, "composite_quality_score"):
            validate_ratio_rows(rows)

    def test_08_build_rows_calculates_documented_metrics(self):
        self.connection.execute(
            """INSERT INTO companies
               (id, company_name, face_value) VALUES ('AAA', 'Alpha', 10)"""
        )
        self.connection.execute(
            """INSERT INTO sectors
               (id, company_id, broad_sector) VALUES (1, 'AAA', 'Industrials')"""
        )
        self.connection.execute(
            """INSERT INTO profitandloss
               (id, company_id, year, sales, operating_profit, opm_percentage,
                other_income, interest, depreciation, net_profit, eps,
                dividend_payout)
               VALUES (1, 'AAA', '2024-03', 1000, 200, 20, 10, 5, 20,
                       100, 50, 25)"""
        )
        self.connection.execute(
            """INSERT INTO balancesheet
               (id, company_id, year, equity_capital, reserves, borrowings,
                investments, total_assets)
               VALUES (1, 'AAA', '2024-03', 20, 780, 200, 50, 2000)"""
        )
        self.connection.execute(
            """INSERT INTO cashflow
               (id, company_id, year, operating_activity, investing_activity,
                financing_activity)
               VALUES (1, 'AAA', '2024-03', 150, -40, -30)"""
        )
        rows = build_financial_ratio_rows(self.connection)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["net_profit_margin_pct"], 10.0)
        self.assertAlmostEqual(rows[0]["book_value_per_share"], 400.0)
        self.assertAlmostEqual(rows[0]["free_cash_flow_cr"], 110.0)
        self.assertIsNotNone(rows[0]["composite_quality_score"])

    def test_09_database_population_is_idempotent(self):
        self.connection.execute(
            "INSERT INTO companies (id, company_name) VALUES ('AAA', 'Alpha')"
        )
        rows = [complete_row("AAA", "2024-03")]
        with patch("src.analytics.ratio_engine.MINIMUM_EXPECTED_ROWS", 1), patch(
            "src.analytics.ratio_engine.EXPECTED_COMPANIES", 1
        ):
            populate_financial_ratios(self.connection, rows)
            populate_financial_ratios(self.connection, rows)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM financial_ratios"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_10_null_audit_marks_required_columns(self):
        rows = [complete_row("AAA", "2024-03")]
        with tempfile.TemporaryDirectory() as directory:
            path = write_null_audit(rows, Path(directory) / "null_audit.csv")
            text = path.read_text(encoding="utf-8")
        self.assertIn("composite_quality_score,True,1,0,100.0,PASS", text)


if __name__ == "__main__":
    unittest.main()
