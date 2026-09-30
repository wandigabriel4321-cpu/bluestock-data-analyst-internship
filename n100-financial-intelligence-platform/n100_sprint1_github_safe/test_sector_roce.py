"""Tests for Sprint 2 Day 13 Financials treatment and anomaly review."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.analytics.ratios import (
    FINANCIAL_ENTITY_BANK,
    FINANCIAL_ENTITY_INSURANCE,
    FINANCIAL_ENTITY_NBFC,
    FINANCIAL_ENTITY_OTHER,
    NON_FINANCIAL_ENTITY,
    classify_financial_entity,
    high_leverage_flag,
    uses_financial_leverage_treatment,
)
from src.analytics.sector_roce import (
    CLASS_FORMULA_DIFFERENCE,
    CLASS_INSUFFICIENT_HISTORY,
    CLASS_SOURCE_PROBLEM,
    CLASS_VERSION_DIFFERENCE,
    CLASS_WITHIN_TOLERANCE,
    SECTOR_NOTE_COLUMNS,
    build_financial_sector_notes,
    classify_reference_difference,
    sector_note_edge_cases,
    write_sector_roce_notes,
)


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


class SectorROCETests(unittest.TestCase):
    def test_01_financial_entity_types_follow_subsector(self):
        cases = {
            "Private Banks": FINANCIAL_ENTITY_BANK,
            "Consumer Finance": FINANCIAL_ENTITY_NBFC,
            "Speciality Finance": FINANCIAL_ENTITY_NBFC,
            "Diversified Financials": FINANCIAL_ENTITY_NBFC,
            "Life Insurance": FINANCIAL_ENTITY_INSURANCE,
            "Holding Companies": FINANCIAL_ENTITY_OTHER,
        }
        for sub_sector, expected in cases.items():
            with self.subTest(sub_sector=sub_sector):
                self.assertEqual(
                    classify_financial_entity("Financials", sub_sector), expected
                )
        self.assertEqual(
            classify_financial_entity("Industrials", "Private Banks"),
            NON_FINANCIAL_ENTITY,
        )

    def test_02_banks_nbfc_and_insurers_receive_de_carve_out(self):
        for sub_sector in (
            "Private Banks",
            "Consumer Finance",
            "Speciality Finance",
            "Life Insurance",
        ):
            with self.subTest(sub_sector=sub_sector):
                self.assertTrue(
                    uses_financial_leverage_treatment("Financials", sub_sector)
                )

    def test_03_holding_company_does_not_receive_automatic_carve_out(self):
        self.assertFalse(
            uses_financial_leverage_treatment("Financials", "Holding Companies")
        )

    def test_04_high_de_is_suppressed_for_bank_but_not_holding_company(self):
        self.assertFalse(
            high_leverage_flag(
                8.0, "Financials", sub_sector="Private Banks"
            )
        )
        self.assertTrue(
            high_leverage_flag(
                8.0, "Financials", sub_sector="Holding Companies"
            )
        )

    def test_05_difference_of_exactly_five_is_within_tolerance(self):
        result = classify_reference_difference(
            metric="ROE",
            calculated=15,
            reference=10,
            comparison_year="2024-03",
            latest_available_year="2024-03",
            entity_type=FINANCIAL_ENTITY_BANK,
        )
        self.assertEqual(result[0], CLASS_WITHIN_TOLERANCE)
        self.assertEqual(result[1], 5.0)

    def test_06_financial_roce_anomaly_is_formula_difference(self):
        result = classify_reference_difference(
            metric="ROCE",
            calculated=20,
            reference=10,
            comparison_year="2024-03",
            latest_available_year="2024-03",
            entity_type=FINANCIAL_ENTITY_INSURANCE,
        )
        self.assertEqual(result[0], CLASS_FORMULA_DIFFERENCE)

    def test_07_roe_with_newer_unmatched_period_is_version_difference(self):
        result = classify_reference_difference(
            metric="ROE",
            calculated=20,
            reference=10,
            comparison_year="2024-03",
            latest_available_year="2024-09",
            entity_type=FINANCIAL_ENTITY_NBFC,
        )
        self.assertEqual(result[0], CLASS_VERSION_DIFFERENCE)

    def test_08_same_period_roe_anomaly_is_source_problem(self):
        result = classify_reference_difference(
            metric="ROE",
            calculated=20,
            reference=10,
            comparison_year="2024-03",
            latest_available_year="2024-03",
            entity_type=FINANCIAL_ENTITY_BANK,
        )
        self.assertEqual(result[0], CLASS_SOURCE_PROBLEM)

    def test_09_missing_calculation_is_insufficient_history(self):
        result = classify_reference_difference(
            metric="ROCE",
            calculated=None,
            reference=10,
            comparison_year=None,
            latest_available_year="2024-03",
            entity_type=FINANCIAL_ENTITY_BANK,
        )
        self.assertEqual(result[0], CLASS_INSUFFICIENT_HISTORY)
        self.assertIsNone(result[1])

    def test_10_database_review_builds_two_rows_per_financial_company(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute(
            """INSERT INTO companies
               (id, company_name, roce_percentage, roe_percentage)
               VALUES ('AAA', 'Alpha Bank', 10, 12)"""
        )
        connection.execute(
            """INSERT INTO sectors
               (id, company_id, broad_sector, sub_sector)
               VALUES (1, 'AAA', 'Financials', 'Private Banks')"""
        )
        connection.execute(
            """INSERT INTO financial_ratios
               (company_id, year, is_financials, opm_mismatch_flag,
                return_on_capital_employed_pct, return_on_equity_pct,
                debt_to_equity, high_leverage_flag)
               VALUES ('AAA', '2024-03', 1, 0, 20, 11, 7, 0)"""
        )
        notes = build_financial_sector_notes(connection)
        connection.close()
        self.assertEqual(len(notes), 2)
        self.assertEqual({note["metric"] for note in notes}, {"ROCE", "ROE"})
        self.assertTrue(all(note["entity_type"] == FINANCIAL_ENTITY_BANK for note in notes))
        self.assertTrue(all(note["common_de_threshold_applied"] is False for note in notes))

    def test_11_edge_case_log_excludes_within_tolerance_rows(self):
        notes = [
            {"company_id": "AAA", "comparison_year": "2024-03", "metric": "ROCE", "classification": CLASS_FORMULA_DIFFERENCE, "calculated_pct": 20, "reference_pct": 10, "difference_pct_points": 10},
            {"company_id": "AAA", "comparison_year": "2024-03", "metric": "ROE", "classification": CLASS_WITHIN_TOLERANCE, "calculated_pct": 11, "reference_pct": 12, "difference_pct_points": 1},
        ]
        cases = sector_note_edge_cases(notes)
        self.assertEqual(len(cases), 1)
        self.assertIn("FORMULA_DIFFERENCE", cases[0]["detail"])

    def test_12_sector_notes_csv_uses_required_columns(self):
        row = {column: "" for column in SECTOR_NOTE_COLUMNS}
        with tempfile.TemporaryDirectory() as directory:
            path = write_sector_roce_notes(
                [row], Path(directory) / "sector_roce_notes.csv"
            )
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                output = list(reader)
                columns = reader.fieldnames
        self.assertEqual(tuple(columns or ()), SECTOR_NOTE_COLUMNS)
        self.assertEqual(len(output), 1)


if __name__ == "__main__":
    unittest.main()
