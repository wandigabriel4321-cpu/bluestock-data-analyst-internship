"""Tests for the Sprint 3 Day 16 official preset screeners."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from src.screener.presets import (
    EXPECTED_PRESET_KEYS,
    apply_preset,
    build_preset_outputs,
    evaluate_rule,
    load_preset_definitions,
    run_all_presets,
)
from src.screener.engine import ScreenerConfigError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"
DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"


def sample_universe() -> pd.DataFrame:
    defaults = {
        "company_name": "Sample",
        "broad_sector": "Industrials",
        "financial_year": "2024-03",
        "icr_label": None,
        "return_on_equity_pct": 10.0,
        "debt_to_equity": 1.5,
        "previous_debt_to_equity": 1.5,
        "free_cash_flow_cr": -1.0,
        "revenue_cagr_3yr": 5.0,
        "revenue_cagr_5yr": 5.0,
        "pat_cagr_5yr": 5.0,
        "operating_profit_margin_pct": 10.0,
        "pe_ratio": 25.0,
        "pb_ratio": 4.0,
        "dividend_yield_pct": 0.5,
        "interest_coverage": 2.0,
        "market_cap_crore": 1000.0,
        "net_profit": 100.0,
        "eps_cagr_5yr": 5.0,
        "asset_turnover": 1.0,
        "dividend_payout_ratio_pct": 90.0,
        "sales": 1000.0,
        "composite_quality_score": 50.0,
    }
    overrides = [
        {
            "company_id": "QUALITY",
            "return_on_equity_pct": 20,
            "debt_to_equity": 0.5,
            "free_cash_flow_cr": 10,
            "revenue_cagr_5yr": 12,
            "composite_quality_score": 90,
        },
        {
            "company_id": "VALUE",
            "pe_ratio": 15,
            "pb_ratio": 2,
            "debt_to_equity": 1,
            "dividend_yield_pct": 2,
        },
        {
            "company_id": "GROWTH",
            "pat_cagr_5yr": 25,
            "revenue_cagr_5yr": 20,
            "debt_to_equity": 1,
        },
        {
            "company_id": "DIVIDEND",
            "dividend_yield_pct": 3,
            "dividend_payout_ratio_pct": 60,
            "free_cash_flow_cr": 10,
        },
        {
            "company_id": "DEBTFREE",
            "debt_to_equity": 0,
            "return_on_equity_pct": 15,
            "sales": 6000,
        },
        {
            "company_id": "TURN",
            "revenue_cagr_3yr": 15,
            "free_cash_flow_cr": 10,
            "debt_to_equity": 1,
            "previous_debt_to_equity": 2,
        },
        {
            "company_id": "FINBANK",
            "broad_sector": "Financials",
            "return_on_equity_pct": 20,
            "debt_to_equity": 9,
            "free_cash_flow_cr": 10,
            "revenue_cagr_5yr": 12,
        },
    ]
    return pd.DataFrame([{**defaults, **row} for row in overrides])


class PresetDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = load_preset_definitions(CONFIG_PATH)

    def test_01_configuration_contains_exactly_six_official_presets(self):
        self.assertEqual(tuple(self.definitions), EXPECTED_PRESET_KEYS)

    def test_02_missing_official_preset_is_rejected(self):
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw["presets"].pop("value_pick")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            with self.assertRaisesRegex(ScreenerConfigError, "exactly six"):
                load_preset_definitions(path)

    def test_03_greater_than_and_less_than_are_strict_at_boundary(self):
        frame = sample_universe().iloc[[0]].copy()
        frame["return_on_equity_pct"] = 15
        frame["debt_to_equity"] = 1
        self.assertFalse(
            evaluate_rule(
                frame,
                {"column": "return_on_equity_pct", "operator": "gt", "threshold": 15},
            ).iloc[0]
        )
        self.assertFalse(
            evaluate_rule(
                frame,
                {"column": "debt_to_equity", "operator": "lt", "threshold": 1},
            ).iloc[0]
        )

    def test_04_financials_are_exempt_only_when_rule_requests_it(self):
        frame = sample_universe().query("company_id == 'FINBANK'")
        exempt = {
            "column": "debt_to_equity",
            "operator": "lt",
            "threshold": 1,
            "financials_exempt": True,
        }
        ordinary = {**exempt, "financials_exempt": False}
        self.assertTrue(evaluate_rule(frame, exempt).iloc[0])
        self.assertFalse(evaluate_rule(frame, ordinary).iloc[0])


class PresetLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = load_preset_definitions(CONFIG_PATH)
        cls.frame = sample_universe()

    def result_ids(self, key: str) -> list[str]:
        result, _ = apply_preset(self.frame, self.definitions[key])
        return result["company_id"].tolist()

    def test_05_quality_compounder_applies_all_four_rules(self):
        ids = self.result_ids("quality_compounder")
        self.assertIn("QUALITY", ids)
        self.assertIn("FINBANK", ids)
        self.assertNotIn("VALUE", ids)

    def test_06_value_pick_applies_valuation_yield_and_leverage(self):
        self.assertEqual(self.result_ids("value_pick"), ["VALUE"])

    def test_07_growth_accelerator_applies_both_cagrs_and_leverage(self):
        self.assertEqual(self.result_ids("growth_accelerator"), ["GROWTH"])

    def test_08_dividend_champion_applies_payout_yield_and_fcf(self):
        self.assertEqual(self.result_ids("dividend_champion"), ["DIVIDEND"])

    def test_09_debt_free_blue_chip_requires_exact_zero_debt(self):
        frame = self.frame.copy()
        frame.loc[frame["company_id"].eq("DEBTFREE"), "debt_to_equity"] = 1e-6
        result, _ = apply_preset(frame, self.definitions["debt_free_blue_chip"])
        self.assertNotIn("DEBTFREE", result["company_id"].tolist())

    def test_10_turnaround_watch_requires_declining_debt_to_equity(self):
        self.assertEqual(self.result_ids("turnaround_watch"), ["TURN"])

    def test_11_turnaround_missing_previous_debt_to_equity_fails(self):
        frame = self.frame.query("company_id == 'TURN'").copy()
        frame["previous_debt_to_equity"] = None
        result, _ = apply_preset(frame, self.definitions["turnaround_watch"])
        self.assertTrue(result.empty)

    def test_12_results_are_sorted_by_composite_score(self):
        result, _ = apply_preset(self.frame, self.definitions["quality_compounder"])
        self.assertEqual(result.iloc[0]["company_id"], "QUALITY")


class PresetOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = load_preset_definitions(CONFIG_PATH)

    def test_13_validation_report_contains_requested_fields(self):
        outputs = build_preset_outputs(
            sample_universe(), self.definitions, expected_universe=7
        )
        required = {
            "preset_name",
            "company_count",
            "thresholds_applied",
            "missing_values_total",
            "status",
        }
        self.assertTrue(required.issubset(outputs["validation"].columns))

    def test_14_manual_samples_recompute_every_rule_successfully(self):
        outputs = build_preset_outputs(
            sample_universe(),
            self.definitions,
            expected_min=1,
            expected_universe=7,
        )
        self.assertFalse(outputs["manual_checks"].empty)
        self.assertTrue(outputs["manual_checks"]["manual_status"].eq("PASS").all())

    def test_15_real_database_generates_all_reports_for_92_companies(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = run_all_presets(
                DATABASE_PATH, config_path=CONFIG_PATH, output_dir=directory
            )
            self.assertTrue(outputs["validation"]["universe_companies"].eq(92).all())
            self.assertEqual(len(outputs["validation"]), 6)
            for filename in (
                "preset_screener_results.csv",
                "preset_validation_report.csv",
                "preset_diagnostics.csv",
                "preset_manual_checks.csv",
            ):
                self.assertTrue((Path(directory) / filename).is_file())


if __name__ == "__main__":
    unittest.main()
