"""Tests for Sprint 3 Day 18 peer percentile rankings."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.peer import (
    NO_PEER_GROUP_MESSAGE,
    PEER_METRICS,
    build_manual_checks,
    build_peer_percentiles,
    load_peer_group_assignments,
    peer_group_for_company,
    percentile_rank,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"
PEER_GROUPS_PATH = PROJECT_ROOT / "data" / "supporting" / "peer_groups.xlsx"


def sample_assignments() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"company_id": "AAA", "peer_group_name": "Sample", "is_benchmark": 1},
            {"company_id": "BBB", "peer_group_name": "Sample", "is_benchmark": 0},
            {"company_id": "CCC", "peer_group_name": "Sample", "is_benchmark": 0},
        ]
    )


def sample_history() -> pd.DataFrame:
    rows = []
    for index, company in enumerate(("AAA", "BBB", "CCC"), start=1):
        row = {"company_id": company, "year": "2024-03"}
        row.update({metric: float(index) for metric in PEER_METRICS})
        rows.append(row)
    return pd.DataFrame(rows)


class PercentileFormulaTests(unittest.TestCase):
    def test_01_unique_minimum_middle_and_maximum_span_zero_to_one_hundred(self):
        result = percentile_rank(pd.Series([10.0, 20.0, 30.0]))
        self.assertEqual(result.tolist(), [0.0, 50.0, 100.0])

    def test_02_debt_to_equity_percentile_is_inverted(self):
        result = percentile_rank(pd.Series([1.0, 2.0, 3.0]), inverse=True)
        self.assertEqual(result.tolist(), [100.0, 50.0, 0.0])

    def test_03_ties_receive_identical_percentile_rank(self):
        result = percentile_rank(pd.Series([10.0, 20.0, 20.0, 30.0]))
        self.assertEqual(result.iloc[1], result.iloc[2])

    def test_04_missing_values_are_excluded_and_remain_missing(self):
        result = percentile_rank(pd.Series([10.0, np.nan, 30.0]))
        self.assertEqual(result.iloc[0], 0.0)
        self.assertTrue(pd.isna(result.iloc[1]))
        self.assertEqual(result.iloc[2], 100.0)

    def test_05_singleton_group_receives_one_hundred(self):
        result = percentile_rank(pd.Series([42.0]))
        self.assertEqual(result.iloc[0], 100.0)


class AssignmentTests(unittest.TestCase):
    def test_06_official_workbook_has_56_assignments_11_groups_and_benchmarks(self):
        frame = load_peer_group_assignments(PEER_GROUPS_PATH)
        self.assertEqual(len(frame), 56)
        self.assertEqual(frame["peer_group_name"].nunique(), 11)
        self.assertEqual(int(frame["is_benchmark"].sum()), 11)

    def test_07_multiple_benchmarks_in_one_group_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.xlsx"
            pd.DataFrame(
                {
                    "company_id": ["AAA", "BBB"],
                    "peer_group_name": ["G", "G"],
                    "is_benchmark": [True, True],
                }
            ).to_excel(path, index=False)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                load_peer_group_assignments(path)

    def test_08_unassigned_company_returns_documented_message(self):
        self.assertEqual(
            peer_group_for_company("ZZZ", sample_assignments()),
            NO_PEER_GROUP_MESSAGE,
        )


class PeerOutputTests(unittest.TestCase):
    def test_09_build_creates_ten_rows_per_company_year(self):
        result = build_peer_percentiles(sample_assignments(), sample_history())
        self.assertEqual(len(result), 30)
        self.assertEqual(set(result["metric"]), set(PEER_METRICS))

    def test_10_debt_to_equity_lowest_company_has_highest_rank(self):
        result = build_peer_percentiles(sample_assignments(), sample_history())
        debt = result.loc[result["metric"].eq("debt_to_equity")]
        best = debt.sort_values("percentile_rank", ascending=False).iloc[0]
        self.assertEqual(best["company_id"], "AAA")

    def test_11_real_database_matches_day18_expected_counts(self):
        assignments = load_peer_group_assignments(PEER_GROUPS_PATH)
        with sqlite3.connect(DATABASE_PATH) as connection:
            columns = ["company_id", "year", *PEER_METRICS]
            history = pd.read_sql_query(
                f"SELECT {', '.join(columns)} FROM financial_ratios", connection
            )
        result = build_peer_percentiles(assignments, history)
        self.assertEqual(len(result), 7060)
        self.assertEqual(int(result["percentile_rank"].notna().sum()), 5589)
        self.assertEqual(int(result["value"].isna().sum()), 1471)

    def test_12_it_services_fmcg_and_all_manual_checks_pass(self):
        assignments = load_peer_group_assignments(PEER_GROUPS_PATH)
        with sqlite3.connect(DATABASE_PATH) as connection:
            columns = ["company_id", "year", *PEER_METRICS]
            history = pd.read_sql_query(
                f"SELECT {', '.join(columns)} FROM financial_ratios", connection
            )
            company_count = connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        percentiles = build_peer_percentiles(assignments, history)
        checks = build_manual_checks(assignments, percentiles, total_company_count=company_count)
        self.assertEqual(len(checks), 57)
        self.assertTrue(checks["status"].eq("PASS").all())
        self.assertEqual(
            checks.query("peer_group_name == 'IT Services' and metric == 'return_on_equity_pct' and check_type == 'EXTREME'")["actual"].iloc[0],
            "TCS",
        )
        self.assertEqual(
            checks.query("peer_group_name == 'FMCG' and metric == 'debt_to_equity' and check_type == 'EXTREME'")["actual"].iloc[0],
            "ITC",
        )


if __name__ == "__main__":
    unittest.main()
