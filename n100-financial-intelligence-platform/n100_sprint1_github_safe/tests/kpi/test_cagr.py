"""Unit tests for Sprint 2 Day 10 CAGR engine."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analytics.cagr import (
    FLAG_BOTH_NEGATIVE,
    FLAG_DECLINE_TO_LOSS,
    FLAG_INSUFFICIENT,
    FLAG_OK,
    FLAG_TURNAROUND,
    FLAG_ZERO_BASE,
    calculate_cagr,
    calculate_company_cagrs,
    calculate_dataset_cagrs,
    calculate_window_cagr,
    sort_annual_records,
    write_cagr_audit,
)


def annual_row(
    year: str,
    sales: float | None,
    net_profit: float | None,
    eps: float | None,
    *,
    company_id: str = "AAA",
) -> dict[str, object]:
    return {
        "company_id": company_id,
        "year": year,
        "sales": sales,
        "net_profit": net_profit,
        "eps": eps,
    }


class CAGRTests(unittest.TestCase):
    def test_01_positive_to_positive_is_calculated(self):
        result = calculate_cagr(100, 133.1, 3)
        self.assertAlmostEqual(result.value, 10.0, places=8)
        self.assertEqual(result.flag, FLAG_OK)

    def test_02_positive_to_negative_is_decline_to_loss(self):
        result = calculate_cagr(100, -10, 3)
        self.assertIsNone(result.value)
        self.assertEqual(result.flag, FLAG_DECLINE_TO_LOSS)

    def test_03_negative_to_positive_is_turnaround(self):
        result = calculate_cagr(-100, 10, 3)
        self.assertIsNone(result.value)
        self.assertEqual(result.flag, FLAG_TURNAROUND)

    def test_04_negative_to_negative_is_not_calculated(self):
        result = calculate_cagr(-100, -50, 3)
        self.assertIsNone(result.value)
        self.assertEqual(result.flag, FLAG_BOTH_NEGATIVE)

    def test_05_zero_base_has_explicit_flag(self):
        result = calculate_cagr(0, 100, 3)
        self.assertIsNone(result.value)
        self.assertEqual(result.flag, FLAG_ZERO_BASE)

    def test_06_missing_value_is_insufficient(self):
        self.assertEqual(calculate_cagr(None, 100, 3).flag, FLAG_INSUFFICIENT)
        self.assertEqual(calculate_cagr(100, None, 3).flag, FLAG_INSUFFICIENT)

    def test_07_years_are_sorted_chronologically(self):
        rows = [
            annual_row("2024-03", 133.1, 40, 4),
            annual_row("2021-03", 100, 30, 3),
            annual_row("2023-03", 121, 35, 3.5),
        ]
        ordered = sort_annual_records(rows)
        self.assertEqual(
            [row["year"] for row in ordered],
            ["2021-03", "2023-03", "2024-03"],
        )

    def test_08_window_uses_exact_elapsed_years_not_row_position(self):
        rows = [
            annual_row("2022-03", 105, 30, 3),
            annual_row("2024-03", 133.1, 40, 4),
            annual_row("2021-03", 100, 25, 2.5),
        ]
        result = calculate_window_cagr(rows, "sales", 3)
        self.assertEqual(result.start_year, "2021-03")
        self.assertEqual(result.end_year, "2024-03")
        self.assertAlmostEqual(result.value, 10.0, places=8)

    def test_09_missing_exact_window_is_insufficient(self):
        rows = [
            annual_row("2020-03", 80, 20, 2),
            annual_row("2022-03", 100, 25, 2.5),
            annual_row("2024-03", 120, 30, 3),
        ]
        result = calculate_window_cagr(rows, "sales", 3)
        self.assertIsNone(result.value)
        self.assertEqual(result.flag, FLAG_INSUFFICIENT)

    def test_10_revenue_cagr_is_created_for_3_5_and_10_years(self):
        rows = [
            annual_row(f"{year}-03", 100 * (1.1 ** (year - 2014)), 10, 1)
            for year in range(2014, 2025)
        ]
        output = calculate_company_cagrs(list(reversed(rows)))
        for window in (3, 5, 10):
            self.assertAlmostEqual(output[f"revenue_cagr_{window}yr"], 10.0)
            self.assertEqual(output[f"revenue_cagr_{window}yr_flag"], FLAG_OK)

    def test_11_pat_and_eps_negative_cases_keep_flags_separate(self):
        rows = [
            annual_row("2021-03", 100, 20, -2),
            annual_row("2024-03", 120, -5, 3),
        ]
        output = calculate_company_cagrs(rows, windows=(3,))
        self.assertIsNone(output["pat_cagr_3yr"])
        self.assertEqual(output["pat_cagr_3yr_flag"], FLAG_DECLINE_TO_LOSS)
        self.assertIsNone(output["eps_cagr_3yr"])
        self.assertEqual(output["eps_cagr_3yr_flag"], FLAG_TURNAROUND)

    def test_12_all_nine_values_have_separate_flag_columns(self):
        rows = [
            annual_row(f"{year}-03", year, year, year)
            for year in range(2014, 2025)
        ]
        output = calculate_company_cagrs(rows)
        value_columns = [
            key
            for key in output
            if "_cagr_" in key and not key.endswith("_flag")
        ]
        self.assertEqual(len(value_columns), 9)
        self.assertTrue(all(f"{key}_flag" in output for key in value_columns))

    def test_13_dataset_is_grouped_and_sorted_by_company(self):
        rows = [
            annual_row("2021-03", 100, 10, 1, company_id="ZZZ"),
            annual_row("2024-03", 120, 12, 1.2, company_id="ZZZ"),
            annual_row("2021-03", 50, 5, 0.5, company_id="AAA"),
            annual_row("2024-03", 60, 6, 0.6, company_id="AAA"),
        ]
        output = calculate_dataset_cagrs(rows)
        self.assertEqual([row["company_id"] for row in output], ["AAA", "ZZZ"])

    def test_14_duplicate_reporting_year_is_rejected(self):
        rows = [annual_row("2024-03", 100, 10, 1)] * 2
        with self.assertRaisesRegex(ValueError, "Duplicate reporting year"):
            sort_annual_records(rows)

    def test_15_invalid_period_and_year_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cagr(100, 120, 0)
        with self.assertRaises(ValueError):
            sort_annual_records([annual_row("2024-13", 100, 10, 1)])

    def test_16_csv_audit_preserves_value_and_flag_columns(self):
        rows = [
            annual_row("2021-03", 100, 10, -1),
            annual_row("2024-03", 133.1, -2, 1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = write_cagr_audit(rows, Path(directory) / "cagr.csv")
            with path.open(encoding="utf-8", newline="") as handle:
                output = list(csv.DictReader(handle))
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["revenue_cagr_3yr_flag"], FLAG_OK)
        self.assertEqual(output[0]["pat_cagr_3yr_flag"], FLAG_DECLINE_TO_LOSS)
        self.assertEqual(output[0]["eps_cagr_3yr_flag"], FLAG_TURNAROUND)


if __name__ == "__main__":
    unittest.main()
