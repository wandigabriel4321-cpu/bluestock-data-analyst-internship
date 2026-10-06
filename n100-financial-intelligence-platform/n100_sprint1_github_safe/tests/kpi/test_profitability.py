"""Unit tests for Sprint 2 Day 08 profitability ratios."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analytics.ratios import (
    cross_check_operating_profit_margin,
    is_financial_sector,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
    safe_divide,
    write_opm_mismatch_log,
)


class ProfitabilityRatioTests(unittest.TestCase):
    def test_01_safe_divide_returns_none_for_zero_denominator(self):
        self.assertIsNone(safe_divide(10, 0))

    def test_02_net_profit_margin_normal_case(self):
        self.assertAlmostEqual(net_profit_margin(25, 200), 12.5)

    def test_03_net_profit_margin_returns_none_for_zero_sales(self):
        self.assertIsNone(net_profit_margin(25, 0))

    def test_04_operating_profit_margin_normal_case(self):
        self.assertAlmostEqual(operating_profit_margin(36, 240), 15.0)

    def test_05_opm_difference_at_or_below_one_point_is_not_flagged(self):
        result = cross_check_operating_profit_margin(20, 100, 19.0)
        self.assertAlmostEqual(result.difference_pct_points, 1.0)
        self.assertFalse(result.exceeds_tolerance)

    def test_06_opm_difference_above_one_point_is_flagged(self):
        result = cross_check_operating_profit_margin(
            20, 100, 17.5, company_id="AAA", year="2024-03"
        )
        self.assertAlmostEqual(result.difference_pct_points, 2.5)
        self.assertTrue(result.exceeds_tolerance)

    def test_07_opm_mismatch_log_contains_only_flagged_rows(self):
        checks = [
            cross_check_operating_profit_margin(20, 100, 19.5),
            cross_check_operating_profit_margin(
                20, 100, 17.5, company_id="AAA", year="2024-03"
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = write_opm_mismatch_log(
                checks, Path(directory) / "opm_mismatches.csv"
            )
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company_id"], "AAA")
        self.assertEqual(rows[0]["year"], "2024-03")

    def test_08_return_on_equity_normal_case(self):
        self.assertAlmostEqual(return_on_equity(30, 100, 50), 20.0)

    def test_09_return_on_equity_returns_none_for_nonpositive_equity(self):
        self.assertIsNone(return_on_equity(30, -100, 50))
        self.assertIsNone(return_on_equity(30, -50, 50))

    def test_10_return_on_assets_returns_none_for_zero_assets(self):
        self.assertIsNone(return_on_assets(30, 0))

    def test_11_return_on_capital_employed_normal_case(self):
        self.assertAlmostEqual(
            return_on_capital_employed(40, 100, 50, 50), 20.0
        )

    def test_12_financial_sector_identification_is_normalised(self):
        self.assertTrue(is_financial_sector(" Financials "))
        self.assertFalse(is_financial_sector("Industrials"))
        self.assertFalse(is_financial_sector(None))


if __name__ == "__main__":
    unittest.main()
