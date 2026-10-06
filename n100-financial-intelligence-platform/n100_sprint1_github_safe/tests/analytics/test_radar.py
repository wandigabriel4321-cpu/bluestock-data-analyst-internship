"""Tests for Sprint 3 Day 19 radar charts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pandas as pd

from src.analytics.radar import (
    RADAR_AXES,
    build_radar_profiles,
    prepare_radar_profiles,
    render_radar_chart,
    safe_chart_filename,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"


def sample_snapshot() -> pd.DataFrame:
    rows = []
    for index, company_id in enumerate(("AAA", "BBB", "CCC", "DDD"), start=1):
        row = {"company_id": company_id, "company_name": f"Company {company_id}"}
        for axis in RADAR_AXES:
            row[axis.source] = float(index * 10)
        rows.append(row)
    return pd.DataFrame(rows)


def sample_assignments() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"company_id": "AAA", "peer_group_name": "Sample", "is_benchmark": 1},
            {"company_id": "BBB", "peer_group_name": "Sample", "is_benchmark": 0},
        ]
    )


class RadarProfileTests(unittest.TestCase):
    def test_01_filename_is_portable_and_deterministic(self):
        self.assertEqual(safe_chart_filename("M&M"), "M_M_radar.png")
        self.assertEqual(safe_chart_filename("TCS"), "TCS_radar.png")

    def test_02_all_eight_axes_are_defined(self):
        self.assertEqual(len(RADAR_AXES), 8)
        self.assertEqual({axis.key for axis in RADAR_AXES}, {"roe", "roce", "npm", "de", "fcf", "pat_cagr", "revenue_cagr", "composite"})

    def test_03_assigned_company_uses_peer_group_reference(self):
        profiles = prepare_radar_profiles(sample_snapshot(), sample_assignments())
        row = profiles.loc[profiles["company_id"].eq("AAA")].iloc[0]
        self.assertTrue(row["has_peer_group"])
        self.assertEqual(row["reference_label"], "Sample average")

    def test_04_unassigned_company_uses_nifty_100_reference(self):
        profiles = prepare_radar_profiles(sample_snapshot(), sample_assignments())
        row = profiles.loc[profiles["company_id"].eq("CCC")].iloc[0]
        self.assertFalse(row["has_peer_group"])
        self.assertEqual(row["reference_label"], "Nifty 100 average")
        self.assertEqual(row["comparison_group"], "No peer group assigned")

    def test_05_lower_debt_to_equity_receives_higher_score(self):
        profiles = prepare_radar_profiles(sample_snapshot(), sample_assignments())
        aaa = profiles.loc[profiles["company_id"].eq("AAA"), "de_score"].iloc[0]
        bbb = profiles.loc[profiles["company_id"].eq("BBB"), "de_score"].iloc[0]
        self.assertGreater(aaa, bbb)

    def test_06_missing_metric_uses_reference_only_for_rendering_and_is_flagged(self):
        snapshot = sample_snapshot()
        snapshot.loc[snapshot["company_id"].eq("AAA"), "pat_cagr_5yr"] = np.nan
        profiles = prepare_radar_profiles(snapshot, sample_assignments())
        row = profiles.loc[profiles["company_id"].eq("AAA")].iloc[0]
        self.assertTrue(row["pat_cagr_was_imputed"])
        self.assertEqual(row["pat_cagr_score"], row["pat_cagr_reference_score"])
        self.assertIn("PAT CAGR 5yr", row["imputed_axes"])

    def test_07_scores_and_references_are_bounded_zero_to_one_hundred(self):
        profiles = prepare_radar_profiles(sample_snapshot(), sample_assignments())
        columns = [
            name
            for axis in RADAR_AXES
            for name in (f"{axis.key}_score", f"{axis.key}_reference_score")
        ]
        self.assertTrue(profiles[columns].ge(0).all().all())
        self.assertTrue(profiles[columns].le(100).all().all())

    def test_08_filenames_are_unique(self):
        profiles = prepare_radar_profiles(sample_snapshot(), sample_assignments())
        self.assertFalse(profiles["filename"].duplicated().any())

    def test_09_single_chart_is_nonempty_and_readable(self):
        profile = prepare_radar_profiles(sample_snapshot(), sample_assignments()).iloc[0]
        with tempfile.TemporaryDirectory() as directory:
            path = render_radar_chart(profile, Path(directory) / profile["filename"])
            image = mpimg.imread(path)
            self.assertGreater(path.stat().st_size, 10_000)
            self.assertGreaterEqual(image.shape[1], 1_000)
            self.assertGreaterEqual(image.shape[0], 800)


class RadarDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = build_radar_profiles(DATABASE_PATH)

    def test_10_real_database_has_92_unique_company_profiles(self):
        self.assertEqual(len(self.profiles), 92)
        self.assertEqual(self.profiles["company_id"].nunique(), 92)

    def test_11_real_database_has_56_peer_and_36_nifty_comparisons(self):
        self.assertEqual(int(self.profiles["has_peer_group"].sum()), 56)
        self.assertEqual(int((~self.profiles["has_peer_group"]).sum()), 36)

    def test_12_required_examples_have_expected_reference_categories(self):
        tcs = self.profiles.loc[self.profiles["company_id"].eq("TCS")].iloc[0]
        abb = self.profiles.loc[self.profiles["company_id"].eq("ABB")].iloc[0]
        self.assertEqual(tcs["peer_group_name"], "IT Services")
        self.assertEqual(abb["comparison_group"], "No peer group assigned")


if __name__ == "__main__":
    unittest.main()
