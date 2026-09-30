"""Tests for reproducible sampling and Day 21 comparison helpers."""

from __future__ import annotations

import unittest

import pandas as pd

from src.etl.manual_review import (
    ManualReviewError,
    canonical_checksum,
    select_reproducible_sample,
    year_coverage,
)


class ManualReviewTests(unittest.TestCase):
    def test_sample_is_reproducible_and_order_independent(self) -> None:
        ids = ["DDD", "AAA", "CCC", "BBB", "EEE", "FFF"]
        first = select_reproducible_sample(ids, 5, "seed")
        second = select_reproducible_sample(reversed(ids), 5, "seed")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)

    def test_sample_rejects_insufficient_population(self) -> None:
        with self.assertRaises(ManualReviewError):
            select_reproducible_sample(["AAA"], 5, "seed")

    def test_checksum_treats_equivalent_numeric_types_as_equal(self) -> None:
        source = pd.DataFrame({"id": pd.Series([1.0], dtype="Float64"), "value": [5.5]})
        database = pd.DataFrame({"id": [1], "value": [5.5]})
        self.assertEqual(
            canonical_checksum(source, ("id",)),
            canonical_checksum(database, ("id",)),
        )

    def test_year_coverage_flags_less_than_five_years(self) -> None:
        companies = pd.DataFrame([{"id": "AAA", "company_name": "A Ltd"}])
        four_years = pd.DataFrame({
            "company_id": ["AAA"] * 4,
            "year": ["2021-03", "2022-03", "2023-03", "2024-03"],
        })
        coverage = year_coverage({
            "companies": companies,
            "profitandloss": four_years,
            "balancesheet": four_years,
            "cashflow": four_years,
        })
        self.assertEqual(set(coverage["coverage_status"]), {"REVIEW"})


if __name__ == "__main__":
    unittest.main()
