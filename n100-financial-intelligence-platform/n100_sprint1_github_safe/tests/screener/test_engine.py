"""Tests for the Sprint 3 Day 15 filter engine."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.screener.engine import (
    ScreenerConfigError,
    apply_filters,
    load_latest_company_metrics,
    load_screener_config,
    run_screener,
    validate_filters,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "company_id": "AAA",
                "company_name": "Alpha",
                "broad_sector": "Technology",
                "icr_label": None,
                "return_on_equity_pct": 20.0,
                "debt_to_equity": 0.5,
                "interest_coverage": 4.0,
                "free_cash_flow_cr": 100.0,
                "composite_quality_score": 70.0,
            },
            {
                "company_id": "BBB",
                "company_name": "Beta",
                "broad_sector": "Technology",
                "icr_label": "Debt Free",
                "return_on_equity_pct": 18.0,
                "debt_to_equity": 0.0,
                "interest_coverage": None,
                "free_cash_flow_cr": 50.0,
                "composite_quality_score": 90.0,
            },
            {
                "company_id": "CCC",
                "company_name": "Capital Bank",
                "broad_sector": " Financials ",
                "icr_label": None,
                "return_on_equity_pct": 16.0,
                "debt_to_equity": 8.0,
                "interest_coverage": 1.0,
                "free_cash_flow_cr": -10.0,
                "composite_quality_score": 80.0,
            },
            {
                "company_id": "DDD",
                "company_name": "Delta",
                "broad_sector": "Energy",
                "icr_label": None,
                "return_on_equity_pct": None,
                "debt_to_equity": None,
                "interest_coverage": None,
                "free_cash_flow_cr": None,
                "composite_quality_score": 60.0,
            },
        ]
    )


class ScreenerConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_screener_config(CONFIG_PATH)

    def test_01_configuration_defines_exactly_fifteen_filterable_metrics(self):
        self.assertEqual(len(self.config["metrics"]), 15)

    def test_02_unknown_metric_is_rejected(self):
        with self.assertRaisesRegex(ScreenerConfigError, "Unknown screener metric"):
            validate_filters({"not_a_metric": 1}, self.config["metrics"])

    def test_03_non_numeric_and_boolean_thresholds_are_rejected(self):
        for invalid in ("15", True, float("inf"), float("nan")):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ScreenerConfigError):
                    validate_filters({"roe_min": invalid}, self.config["metrics"])

    def test_04_invalid_configuration_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
            with self.assertRaisesRegex(ScreenerConfigError, "root must be a mapping"):
                load_screener_config(path)

    def test_05_invalid_metric_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text(
                "metrics:\n  wrong:\n    column: imaginary\n    direction: min\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ScreenerConfigError, "unsupported"):
                load_screener_config(path)


class ScreenerFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = load_screener_config(CONFIG_PATH)["metrics"]

    def test_06_multiple_filters_are_applied_simultaneously(self):
        result = apply_filters(
            sample_frame(),
            {"roe_min": 17, "fcf_min": 0},
            self.metrics,
        )
        self.assertEqual(result["company_id"].tolist(), ["BBB", "AAA"])

    def test_07_results_are_sorted_by_composite_score_descending(self):
        result = apply_filters(sample_frame(), {}, self.metrics)
        self.assertEqual(result["company_id"].tolist(), ["BBB", "CCC", "AAA", "DDD"])

    def test_08_missing_value_fails_only_a_filter_that_requires_it(self):
        all_companies = apply_filters(sample_frame(), {}, self.metrics)
        filtered = apply_filters(sample_frame(), {"roe_min": 0}, self.metrics)
        self.assertIn("DDD", all_companies["company_id"].tolist())
        self.assertNotIn("DDD", filtered["company_id"].tolist())

    def test_09_debt_free_label_passes_any_icr_minimum(self):
        result = apply_filters(
            sample_frame(), {"interest_coverage_min": 1000}, self.metrics
        )
        self.assertEqual(result["company_id"].tolist(), ["BBB"])

    def test_10_numeric_interest_coverage_is_enforced(self):
        result = apply_filters(
            sample_frame(), {"interest_coverage_min": 2}, self.metrics
        )
        self.assertEqual(result["company_id"].tolist(), ["BBB", "AAA"])

    def test_11_financials_are_exempt_from_common_de_maximum(self):
        result = apply_filters(sample_frame(), {"de_max": 1}, self.metrics)
        self.assertEqual(result["company_id"].tolist(), ["BBB", "CCC", "AAA"])

    def test_12_nonfinancial_company_must_meet_de_maximum(self):
        frame = sample_frame()
        frame.loc[frame["company_id"] == "AAA", "debt_to_equity"] = 2.0
        result = apply_filters(frame, {"de_max": 1}, self.metrics)
        self.assertNotIn("AAA", result["company_id"].tolist())
        self.assertIn("CCC", result["company_id"].tolist())

    def test_13_zero_is_preserved_as_a_real_value(self):
        result = apply_filters(sample_frame(), {"de_max": 0}, self.metrics)
        self.assertIn("BBB", result["company_id"].tolist())


class ScreenerDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "test.db"
        with sqlite3.connect(self.database) as connection:
            connection.executescript(
                """
                CREATE TABLE companies (
                    id TEXT PRIMARY KEY, company_name TEXT NOT NULL
                );
                CREATE TABLE sectors (
                    id INTEGER PRIMARY KEY, company_id TEXT,
                    broad_sector TEXT, sub_sector TEXT
                );
                CREATE TABLE financial_ratios (
                    id INTEGER PRIMARY KEY, company_id TEXT, year TEXT,
                    broad_sector TEXT, return_on_equity_pct REAL,
                    debt_to_equity REAL, free_cash_flow_cr REAL,
                    revenue_cagr_3yr REAL, revenue_cagr_5yr REAL, pat_cagr_5yr REAL,
                    operating_profit_margin_pct REAL, interest_coverage REAL,
                    icr_label TEXT, eps_cagr_5yr REAL, asset_turnover REAL,
                    dividend_payout_ratio_pct REAL,
                    composite_quality_score REAL,
                    return_on_capital_employed_pct REAL,
                    net_profit_margin_pct REAL,
                    cfo_pat_ratio_5yr REAL
                );
                CREATE TABLE market_cap (
                    id INTEGER PRIMARY KEY, company_id TEXT, year TEXT,
                    pe_ratio REAL, pb_ratio REAL, dividend_yield_pct REAL,
                    market_cap_crore REAL
                );
                CREATE TABLE profitandloss (
                    id INTEGER, company_id TEXT, year TEXT,
                    net_profit REAL, sales REAL
                );
                INSERT INTO companies VALUES ('AAA', 'Alpha');
                INSERT INTO sectors VALUES (1, 'AAA', 'Technology', 'IT Services');
                INSERT INTO financial_ratios VALUES
                    (1, 'AAA', '2023-03', 'Technology', 10, 1, 5, 1, 2, 3, 4, 5, NULL, 6, 7, 25, 40, 11, 12, 1.1),
                    (2, 'AAA', '2024-03', 'Technology', 20, 0.5, 10, 3, 4, 5, 6, 7, NULL, 8, 9, 20, 80, 21, 22, 1.2),
                    (3, 'AAA', '2024-09', 'Technology', NULL, 0.4, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
                INSERT INTO market_cap VALUES
                    (1, 'AAA', '2022-03', 30, 4, 1, 100),
                    (2, 'AAA', '2024-09', 20, 3, 2, 200);
                INSERT INTO profitandloss VALUES
                    (1, 'AAA', '2021-03', 10, 100),
                    (2, 'AAA', '2024-06', 20, 200);
                """
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_14_latest_substantive_row_is_selected_independently_per_table(self):
        frame = load_latest_company_metrics(self.database)
        row = frame.iloc[0]
        self.assertEqual(row["financial_year"], "2024-03")
        self.assertEqual(row["market_cap_year"], "2024-09")
        self.assertEqual(row["profitandloss_year"], "2024-06")
        self.assertEqual(row["return_on_equity_pct"], 20)
        self.assertEqual(row["market_cap_crore"], 200)
        self.assertEqual(row["sales"], 200)
        self.assertEqual(row["previous_financial_year"], "2023-03")
        self.assertEqual(row["previous_debt_to_equity"], 1)

    def test_15_run_screener_uses_custom_filters(self):
        result = run_screener(
            self.database,
            filters={"roe_min": 15, "pe_max": 25},
            config_path=CONFIG_PATH,
        )
        self.assertEqual(result["company_id"].tolist(), ["AAA"])


if __name__ == "__main__":
    unittest.main()
