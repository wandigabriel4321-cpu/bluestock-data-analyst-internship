"""Sprint 3 Day 19 radar-chart generation.

The charts compare 56 officially assigned companies with the average of their
peer group and the remaining 36 companies with the Nifty 100 average.  Every
axis is a 0--100 percentile score, allowing unlike financial units to share a
single polar scale.  Lower Debt-to-Equity is explicitly inverted.
"""

from __future__ import annotations

import argparse
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analytics.peer import NO_PEER_GROUP_MESSAGE, percentile_rank
from src.screener.composite_score import build_scored_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"
DEFAULT_CHART_DIR = PROJECT_ROOT / "reports" / "radar_charts"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "output" / "radar_chart_audit.csv"
EXPECTED_COMPANIES = 92
EXPECTED_ASSIGNED = 56
EXPECTED_UNASSIGNED = 36


@dataclass(frozen=True)
class RadarAxis:
    key: str
    label: str
    source: str
    inverse: bool = False


RADAR_AXES: tuple[RadarAxis, ...] = (
    RadarAxis("roe", "ROE", "return_on_equity_pct"),
    RadarAxis("roce", "ROCE", "return_on_capital_employed_pct"),
    RadarAxis("npm", "Net Profit\nMargin", "net_profit_margin_pct"),
    RadarAxis("de", "D/E", "debt_to_equity", inverse=True),
    RadarAxis("fcf", "FCF\nScore", "free_cash_flow_cr"),
    RadarAxis("pat_cagr", "PAT CAGR\n5yr", "pat_cagr_5yr"),
    RadarAxis("revenue_cagr", "Revenue CAGR\n5yr", "revenue_cagr_5yr"),
    RadarAxis("composite", "Composite\nScore", "sprint3_composite_score"),
)


@dataclass(frozen=True)
class RadarRunResult:
    chart_count: int
    assigned_count: int
    unassigned_count: int
    imputed_company_axis_count: int
    chart_dir: Path
    audit_path: Path


def safe_chart_filename(company_id: Any) -> str:
    """Return a deterministic, portable and unique candidate filename."""

    ticker = str(company_id).strip().upper()
    safe = re.sub(r"[^A-Z0-9._-]+", "_", ticker).strip("._-")
    if not safe:
        raise ValueError(f"Invalid company identifier for chart filename: {company_id!r}")
    return f"{safe}_radar.png"


def load_latest_metric_snapshot(connection: sqlite3.Connection) -> pd.DataFrame:
    """Return one latest non-null value per company and radar metric."""

    companies = pd.read_sql_query(
        "SELECT id AS company_id, company_name FROM companies ORDER BY id", connection
    )
    history_columns = [axis.source for axis in RADAR_AXES if axis.source != "sprint3_composite_score"]
    history = pd.read_sql_query(
        f"SELECT company_id, year, {', '.join(history_columns)} "
        "FROM financial_ratios ORDER BY company_id, year",
        connection,
    )
    snapshot = companies.copy()
    for source in history_columns:
        available = history.loc[history[source].notna(), ["company_id", "year", source]]
        latest = (
            available.sort_values(["company_id", "year"], kind="stable")
            .groupby("company_id", sort=False)
            .tail(1)
            .rename(columns={"year": f"{source}_year"})
        )
        snapshot = snapshot.merge(latest, on="company_id", how="left", validate="one_to_one")
    return snapshot


def load_peer_assignments(connection: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT company_id, peer_group_name, is_benchmark
           FROM peer_group_assignments
           ORDER BY peer_group_name, company_id""",
        connection,
    )


def prepare_radar_profiles(
    snapshot: pd.DataFrame, assignments: pd.DataFrame
) -> pd.DataFrame:
    """Attach comparable company and reference scores for all eight axes.

    Assigned companies use a within-peer-group distribution. Unassigned
    companies use a global 92-company distribution. Missing source metrics
    remain null in the profile and are represented in the PNG at the relevant
    reference average solely to keep the polygon renderable.
    """

    required = {"company_id", "company_name", *(axis.source for axis in RADAR_AXES)}
    missing = required.difference(snapshot.columns)
    if missing:
        raise ValueError("Radar snapshot is missing columns: " + ", ".join(sorted(missing)))
    if assignments["company_id"].duplicated().any():
        raise ValueError("Peer assignments contain duplicate companies")

    frame = snapshot.merge(
        assignments[["company_id", "peer_group_name", "is_benchmark"]],
        on="company_id",
        how="left",
        validate="one_to_one",
    )
    frame["has_peer_group"] = frame["peer_group_name"].notna()
    frame["comparison_group"] = frame["peer_group_name"].fillna(NO_PEER_GROUP_MESSAGE)
    frame["reference_label"] = frame["peer_group_name"].map(
        lambda value: f"{value} average" if pd.notna(value) else "Nifty 100 average"
    )

    imputed_labels: list[list[str]] = [[] for _ in range(len(frame))]
    for axis in RADAR_AXES:
        values = pd.to_numeric(frame[axis.source], errors="coerce").astype(float)
        values = values.where(np.isfinite(values), np.nan)
        global_scores = percentile_rank(values, inverse=axis.inverse)
        peer_scores = pd.Series(np.nan, index=frame.index, dtype=float)
        assigned = frame.loc[frame["has_peer_group"]]
        for group, index in assigned.groupby("peer_group_name", sort=True).groups.items():
            peer_scores.loc[index] = percentile_rank(
                values.loc[index], inverse=axis.inverse
            )

        score_column = f"{axis.key}_score"
        reference_column = f"{axis.key}_reference_score"
        frame[score_column] = global_scores
        frame.loc[frame["has_peer_group"], score_column] = peer_scores.loc[
            frame["has_peer_group"]
        ]

        global_reference = float(global_scores.dropna().mean())
        peer_references = (
            frame.loc[frame["has_peer_group"], ["peer_group_name", score_column]]
            .groupby("peer_group_name")[score_column]
            .mean()
        )
        frame[reference_column] = global_reference
        frame.loc[frame["has_peer_group"], reference_column] = frame.loc[
            frame["has_peer_group"], "peer_group_name"
        ].map(peer_references)

        missing_score = frame[score_column].isna()
        for position in np.flatnonzero(missing_score.to_numpy()):
            imputed_labels[position].append(axis.label.replace("\n", " "))
        # Rendering fallback only. The raw source and *_was_imputed flag remain
        # in the audit, so this cannot be mistaken for a calculated KPI.
        frame[f"{axis.key}_was_imputed"] = missing_score
        frame.loc[missing_score, score_column] = frame.loc[
            missing_score, reference_column
        ]
        frame[score_column] = frame[score_column].round(6)
        frame[reference_column] = frame[reference_column].round(6)

    frame["imputed_axes"] = [", ".join(labels) for labels in imputed_labels]
    frame["imputed_axis_count"] = [len(labels) for labels in imputed_labels]
    frame["filename"] = frame["company_id"].map(safe_chart_filename)
    if frame["filename"].duplicated().any():
        duplicates = frame.loc[frame["filename"].duplicated(False), "filename"].tolist()
        raise ValueError("Radar filenames are not unique: " + ", ".join(duplicates))
    return frame.sort_values("company_id", kind="stable").reset_index(drop=True)


def build_radar_profiles(database_path: str | Path = DEFAULT_DATABASE_PATH) -> pd.DataFrame:
    database = Path(database_path)
    if not database.is_file() or database.stat().st_size == 0:
        raise FileNotFoundError(f"SQLite database is missing or empty: {database}")
    with sqlite3.connect(database) as connection:
        snapshot = load_latest_metric_snapshot(connection)
        assignments = load_peer_assignments(connection)
    scored, _ = build_scored_snapshot(database)
    composite = scored[
        ["company_id", "financial_year", "sprint3_composite_score"]
    ].rename(columns={"financial_year": "sprint3_composite_score_year"})
    snapshot = snapshot.merge(composite, on="company_id", how="left", validate="one_to_one")
    return prepare_radar_profiles(snapshot, assignments)


def _closed(values: Sequence[float]) -> list[float]:
    values = [float(value) for value in values]
    return [*values, values[0]]


def render_radar_chart(profile: pd.Series, output_path: str | Path) -> Path:
    """Render one readable company-versus-reference radar chart."""

    labels = [axis.label for axis in RADAR_AXES]
    company_scores = [profile[f"{axis.key}_score"] for axis in RADAR_AXES]
    reference_scores = [profile[f"{axis.key}_reference_score"] for axis in RADAR_AXES]
    if not all(math.isfinite(float(value)) for value in company_scores + reference_scores):
        raise ValueError(f"Non-finite render score for {profile['company_id']}")

    angles = np.linspace(0, 2 * np.pi, len(RADAR_AXES), endpoint=False).tolist()
    closed_angles = [*angles, angles[0]]
    company_closed = _closed(company_scores)
    reference_closed = _closed(reference_scores)

    fig, ax = plt.subplots(figsize=(10.5, 8.5), subplot_kw={"polar": True})
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFCFD")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10.5, fontweight="semibold", color="#243447")
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    # The outer ring is fixed at 100; its text label is intentionally blank so
    # it cannot collide with the horizontal Net Profit Margin axis label.
    ax.set_yticklabels(["20", "40", "60", "80", ""], fontsize=8.5, color="#667788")
    ax.set_rlabel_position(90)
    ax.grid(color="#CCD6DD", linewidth=0.8, alpha=0.9)
    ax.spines["polar"].set_color("#9AAAB5")

    company_color = "#008C6A"
    reference_color = "#D88919"
    ax.plot(
        closed_angles,
        company_closed,
        color=company_color,
        linewidth=2.7,
        marker="o",
        markersize=4.5,
        label=str(profile["company_id"]),
    )
    ax.fill(closed_angles, company_closed, color=company_color, alpha=0.22)
    ax.plot(
        closed_angles,
        reference_closed,
        color=reference_color,
        linewidth=2.3,
        linestyle="--",
        marker="s",
        markersize=3.5,
        label=str(profile["reference_label"]),
    )

    group_text = (
        f"Peer group: {profile['peer_group_name']}"
        if bool(profile["has_peer_group"])
        else "No peer group assigned — benchmark: Nifty 100"
    )
    ax.set_title(
        f"{profile['company_id']} — {profile['company_name']}\n{group_text}",
        fontsize=15,
        fontweight="bold",
        color="#17324D",
        pad=28,
    )
    legend = ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.28, 1.13),
        frameon=True,
        fontsize=9.5,
    )
    legend.get_frame().set_edgecolor("#D8E0E5")
    legend.get_frame().set_facecolor("white")

    footer = "Scores: percentile scale 0–100 | Higher is better | D/E is inverted"
    if int(profile["imputed_axis_count"]) > 0:
        footer += f"\nMissing source axis shown at reference average: {profile['imputed_axes']}"
    fig.text(0.5, 0.025, footer, ha="center", va="bottom", fontsize=8.5, color="#5A6872")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    if not target.is_file() or target.stat().st_size == 0:
        raise ValueError(f"Radar chart was not created correctly: {target}")
    return target


def generate_radar_charts(
    profiles: pd.DataFrame, output_dir: str | Path = DEFAULT_CHART_DIR
) -> pd.DataFrame:
    """Generate every PNG and return a complete file-level audit."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []
    for _, profile in profiles.iterrows():
        path = render_radar_chart(profile, target_dir / str(profile["filename"]))
        image = mpimg.imread(path)
        height, width = image.shape[:2]
        row: dict[str, Any] = {
            "company_id": profile["company_id"],
            "company_name": profile["company_name"],
            "peer_group_name": profile["comparison_group"],
            "reference_label": profile["reference_label"],
            "filename": profile["filename"],
            "file_size_bytes": path.stat().st_size,
            "width_px": width,
            "height_px": height,
            "imputed_axis_count": profile["imputed_axis_count"],
            "imputed_axes": profile["imputed_axes"],
            "status": "PASS" if path.stat().st_size > 10_000 and width >= 1_000 and height >= 800 else "FAIL",
        }
        for axis in RADAR_AXES:
            row[f"{axis.key}_score"] = profile[f"{axis.key}_score"]
            row[f"{axis.key}_reference_score"] = profile[f"{axis.key}_reference_score"]
        audit_rows.append(row)
    audit = pd.DataFrame(audit_rows)
    if len(audit) != EXPECTED_COMPANIES:
        raise ValueError(f"Expected {EXPECTED_COMPANIES} radar charts, generated {len(audit)}")
    if audit["filename"].duplicated().any():
        raise ValueError("Generated radar chart filenames are not unique")
    if not audit["status"].eq("PASS").all():
        raise ValueError("One or more radar charts failed file validation")
    return audit


def run_day19(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    chart_dir: str | Path = DEFAULT_CHART_DIR,
    audit_path: str | Path = DEFAULT_AUDIT_PATH,
) -> RadarRunResult:
    profiles = build_radar_profiles(database_path)
    assigned_count = int(profiles["has_peer_group"].sum())
    unassigned_count = int((~profiles["has_peer_group"]).sum())
    if len(profiles) != EXPECTED_COMPANIES:
        raise ValueError(f"Expected {EXPECTED_COMPANIES} company profiles")
    if assigned_count != EXPECTED_ASSIGNED or unassigned_count != EXPECTED_UNASSIGNED:
        raise ValueError(
            f"Expected {EXPECTED_ASSIGNED}/{EXPECTED_UNASSIGNED} assigned/unassigned, "
            f"found {assigned_count}/{unassigned_count}"
        )
    audit = generate_radar_charts(profiles, chart_dir)
    audit_target = Path(audit_path)
    audit_target.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_target, index=False)
    return RadarRunResult(
        chart_count=len(audit),
        assigned_count=assigned_count,
        unassigned_count=unassigned_count,
        imputed_company_axis_count=int(profiles["imputed_axis_count"].sum()),
        chart_dir=Path(chart_dir),
        audit_path=audit_target,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--chart-dir", type=Path, default=DEFAULT_CHART_DIR)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_day19(args.database, chart_dir=args.chart_dir, audit_path=args.audit)
    print(
        f"Day 19 complete: {result.chart_count} radar charts; "
        f"{result.assigned_count} peer-group comparisons; "
        f"{result.unassigned_count} Nifty 100 comparisons; "
        f"{result.imputed_company_axis_count} render-only missing-axis fallbacks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
