"""Structural checks for the Day 21 exploratory SQL file."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.analytics.run_queries import parse_queries


ROOT = Path(__file__).resolve().parents[2]


class ExploratoryQueryTests(unittest.TestCase):
    def test_sql_file_contains_exactly_ten_numbered_queries(self) -> None:
        queries = parse_queries(ROOT / "notebooks/exploratory_queries.sql")
        self.assertEqual(len(queries), 10)
        self.assertEqual(
            [query["number"] for query in queries],
            [f"{number:02d}" for number in range(1, 11)],
        )


if __name__ == "__main__":
    unittest.main()
