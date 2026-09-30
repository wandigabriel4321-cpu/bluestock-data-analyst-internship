"""Financial-sector ROCE/ROE review for Sprint 2 Day 13."""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.analytics.ratios import (
    FINANCIAL_ENTITY_BANK,
    FINANCIAL_ENTITY_INSURANCE,
    FINANCIAL_ENTITY_NBFC,
    classify_financial_entity,
    uses_financial_leverage_treatment,
)


DIFFERENCE_TOLERANCE_PCT_POINTS = 5.0
TASK_REFERENCE_FINANCIALS_COUNT = 19

CLASS_WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
CLASS_SOURCE_PROBLEM = "SOURCE_PROBLEM"
CLASS_VERSION_DIFFERENCE = "VERSION_DIFFERENCE"
CLASS_FORMULA_DIFFERENCE = "FORMULA_DIFFERENCE"
CLASS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

SECTOR_NOTE_COLUMNS = (
    "company_id",
    "company_name",
    "broad_sector",
    "sub_sector",
    "entity_type",
    "metric",
    "comparison_year",
    "latest_available_year",
    "calculated_pct",
    "reference_pct",
    "difference_pct_points",
    "tolerance_pct_points",
    "exceeds_tolerance",
    "classification",
    "classification_detail",
    "peer_group_median_pct",
    "peer_group_percentile_pct",
    "latest_debt_to_equity",
    "common_de_threshold_applied",
    "high_leverage_flag",
    "task_reference_financials_count",
    "current_dataset_financials_count",
    "count_variance",
    "count_reconciliation",
)


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def classify_reference_difference(
    *,
    metric: str,
    calculated: Any,
    reference: Any,
    comparison_year: str | None,
    latest_available_year: str | None,
    entity_type: str,
    tolerance_pct_points: float = DIFFERENCE_TOLERANCE_PCT_POINTS,
) -> tuple[str, float | None, str]:
    """Classify a ROCE/ROE comparison with an explicit audit rationale."""
    calculated_value = _finite_number(calculated)
    reference_value = _finite_number(reference)
    if calculated_value is None or reference_value is None:
        return (
            CLASS_INSUFFICIENT_HISTORY,
            None,
            "A calculated annual value or company-level reference is unavailable.",
        )

    difference = abs(calculated_value - reference_value)
    if difference <= tolerance_pct_points:
        return (
            CLASS_WITHIN_TOLERANCE,
            difference,
            "Absolute difference is not greater than five percentage points.",
        )

    if metric == "ROCE" and entity_type in {
        FINANCIAL_ENTITY_BANK,
        FINANCIAL_ENTITY_NBFC,
        FINANCIAL_ENTITY_INSURANCE,
        "OTHER_FINANCIAL",
    }:
        return (
            CLASS_FORMULA_DIFFERENCE,
            difference,
            "Industrial ROCE uses EBIT and funded capital; financial institutions require sector-relative interpretation.",
        )

    if comparison_year and latest_available_year and comparison_year != latest_available_year:
        return (
            CLASS_VERSION_DIFFERENCE,
            difference,
            "The latest calculable period differs from the latest annual key available in the current dataset.",
        )

    return (
        CLASS_SOURCE_PROBLEM,
        difference,
        "The same-period formula diverges materially from the supplied company-level reference and requires source review.",
    )


def _latest_metric_row(
    connection: sqlite3.Connection, company_id: str, column: str
) -> sqlite3.Row | None:
    allowed = {
        "return_on_capital_employed_pct",
        "return_on_equity_pct",
        "debt_to_equity",
    }
    if column not in allowed:
        raise ValueError(f"Unsupported metric column: {column}")
    return connection.execute(
        f"""
        SELECT year, {column} AS value, high_leverage_flag
        FROM financial_ratios
        WHERE company_id = ? AND {column} IS NOT NULL
        ORDER BY year DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _percentile_rank(values: Sequence[float], value: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 50.0
    less = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    rank = less + (equal - 1) / 2.0
    return rank / (len(values) - 1) * 100.0


def build_financial_sector_notes(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Build the two-metric review for every official Financials company."""
    connection.row_factory = sqlite3.Row
    companies = connection.execute(
        """
        SELECT
            s.company_id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,
            c.roce_percentage,
            c.roe_percentage,
            (SELECT MAX(f.year) FROM financial_ratios AS f
             WHERE f.company_id = s.company_id) AS latest_available_year
        FROM sectors AS s
        JOIN companies AS c ON c.id = s.company_id
        WHERE lower(trim(s.broad_sector)) = 'financials'
        ORDER BY s.company_id
        """
    ).fetchall()
    current_count = len(companies)

    observations: list[dict[str, Any]] = []
    roce_by_entity: dict[str, list[float]] = defaultdict(list)
    for company in companies:
        entity_type = classify_financial_entity(
            company["broad_sector"], company["sub_sector"]
        )
        roce_row = _latest_metric_row(
            connection, company["company_id"], "return_on_capital_employed_pct"
        )
        roe_row = _latest_metric_row(
            connection, company["company_id"], "return_on_equity_pct"
        )
        debt_row = _latest_metric_row(
            connection, company["company_id"], "debt_to_equity"
        )
        if roce_row is not None:
            roce_by_entity[entity_type].append(float(roce_row["value"]))
        observations.append(
            {
                "company": company,
                "entity_type": entity_type,
                "roce_row": roce_row,
                "roe_row": roe_row,
                "debt_row": debt_row,
            }
        )

    notes: list[dict[str, Any]] = []
    for observation in observations:
        company = observation["company"]
        entity_type = observation["entity_type"]
        debt_row = observation["debt_row"]
        for metric, row_name, reference_column in (
            ("ROCE", "roce_row", "roce_percentage"),
            ("ROE", "roe_row", "roe_percentage"),
        ):
            metric_row = observation[row_name]
            calculated = metric_row["value"] if metric_row is not None else None
            comparison_year = metric_row["year"] if metric_row is not None else None
            reference = company[reference_column]
            classification, difference, detail = classify_reference_difference(
                metric=metric,
                calculated=calculated,
                reference=reference,
                comparison_year=comparison_year,
                latest_available_year=company["latest_available_year"],
                entity_type=entity_type,
            )
            peer_values = roce_by_entity.get(entity_type, []) if metric == "ROCE" else []
            calculated_number = _finite_number(calculated)
            exempt = uses_financial_leverage_treatment(
                company["broad_sector"], company["sub_sector"]
            )
            notes.append(
                {
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "broad_sector": company["broad_sector"],
                    "sub_sector": company["sub_sector"],
                    "entity_type": entity_type,
                    "metric": metric,
                    "comparison_year": comparison_year,
                    "latest_available_year": company["latest_available_year"],
                    "calculated_pct": calculated_number,
                    "reference_pct": _finite_number(reference),
                    "difference_pct_points": difference,
                    "tolerance_pct_points": DIFFERENCE_TOLERANCE_PCT_POINTS,
                    "exceeds_tolerance": difference is not None and difference > DIFFERENCE_TOLERANCE_PCT_POINTS,
                    "classification": classification,
                    "classification_detail": detail,
                    "peer_group_median_pct": _median(peer_values) if metric == "ROCE" else None,
                    "peer_group_percentile_pct": (
                        _percentile_rank(peer_values, calculated_number)
                        if metric == "ROCE" and calculated_number is not None
                        else None
                    ),
                    "latest_debt_to_equity": debt_row["value"] if debt_row is not None else None,
                    "common_de_threshold_applied": not exempt,
                    "high_leverage_flag": debt_row["high_leverage_flag"] if debt_row is not None else None,
                    "task_reference_financials_count": TASK_REFERENCE_FINANCIALS_COUNT,
                    "current_dataset_financials_count": current_count,
                    "count_variance": current_count - TASK_REFERENCE_FINANCIALS_COUNT,
                    "count_reconciliation": (
                        "SOURCE_VERSION_DIFFERENCE: sectors.xlsx is authoritative; no 19-company membership list was supplied."
                    ),
                }
            )
    return notes


def write_sector_roce_notes(
    notes: Iterable[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Write the complete Financials review with a stable output schema."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SECTOR_NOTE_COLUMNS)
        writer.writeheader()
        writer.writerows(notes)
    return path


def sector_note_edge_cases(
    notes: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert material/insufficient comparisons to the common edge-case log."""
    edge_cases: list[dict[str, Any]] = []
    for note in notes:
        classification = str(note["classification"])
        if classification == CLASS_WITHIN_TOLERANCE:
            continue
        metric_column = (
            "return_on_capital_employed_pct"
            if note["metric"] == "ROCE"
            else "return_on_equity_pct"
        )
        edge_cases.append(
            {
                "company_id": note["company_id"],
                "year": note["comparison_year"] or "",
                "category": "FINANCIALS_ROCE_ROE_REVIEW",
                "metric": metric_column,
                "detail": (
                    f"classification={classification}; "
                    f"calculated={note['calculated_pct']}; "
                    f"reference={note['reference_pct']}; "
                    f"difference_pct_points={note['difference_pct_points']}"
                ),
            }
        )
    return edge_cases


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Financials ROCE and ROE")
    parser.add_argument("--database", default="db/nifty100.db")
    parser.add_argument("--output", default="output/sector_roce_notes.csv")
    args = parser.parse_args(argv)
    connection = sqlite3.connect(Path(args.database))
    try:
        notes = build_financial_sector_notes(connection)
        output = write_sector_roce_notes(notes, args.output)
    finally:
        connection.close()
    anomalies = sum(
        note["classification"] != CLASS_WITHIN_TOLERANCE for note in notes
    )
    print(
        f"Financials review written to {output}: {len(notes)} comparisons, "
        f"{anomalies} anomalies/insufficient cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
