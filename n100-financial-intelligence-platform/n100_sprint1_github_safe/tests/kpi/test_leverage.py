"""Unit tests for Sprint 2 Day 09 leverage and efficiency ratios."""

from __future__ import annotations

import unittest

from src.analytics.ratios import (
    assess_interest_coverage,
    asset_turnover,
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_label,
    interest_coverage_ratio,
    interest_coverage_warning,
    net_debt,
)


class LeverageEfficiencyTests(unittest.TestCase):
    def test_01_debt_to_equity_normal_case(self):
        self.assertAlmostEqual(debt_to_equity(150, 100, 50), 1.0)

    def test_02_debt_free_company_returns_zero(self):
        self.assertEqual(debt_to_equity(0, 100, 50), 0.0)
        self.assertEqual(debt_to_equity(0, 0, 0), 0.0)

    def test_03_debt_to_equity_rejects_nonpositive_equity_base(self):
        self.assertIsNone(debt_to_equity(100, 0, 0))
        self.assertIsNone(debt_to_equity(100, -100, 50))

    def test_04_high_leverage_flag_for_nonfinancial_company(self):
        self.assertTrue(high_leverage_flag(5.01, "Industrials"))

    def test_05_high_leverage_flag_is_suppressed_for_financials(self):
        self.assertFalse(high_leverage_flag(25.0, " Financials "))

    def test_06_high_leverage_boundary_is_not_flagged(self):
        self.assertFalse(high_leverage_flag(5.0, "Energy"))
        self.assertFalse(high_leverage_flag(None, "Energy"))

    def test_07_interest_coverage_normal_case(self):
        self.assertAlmostEqual(interest_coverage_ratio(100, 20, 10), 12.0)

    def test_08_zero_interest_returns_none_and_debt_free_label(self):
        result = assess_interest_coverage(100, 20, 0, borrowings=0)
        self.assertIsNone(result.ratio)
        self.assertEqual(result.label, "Debt Free")
        self.assertFalse(result.warning_flag)

    def test_09_zero_interest_with_debt_is_not_mislabeled(self):
        self.assertIsNone(interest_coverage_label(0, borrowings=100))

    def test_10_interest_coverage_below_one_point_five_is_warning(self):
        ratio = interest_coverage_ratio(10, 0, 10)
        self.assertAlmostEqual(ratio, 1.0)
        self.assertTrue(interest_coverage_warning(ratio))

    def test_11_interest_coverage_boundary_is_not_warning(self):
        self.assertFalse(interest_coverage_warning(1.5))
        self.assertFalse(interest_coverage_warning(None))

    def test_12_net_debt_uses_investments_as_liquid_asset_proxy(self):
        self.assertAlmostEqual(net_debt(500, 125), 375.0)
        self.assertAlmostEqual(net_debt(100, 150), -50.0)

    def test_13_net_debt_rejects_missing_values(self):
        self.assertIsNone(net_debt(None, 100))
        self.assertIsNone(net_debt(100, None))

    def test_14_asset_turnover_normal_case(self):
        self.assertAlmostEqual(asset_turnover(750, 500), 1.5)

    def test_15_asset_turnover_rejects_nonpositive_assets(self):
        self.assertIsNone(asset_turnover(750, 0))
        self.assertIsNone(asset_turnover(750, -500))

    def test_16_invalid_thresholds_are_rejected(self):
        with self.assertRaises(ValueError):
            high_leverage_flag(6.0, "Energy", threshold=-1)
        with self.assertRaises(ValueError):
            interest_coverage_warning(1.0, threshold=-1)


if __name__ == "__main__":
    unittest.main()
