from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.etl.validator import DataQualityValidator, write_validation_outputs


def base_tables() -> dict[str, pd.DataFrame]:
    years = [f"{year}-03" for year in range(2020, 2025)]
    companies = pd.DataFrame([
        {"id": "AAA", "company_name": "Alpha Ltd"},
    ])
    profitandloss = pd.DataFrame([
        {
            "id": number,
            "company_id": "AAA",
            "year": year,
            "sales": 100.0,
            "expenses": 90.0,
            "operating_profit": 10.0,
            "opm_percentage": 10.0,
            "tax_percentage": 25.0,
            "net_profit": 5.0,
            "eps": 1.0,
            "dividend_payout": 10.0,
        }
        for number, year in enumerate(years, 1)
    ])
    balancesheet = pd.DataFrame([
        {
            "id": number,
            "company_id": "AAA",
            "year": year,
            "fixed_assets": 100.0,
            "total_liabilities": 1000.0,
            "total_assets": 1000.0,
        }
        for number, year in enumerate(years, 1)
    ])
    cashflow = pd.DataFrame([
        {
            "id": number,
            "company_id": "AAA",
            "year": year,
            "operating_activity": 100.0,
            "investing_activity": -30.0,
            "financing_activity": -20.0,
            "net_cash_flow": 50.0,
        }
        for number, year in enumerate(years, 1)
    ])
    sectors = pd.DataFrame([
        {"id": 1, "company_id": "AAA", "broad_sector": "Industrials", "sub_sector": "Capital Goods"}
    ])
    documents = pd.DataFrame([
        {"id": 1, "company_id": "AAA", "year": "2024-03", "annual_report": "https://example.com/report.pdf"}
    ])
    return {
        "companies": companies,
        "profitandloss": profitandloss,
        "balancesheet": balancesheet,
        "cashflow": cashflow,
        "sectors": sectors,
        "documents": documents,
    }


class DataQualityRuleTests(unittest.TestCase):
    def test_01_dq01_duplicate_company_pk_blocks_load(self):
        tables = base_tables()
        tables["companies"] = pd.concat([tables["companies"], tables["companies"]], ignore_index=True)
        result = DataQualityValidator(tables).validate()
        self.assertTrue(result.load_blocked)
        self.assertEqual(len(result.failures_for("DQ-01")), 2)

    def test_02_dq02_keeps_last_annual_duplicate(self):
        tables = base_tables()
        duplicate = tables["profitandloss"].iloc[[0]].copy()
        duplicate["id"] = 999
        tables["profitandloss"] = pd.concat([tables["profitandloss"], duplicate], ignore_index=True)
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-02")), 1)
        kept = result.tables["profitandloss"].query("year == '2020-03'")
        self.assertEqual(kept.iloc[0]["id"], 999)

    def test_03_dq03_rejects_orphan(self):
        tables = base_tables()
        orphan = tables["profitandloss"].iloc[[0]].copy()
        orphan["id"], orphan["company_id"], orphan["year"] = 999, "ZZZ", "2019-03"
        tables["profitandloss"] = pd.concat([tables["profitandloss"], orphan], ignore_index=True)
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-03")), 1)
        self.assertNotIn("ZZZ", set(result.tables["profitandloss"]["company_id"]))

    def test_04_dq04_flags_balance_difference_over_one_percent(self):
        tables = base_tables()
        tables["balancesheet"].loc[0, "total_liabilities"] = 1020.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-04")), 1)
        self.assertEqual(result.failures_for("DQ-04")[0].severity, "WARNING")

    def test_05_dq05_flags_opm_difference(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "opm_percentage"] = 20.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-05")), 1)

    def test_06_dq06_flags_non_bank_non_positive_sales(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "sales"] = 0.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-06")), 1)

    def test_07_dq07_rejects_invalid_year(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "year"] = "PARSE_ERROR"
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-07")), 1)
        self.assertNotIn("PARSE_ERROR", set(result.tables["profitandloss"]["year"]))

    def test_08_dq08_rejects_invalid_ticker(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "company_id"] = "X"
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-08")), 1)
        self.assertNotIn("X", set(result.tables["profitandloss"]["company_id"]))

    def test_09_dq09_recomputes_mismatched_net_cash(self):
        tables = base_tables()
        tables["cashflow"].loc[0, "net_cash_flow"] = 100.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-09")), 1)
        self.assertEqual(result.tables["cashflow"].loc[0, "net_cash_flow"], 50.0)

    def test_10_dq10_coerces_negative_fixed_assets(self):
        tables = base_tables()
        tables["balancesheet"].loc[0, "fixed_assets"] = -10.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-10")), 1)
        self.assertEqual(result.tables["balancesheet"].loc[0, "fixed_assets"], 0.0)

    def test_11_dq11_flags_tax_rate_outside_range(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "tax_percentage"] = 80.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-11")), 1)

    def test_12_dq12_flags_dividend_payout_over_cap(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "dividend_payout"] = 250.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-12")), 1)

    def test_13_dq13_flags_missing_or_malformed_url(self):
        tables = base_tables()
        tables["documents"].loc[0, "annual_report"] = "not-a-url"
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-13")), 1)

    def test_14_dq13_uses_http_head_status_when_enabled(self):
        tables = base_tables()
        result = DataQualityValidator(
            tables, check_urls=True, url_checker=lambda _url: 404
        ).validate()
        self.assertEqual(result.failures_for("DQ-13")[0].observed_value, 404)

    def test_15_dq14_flags_positive_profit_with_nonpositive_eps(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "eps"] = 0.0
        result = DataQualityValidator(tables).validate()
        self.assertEqual(len(result.failures_for("DQ-14")), 1)

    def test_16_dq15_records_strict_balance_counter(self):
        result = DataQualityValidator(base_tables()).validate()
        self.assertEqual(result.audit["DQ-15.strict_balance_matches"], 5)
        self.assertEqual(result.audit["DQ-15.strict_balance_mismatches"], 0)

    def test_17_dq16_flags_companies_with_less_than_five_years(self):
        tables = base_tables()
        tables["companies"] = pd.concat([
            tables["companies"], pd.DataFrame([{"id": "BBB", "company_name": "Beta Ltd"}])
        ], ignore_index=True)
        result = DataQualityValidator(tables).validate()
        failures = [f for f in result.failures_for("DQ-16") if f.company_id == "BBB"]
        self.assertEqual(len(failures), 3)
        self.assertTrue(all("exclude company from CAGR" in f.action for f in failures))

    def test_18_writes_validation_failure_and_summary_csv(self):
        tables = base_tables()
        tables["profitandloss"].loc[0, "tax_percentage"] = 80.0
        result = DataQualityValidator(tables).validate()
        with tempfile.TemporaryDirectory() as directory:
            failure_path, summary_path = write_validation_outputs(result, directory)
            failures = pd.read_csv(failure_path)
            summary = pd.read_csv(summary_path)
            self.assertIn("DQ-11", set(failures["rule_id"]))
            self.assertIn("critical_failures", set(summary["metric"]))


if __name__ == "__main__":
    unittest.main()
