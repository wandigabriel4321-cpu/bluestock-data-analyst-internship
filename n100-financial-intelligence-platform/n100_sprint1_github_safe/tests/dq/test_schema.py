from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


class SQLiteSchemaTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.connection.close()

    def test_schema_preserves_sprint1_tables_and_adds_financial_ratios(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        expected = {
            "companies", "profitandloss", "balancesheet", "cashflow", "analysis",
            "documents", "prosandcons", "sectors", "market_cap", "stock_prices",
            "financial_ratios", "peer_group_assignments", "peer_percentiles",
        }
        self.assertEqual(tables, expected)
        self.assertEqual(self.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_financial_ratios_enforces_company_year_uniqueness_and_fk(self):
        self.connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (?, ?)", ("AAA", "Alpha")
        )
        self.connection.execute(
            """INSERT INTO financial_ratios
               (id, company_id, year, net_profit_margin_pct)
               VALUES (?, ?, ?, ?)""",
            (1, "AAA", "2024-03", 12.5),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO financial_ratios
                   (id, company_id, year, net_profit_margin_pct)
                   VALUES (?, ?, ?, ?)""",
                (2, "AAA", "2024-03", 14.0),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO financial_ratios
                   (id, company_id, year) VALUES (?, ?, ?)""",
                (3, "ZZZ", "2024-03"),
            )

    def test_schema_enforces_composite_primary_key_and_foreign_key(self):
        self.connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (?, ?)", ("AAA", "Alpha")
        )
        values = (1, "AAA", "2024-03", 100.0)
        self.connection.execute(
            "INSERT INTO profitandloss (id, company_id, year, sales) VALUES (?, ?, ?, ?)",
            values,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO profitandloss (id, company_id, year, sales) VALUES (?, ?, ?, ?)",
                (2, "AAA", "2024-03", 120.0),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO cashflow (id, company_id, year) VALUES (?, ?, ?)",
                (1, "ZZZ", "2024-03"),
            )


if __name__ == "__main__":
    unittest.main()
