"""CAGR engine for Sprint 2 of the N100 financial-intelligence platform.

The engine calculates Revenue, PAT and EPS CAGR over exact 3-, 5- and 10-year
reporting windows.  Negative and incomplete histories never enter a fractional
power calculation; they receive an explicit, separately stored status flag.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CAGR_WINDOWS = (3, 5, 10)
CAGR_METRICS = {
    "revenue": "sales",
    "pat": "net_profit",
    "eps": "eps",
}

FLAG_OK = "OK"
FLAG_DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
FLAG_TURNAROUND = "TURNAROUND"
FLAG_BOTH_NEGATIVE = "BOTH_NEGATIVE"
FLAG_ZERO_BASE = "ZERO_BASE"
FLAG_INSUFFICIENT = "INSUFFICIENT"

_REPORTING_YEAR = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")


@dataclass(frozen=True)
class CAGRResult:
    """One CAGR value and its independent audit metadata."""

    value: float | None
    flag: str
    start_year: str | None = None
    end_year: str | None = None
    periods: int | None = None


def _finite_number(value: Any) -> float | None:
    """Convert a finite numeric value to float; reject booleans and NaN/Inf."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_reporting_year(value: Any) -> tuple[int, int]:
    """Parse the canonical ``YYYY-MM`` reporting label for chronological use."""
    label = str(value).strip()
    match = _REPORTING_YEAR.fullmatch(label)
    if match is None:
        raise ValueError(f"Invalid reporting year: {value!r}")
    year = int(match.group("year"))
    month = int(match.group("month"))
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid reporting month: {value!r}")
    return year, month


def sort_annual_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return validated records ordered by reporting year and month.

    Duplicate reporting periods are rejected because silently selecting one
    would make the CAGR result dependent on source-row order.
    """
    ordered = [dict(record) for record in records]
    seen: set[str] = set()
    for record in ordered:
        label = str(record.get("year", "")).strip()
        parse_reporting_year(label)
        if label in seen:
            raise ValueError(f"Duplicate reporting year: {label}")
        seen.add(label)
        record["year"] = label
    return sorted(ordered, key=lambda row: parse_reporting_year(row["year"]))


def calculate_cagr(start_value: Any, end_value: Any, periods: int) -> CAGRResult:
    """Calculate CAGR or return the required edge-case flag.

    ``periods`` is the actual elapsed number of years, not the number of rows.
    Only a positive-to-positive transition is mathematically calculated.
    A zero ending value is treated as a decline to loss/non-profit territory;
    a zero starting value always receives ``ZERO_BASE``.
    """
    if isinstance(periods, bool) or not isinstance(periods, int) or periods <= 0:
        raise ValueError("CAGR periods must be a positive integer")

    start = _finite_number(start_value)
    end = _finite_number(end_value)
    if start is None or end is None:
        return CAGRResult(None, FLAG_INSUFFICIENT, periods=periods)
    if start == 0:
        return CAGRResult(None, FLAG_ZERO_BASE, periods=periods)
    if start > 0 and end > 0:
        value = ((end / start) ** (1.0 / periods) - 1.0) * 100.0
        return CAGRResult(value, FLAG_OK, periods=periods)
    if start > 0 and end <= 0:
        return CAGRResult(None, FLAG_DECLINE_TO_LOSS, periods=periods)
    if start < 0 and end > 0:
        return CAGRResult(None, FLAG_TURNAROUND, periods=periods)
    return CAGRResult(None, FLAG_BOTH_NEGATIVE, periods=periods)


def calculate_window_cagr(
    records: Iterable[Mapping[str, Any]],
    value_field: str,
    window_years: int,
    *,
    end_year: str | None = None,
) -> CAGRResult:
    """Calculate CAGR across an exact reporting-period window.

    The start period must share the ending month and be exactly
    ``window_years`` earlier.  Missing endpoints return ``INSUFFICIENT`` rather
    than substituting an adjacent observation and changing the period length.
    """
    if (
        isinstance(window_years, bool)
        or not isinstance(window_years, int)
        or window_years <= 0
    ):
        raise ValueError("CAGR window must be a positive integer")

    ordered = sort_annual_records(records)
    requested_end = str(end_year).strip() if end_year is not None else None
    if not ordered:
        return CAGRResult(
            None,
            FLAG_INSUFFICIENT,
            end_year=requested_end,
            periods=window_years,
        )

    by_year = {record["year"]: record for record in ordered}
    actual_end_year = requested_end or ordered[-1]["year"]
    try:
        end_year_number, end_month = parse_reporting_year(actual_end_year)
    except ValueError:
        if requested_end is not None:
            raise
        return CAGRResult(None, FLAG_INSUFFICIENT, periods=window_years)

    start_year = f"{end_year_number - window_years:04d}-{end_month:02d}"
    start_record = by_year.get(start_year)
    end_record = by_year.get(actual_end_year)
    if start_record is None or end_record is None:
        return CAGRResult(
            None,
            FLAG_INSUFFICIENT,
            start_year=start_year,
            end_year=actual_end_year,
            periods=window_years,
        )

    result = calculate_cagr(
        start_record.get(value_field), end_record.get(value_field), window_years
    )
    return CAGRResult(
        value=result.value,
        flag=result.flag,
        start_year=start_year,
        end_year=actual_end_year,
        periods=window_years,
    )


def calculate_company_cagrs(
    records: Iterable[Mapping[str, Any]],
    *,
    windows: Sequence[int] = CAGR_WINDOWS,
) -> dict[str, Any]:
    """Return the nine CAGR values and nine separate flag fields for a company."""
    ordered = sort_annual_records(records)
    output: dict[str, Any] = {
        "company_id": None,
        "cagr_as_of_year": ordered[-1]["year"] if ordered else None,
    }
    if ordered:
        company_ids = {
            str(record.get("company_id", "")).strip()
            for record in ordered
            if record.get("company_id") is not None
        }
        if len(company_ids) > 1:
            raise ValueError("Company CAGR input contains multiple company IDs")
        output["company_id"] = next(iter(company_ids), None)

    for metric_name, value_field in CAGR_METRICS.items():
        for window in windows:
            result = calculate_window_cagr(
                ordered,
                value_field,
                window,
                end_year=output["cagr_as_of_year"],
            )
            column = f"{metric_name}_cagr_{window}yr"
            output[column] = result.value
            output[f"{column}_flag"] = result.flag
    return output


def calculate_dataset_cagrs(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Group annual P&L records by company and calculate all CAGR outputs."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source_record in records:
        record = dict(source_record)
        company_id = str(record.get("company_id", "")).strip()
        if not company_id:
            raise ValueError("CAGR record is missing company_id")
        grouped.setdefault(company_id, []).append(record)
    return [calculate_company_cagrs(grouped[key]) for key in sorted(grouped)]


def cagr_output_columns() -> list[str]:
    """Return audit columns in the same value/flag order as the SQLite schema."""
    fields = ["company_id", "cagr_as_of_year"]
    for metric_name in CAGR_METRICS:
        for window in CAGR_WINDOWS:
            column = f"{metric_name}_cagr_{window}yr"
            fields.extend((column, f"{column}_flag"))
    return fields


def write_cagr_audit(
    records: Iterable[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Calculate the dataset and write a CSV with separate value/flag columns."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = calculate_dataset_cagrs(records)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cagr_output_columns())
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_profitandloss_records(database_path: str | Path) -> list[dict[str, Any]]:
    """Read the CAGR source fields from the Sprint SQLite database."""
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT company_id, year, sales, net_profit, eps
            FROM profitandloss
            ORDER BY company_id, year
            """
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the reproducible Day 10 CAGR audit from SQLite."""
    parser = argparse.ArgumentParser(description="Generate N100 CAGR audit CSV")
    parser.add_argument("--database", default="db/nifty100.db")
    parser.add_argument("--output", default="output/cagr_day10.csv")
    args = parser.parse_args(argv)

    records = load_profitandloss_records(args.database)
    output = write_cagr_audit(records, args.output)
    company_count = len({record["company_id"] for record in records})
    print(
        f"CAGR audit written to {output}: "
        f"{len(records)} source rows, {company_count} companies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
