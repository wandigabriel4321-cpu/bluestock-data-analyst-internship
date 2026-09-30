"""Unit tests for Sprint 2 Day 11 cash-flow KPIs."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analytics.cashflow_kpis import (
    LABEL_ACCRUAL_RISK,
    LABEL_ASSET_LIGHT,
    LABEL_CAPITAL_INTENSIVE,
    LABEL_HIGH_QUALITY,
    LABEL_MODERATE,
    PATTERN_ASSET_SALE_SURVIVAL,
    PATTERN_CASH_ACCUMULATOR,
    PATTERN_DISTRESS_SIGNAL,
    PATTERN_GROWTH_FUNDED_BY_DEBT,
    PATTERN_LIQUIDATING_ASSETS,
    PATTERN_MIXED,
    PATTERN_PRE_REVENUE,
    PATTERN_REINVESTOR,
    PATTERN_SHAREHOLDER_RETURNS,
    assess_five_year_cfo_quality,
    capex_intensity,
    cashflow_sign,
    cfo_pat_ratio,
    classify_capex_intensity,
    classify_capital_allocation,
    classify_cfo_quality,
    fcf_conversion_rate,
    free_cash_flow,
    write_capital_allocation,
)


def annual_row(
    year: str,
    *,
    cfo: float | None = 100,
    cfi: float | None = -20,
    cff: float | None = -10,
    pat: float | None = 80,
    sales: float | None = 500,
    operating_profit: float | None = 125,
    company_id: str = "AAA",
) -> dict[str, object]:
    return {
        "company_id": company_id,
        "year": year,
        "operating_activity": cfo,
        "investing_activity": cfi,
        "financing_activity": cff,
        "net_profit": pat,
        "sales": sales,
        "operating_profit": operating_profit,
    }


class CashFlowKPITests(unittest.TestCase):
    def test_01_free_cash_flow_allows_positive_and_negative_results(self):
        self.assertEqual(free_cash_flow(100, -40), 60.0)
        self.assertEqual(free_cash_flow(100, -140), -40.0)

    def test_02_free_cash_flow_rejects_missing_components(self):
        self.assertIsNone(free_cash_flow(None, -40))
        self.assertIsNone(free_cash_flow(100, None))

    def test_03_cfo_pat_ratio_and_zero_pat(self):
        self.assertEqual(cfo_pat_ratio(120, 80), 1.5)
        self.assertIsNone(cfo_pat_ratio(120, 0))

    def test_04_cfo_quality_thresholds(self):
        self.assertEqual(classify_cfo_quality(1.01), LABEL_HIGH_QUALITY)
        self.assertEqual(classify_cfo_quality(1.0), LABEL_MODERATE)
        self.assertEqual(classify_cfo_quality(0.5), LABEL_MODERATE)
        self.assertEqual(classify_cfo_quality(0.49), LABEL_ACCRUAL_RISK)

    def test_05_five_year_cfo_quality_uses_exact_consecutive_years(self):
        rows = [
            annual_row(f"{year}-03", cfo=120, pat=100)
            for year in range(2020, 2025)
        ]
        result = assess_five_year_cfo_quality(list(reversed(rows)))
        self.assertAlmostEqual(result.average_ratio, 1.2)
        self.assertEqual(result.label, LABEL_HIGH_QUALITY)
        self.assertEqual(result.years_used, 5)
        self.assertEqual(result.start_year, "2020-03")

    def test_06_five_year_quality_rejects_partial_history(self):
        rows = [annual_row(f"{year}-03") for year in range(2021, 2025)]
        result = assess_five_year_cfo_quality(rows)
        self.assertIsNone(result.average_ratio)
        self.assertIsNone(result.label)
        self.assertEqual(result.years_used, 4)

    def test_07_zero_pat_invalidates_five_year_average(self):
        rows = [
            annual_row(f"{year}-03", pat=0 if year == 2022 else 100)
            for year in range(2020, 2025)
        ]
        result = assess_five_year_cfo_quality(rows)
        self.assertIsNone(result.average_ratio)
        self.assertEqual(result.years_used, 4)

    def test_08_capex_intensity_uses_absolute_cfi(self):
        self.assertAlmostEqual(capex_intensity(-40, 1000), 4.0)

    def test_09_capex_intensity_rejects_invalid_sales(self):
        self.assertIsNone(capex_intensity(-40, 0))
        self.assertIsNone(capex_intensity(-40, -1000))

    def test_10_capex_intensity_classification_boundaries(self):
        self.assertEqual(classify_capex_intensity(2.99), LABEL_ASSET_LIGHT)
        self.assertEqual(classify_capex_intensity(3.0), LABEL_MODERATE)
        self.assertEqual(classify_capex_intensity(8.0), LABEL_MODERATE)
        self.assertEqual(
            classify_capex_intensity(8.01), LABEL_CAPITAL_INTENSIVE
        )

    def test_11_fcf_conversion_and_zero_operating_profit(self):
        self.assertAlmostEqual(fcf_conversion_rate(100, -40, 120), 50.0)
        self.assertIsNone(fcf_conversion_rate(100, -40, 0))

    def test_12_cashflow_sign_maps_zero_to_nonnegative_bin(self):
        self.assertEqual(cashflow_sign(10), "+")
        self.assertEqual(cashflow_sign(0), "+")
        self.assertEqual(cashflow_sign(-0.01), "-")
        self.assertIsNone(cashflow_sign(None))

    def test_13_all_eight_sign_combinations_have_labels(self):
        cases = {
            (1, 1, 1): PATTERN_CASH_ACCUMULATOR,
            (1, 1, -1): PATTERN_LIQUIDATING_ASSETS,
            (1, -1, 1): PATTERN_MIXED,
            (1, -1, -1): PATTERN_REINVESTOR,
            (-1, 1, 1): PATTERN_DISTRESS_SIGNAL,
            (-1, 1, -1): PATTERN_ASSET_SALE_SURVIVAL,
            (-1, -1, 1): PATTERN_GROWTH_FUNDED_BY_DEBT,
            (-1, -1, -1): PATTERN_PRE_REVENUE,
        }
        for values, expected in cases.items():
            with self.subTest(values=values):
                self.assertEqual(classify_capital_allocation(*values), expected)

    def test_14_high_quality_positive_negative_negative_is_shareholder_returns(self):
        self.assertEqual(
            classify_capital_allocation(
                100, -50, -20, cfo_pat_5yr_average=1.2
            ),
            PATTERN_SHAREHOLDER_RETURNS,
        )

    def test_15_missing_cashflow_component_is_not_eligible(self):
        self.assertIsNone(classify_capital_allocation(None, -50, -20))

    def test_16_capital_allocation_csv_has_required_columns_and_no_blank_label(self):
        rows = [
            annual_row("2023-03", cfo=100, cfi=-50, cff=-20),
            annual_row("2024-03", cfo=-10, cfi=20, cff=-5),
            annual_row("2022-03", cfo=None, cfi=None, cff=None),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = write_capital_allocation(
                rows, Path(directory) / "capital_allocation.csv"
            )
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                output = list(reader)
                columns = reader.fieldnames
        self.assertEqual(
            columns,
            ["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"],
        )
        self.assertEqual(len(output), 2)
        self.assertTrue(all(row["pattern_label"] for row in output))


if __name__ == "__main__":
    unittest.main()
