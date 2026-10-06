from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.analytics.sprint3_review import (
    DEFAULT_DATABASE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PEER_WORKBOOK,
    DEFAULT_RADAR_DIR,
    DEFAULT_SCREENER_WORKBOOK,
    OFFICIAL_GROUP_ORDER,
    RADAR_SAMPLE,
    database_quality_checks,
    excel_review,
    peer_manual_review,
    quality_compounder_review,
    radar_sample_review,
)


class DatabaseQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checks = database_quality_checks()
        cls.actual = dict(zip(cls.checks["check"], cls.checks["actual"]))

    def test_01_sqlite_integrity_check_is_ok(self):
        self.assertEqual(self.actual["PRAGMA integrity_check"], "ok")

    def test_02_foreign_key_check_has_no_rows(self):
        self.assertEqual(self.actual["PRAGMA foreign_key_check"], 0)

    def test_03_company_universe_is_92(self):
        self.assertEqual(self.actual["companies"], 92)

    def test_04_financial_ratios_has_at_least_1100_rows(self):
        self.assertGreaterEqual(self.actual["financial_ratios rows"], 1100)

    def test_05_financial_ratios_represents_all_92_companies(self):
        self.assertEqual(self.actual["financial_ratios companies"], 92)

    def test_06_peer_assignments_has_56_companies(self):
        self.assertEqual(self.actual["peer assignments"], 56)

    def test_07_peer_assignments_has_11_groups(self):
        self.assertEqual(self.actual["peer groups"], 11)

    def test_08_every_group_has_one_benchmark(self):
        self.assertEqual(self.actual["peer benchmarks"], 11)

    def test_09_peer_percentiles_has_expected_rows(self):
        self.assertEqual(self.actual["peer percentile rows"], 7060)

    def test_10_percentiles_are_bounded_zero_to_one_hundred(self):
        self.assertEqual(self.actual["invalid percentile ranks"], 0)


class QualityCompounderReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = quality_compounder_review()

    def test_11_exactly_five_top_results_are_reviewed(self):
        self.assertEqual(len(self.review), 5)

    def test_12_reviewed_companies_are_unique(self):
        self.assertEqual(self.review["company_id"].nunique(), 5)

    def test_13_results_are_sorted_by_sprint3_score(self):
        scores = self.review["sprint3_composite_score"].tolist()
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_14_every_reviewed_company_has_roe_above_15(self):
        self.assertTrue(self.review["roe_rule_pass"].all())

    def test_15_nonfinancial_companies_have_de_below_one(self):
        nonfinancial = self.review["broad_sector"].str.casefold().ne("financials")
        self.assertTrue(self.review.loc[nonfinancial, "debt_to_equity"].lt(1).all())

    def test_16_every_reviewed_company_has_positive_fcf(self):
        self.assertTrue(self.review["fcf_rule_pass"].all())

    def test_17_every_reviewed_company_has_revenue_cagr_above_10(self):
        self.assertTrue(self.review["revenue_cagr_rule_pass"].all())

    def test_18_all_top_five_manual_checks_pass(self):
        self.assertTrue(self.review["manual_status"].eq("PASS").all())


class PeerQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = peer_manual_review()

    def test_19_all_peer_manual_checks_pass(self):
        self.assertTrue(self.review["status"].eq("PASS").all())

    def _extreme(self, group, metric):
        return self.review.loc[
            self.review["check_type"].eq("EXTREME")
            & self.review["peer_group_name"].eq(group)
            & self.review["metric"].eq(metric)
        ].iloc[0]

    def test_20_it_services_highest_roe_is_tcs(self):
        self.assertEqual(self._extreme("IT Services", "return_on_equity_pct")["actual"], "TCS")

    def test_21_it_services_lowest_de_is_techm(self):
        self.assertEqual(self._extreme("IT Services", "debt_to_equity")["actual"], "TECHM")

    def test_22_fmcg_highest_roe_is_nestleind(self):
        self.assertEqual(self._extreme("FMCG", "return_on_equity_pct")["actual"], "NESTLEIND")

    def test_23_fmcg_lowest_de_is_itc(self):
        self.assertEqual(self._extreme("FMCG", "debt_to_equity")["actual"], "ITC")

    def test_24_de_percentile_inversion_is_pairwise_monotonic(self):
        checks = self.review.loc[self.review["check_type"].eq("D_E_INVERSION")]
        self.assertGreater(len(checks), 0)
        self.assertTrue(checks["status"].eq("PASS").all())

    def test_25_exactly_36_companies_have_no_official_group(self):
        with sqlite3.connect(DEFAULT_DATABASE) as connection:
            count = connection.execute(
                """SELECT COUNT(*) FROM companies c
                   WHERE NOT EXISTS (
                       SELECT 1 FROM peer_group_assignments p
                       WHERE p.company_id = c.id
                   )"""
            ).fetchone()[0]
        self.assertEqual(count, 36)


class ExcelQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = excel_review(visual_confirmed=False)
        cls.screener = cls.review.loc[cls.review["workbook"].eq("screener_output.xlsx")]
        cls.peer = cls.review.loc[cls.review["workbook"].eq("peer_comparison.xlsx")]

    def test_26_screener_workbook_has_exactly_six_sheets(self):
        self.assertEqual(len(self.screener), 6)

    def test_27_every_screener_sheet_is_nonempty(self):
        self.assertTrue(self.screener["data_rows"].gt(0).all())

    def test_28_every_screener_sheet_has_twenty_kpis(self):
        workbook = load_workbook(DEFAULT_SCREENER_WORKBOOK, read_only=True)
        for worksheet in workbook.worksheets:
            headers = {str(cell.value) for cell in worksheet[1]}
            from src.screener.excel_report import KPI_COLUMNS
            self.assertEqual(len(set(KPI_COLUMNS).intersection(headers)), 20)

    def test_29_peer_workbook_has_exactly_eleven_sheets(self):
        self.assertEqual(tuple(self.peer["sheet_name"]), OFFICIAL_GROUP_ORDER)

    def test_30_peer_workbook_represents_56_companies(self):
        self.assertEqual(int(self.peer["data_rows"].sum()), 56)

    def test_31_every_peer_sheet_has_benchmark_and_median(self):
        self.assertTrue(self.peer["structural_status"].eq("PASS").all())

    def test_32_all_seventeen_sheets_pass_structural_review(self):
        self.assertEqual(len(self.review), 17)
        self.assertTrue(self.review["structural_status"].eq("PASS").all())


class RadarQualityTests(unittest.TestCase):
    def test_33_radar_audit_has_92_passed_charts(self):
        audit = pd.read_csv(DEFAULT_OUTPUT_DIR / "radar_chart_audit.csv")
        self.assertEqual(len(audit), 92)
        self.assertTrue(audit["status"].eq("PASS").all())
        self.assertEqual(audit["filename"].nunique(), 92)

    def test_34_radar_reference_split_is_56_peer_and_36_nifty(self):
        audit = pd.read_csv(DEFAULT_OUTPUT_DIR / "radar_chart_audit.csv")
        peer = audit["peer_group_name"].ne("No peer group assigned").sum()
        self.assertEqual((peer, len(audit) - peer), (56, 36))

    def test_35_visual_sample_files_are_nonempty_and_high_resolution(self):
        review = radar_sample_review(visual_confirmed=False)
        self.assertEqual(tuple(review["company_id"]), RADAR_SAMPLE)
        self.assertTrue(review["automated_status"].eq("PASS").all())
        self.assertTrue(review["file_size_bytes"].gt(0).all())


if __name__ == "__main__":
    unittest.main()
