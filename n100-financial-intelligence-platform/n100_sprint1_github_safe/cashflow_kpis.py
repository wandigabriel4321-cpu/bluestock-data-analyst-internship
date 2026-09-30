"""Cash-flow KPIs and capital-allocation classifier for Sprint 2 Day 11."""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.analytics.cagr import parse_reporting_year, sort_annual_records


CFO_QUALITY_YEARS = 5
CFO_HIGH_QUALITY_THRESHOLD = 1.0
CFO_ACCRUAL_RISK_THRESHOLD = 0.5
CAPEX_ASSET_LIGHT_THRESHOLD = 3.0
CAPEX_CAPITAL_INTENSIVE_THRESHOLD = 8.0

LABEL_HIGH_QUALITY = "High Quality"
LABEL_MODERATE = "Moderate"
LABEL_ACCRUAL_RISK = "Accrual Risk"
LABEL_ASSET_LIGHT = "Asset Light"
LABEL_CAPITAL_INTENSIVE = "Capital Intensive"

PATTERN_CASH_ACCUMULATOR = "Cash Accumulator"
PATTERN_LIQUIDATING_ASSETS = "Liquidating Assets"
PATTERN_MIXED = "Mixed"
PATTERN_REINVESTOR = "Reinvestor"
PATTERN_SHAREHOLDER_RETURNS = "Shareholder Returns"
PATTERN_DISTRESS_SIGNAL = "Distress Signal"
PATTERN_ASSET_SALE_SURVIVAL = "Asset Sale Survival"
PATTERN_GROWTH_FUNDED_BY_DEBT = "Growth Funded by Debt"
PATTERN_PRE_REVENUE = "Pre-Revenue"


@dataclass(frozen=True)
class CFOQualityAssessment:
    """Five-year average CFO/PAT ratio and its quality label."""

    average_ratio: float | None
    label: str | None
    years_used: int
    start_year: str | None
    end_year: str | None


def _finite_number(value: Any) -> float | None:
    """Convert a finite numeric value to float; reject booleans and NaN/Inf."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def free_cash_flow(operating_activity: Any, investing_activity: Any) -> float | None:
    """Return CFO + CFI; negative FCF remains a valid analytical result."""
    cfo = _finite_number(operating_activity)
    cfi = _finite_number(investing_activity)
    if cfo is None or cfi is None:
        return None
    return cfo + cfi


def cfo_pat_ratio(operating_activity: Any, net_profit: Any) -> float | None:
    """Return CFO divided by PAT, or ``None`` when PAT is zero/unavailable."""
    cfo = _finite_number(operating_activity)
    pat = _finite_number(net_profit)
    if cfo is None or pat is None or pat == 0:
        return None
    return cfo / pat


def classify_cfo_quality(average_ratio: Any) -> str | None:
    """Classify five-year average CFO/PAT using the documented thresholds."""
    ratio = _finite_number(average_ratio)
    if ratio is None:
        return None
    if ratio > CFO_HIGH_QUALITY_THRESHOLD:
        return LABEL_HIGH_QUALITY
    if ratio < CFO_ACCRUAL_RISK_THRESHOLD:
        return LABEL_ACCRUAL_RISK
    return LABEL_MODERATE


def assess_five_year_cfo_quality(
    records: Iterable[Mapping[str, Any]],
    *,
    end_year: str | None = None,
) -> CFOQualityAssessment:
    """Average five exact consecutive annual CFO/PAT ratios.

    All five reporting periods must exist and each annual PAT denominator must
    be valid.  Otherwise no partial or misleading quality score is returned.
    """
    ordered = sort_annual_records(records)
    requested_end = str(end_year).strip() if end_year is not None else None
    if not ordered:
        return CFOQualityAssessment(None, None, 0, None, requested_end)

    actual_end = requested_end or ordered[-1]["year"]
    end_number, end_month = parse_reporting_year(actual_end)
    expected_years = [
        f"{year:04d}-{end_month:02d}"
        for year in range(end_number - CFO_QUALITY_YEARS + 1, end_number + 1)
    ]
    by_year = {record["year"]: record for record in ordered}
    ratios: list[float] = []
    for year in expected_years:
        record = by_year.get(year)
        if record is None:
            continue
        ratio = cfo_pat_ratio(
            record.get("operating_activity"), record.get("net_profit")
        )
        if ratio is not None:
            ratios.append(ratio)

    if len(ratios) != CFO_QUALITY_YEARS:
        return CFOQualityAssessment(
            None,
            None,
            len(ratios),
            expected_years[0],
            actual_end,
        )
    average = sum(ratios) / CFO_QUALITY_YEARS
    return CFOQualityAssessment(
        average,
        classify_cfo_quality(average),
        len(ratios),
        expected_years[0],
        actual_end,
    )


def capex_intensity(investing_activity: Any, sales: Any) -> float | None:
    """Return the absolute CFI proxy divided by positive revenue, as percent."""
    cfi = _finite_number(investing_activity)
    revenue = _finite_number(sales)
    if cfi is None or revenue is None or revenue <= 0:
        return None
    return abs(cfi) / revenue * 100.0


def classify_capex_intensity(intensity_pct: Any) -> str | None:
    """Classify CapEx intensity as Asset Light, Moderate or Capital Intensive."""
    intensity = _finite_number(intensity_pct)
    if intensity is None or intensity < 0:
        return None
    if intensity < CAPEX_ASSET_LIGHT_THRESHOLD:
        return LABEL_ASSET_LIGHT
    if intensity > CAPEX_CAPITAL_INTENSIVE_THRESHOLD:
        return LABEL_CAPITAL_INTENSIVE
    return LABEL_MODERATE


def fcf_conversion_rate(
    operating_activity: Any,
    investing_activity: Any,
    operating_profit: Any,
) -> float | None:
    """Return FCF / operating profit × 100; zero operating profit returns None."""
    fcf = free_cash_flow(operating_activity, investing_activity)
    profit = _finite_number(operating_profit)
    if fcf is None or profit is None or profit == 0:
        return None
    return fcf / profit * 100.0


def cashflow_sign(value: Any) -> str | None:
    """Return the binary sign used by the eight-pattern matrix.

    Zero is assigned ``+`` as the non-negative bin.  This keeps the classifier
    exhaustive for finite cash-flow values while retaining exactly 2³ patterns.
    """
    number = _finite_number(value)
    if number is None:
        return None
    return "+" if number >= 0 else "-"


def classify_capital_allocation(
    operating_activity: Any,
    investing_activity: Any,
    financing_activity: Any,
    *,
    cfo_pat_5yr_average: Any = None,
) -> str | None:
    """Classify all eight possible CFO/CFI/CFF binary sign combinations."""
    signature = (
        cashflow_sign(operating_activity),
        cashflow_sign(investing_activity),
        cashflow_sign(financing_activity),
    )
    if None in signature:
        return None

    if signature == ("+", "-", "-"):
        quality = _finite_number(cfo_pat_5yr_average)
        return (
            PATTERN_SHAREHOLDER_RETURNS
            if quality is not None and quality > CFO_HIGH_QUALITY_THRESHOLD
            else PATTERN_REINVESTOR
        )

    patterns = {
        ("+", "+", "+"): PATTERN_CASH_ACCUMULATOR,
        ("+", "+", "-"): PATTERN_LIQUIDATING_ASSETS,
        ("+", "-", "+"): PATTERN_MIXED,
        ("-", "+", "+"): PATTERN_DISTRESS_SIGNAL,
        ("-", "+", "-"): PATTERN_ASSET_SALE_SURVIVAL,
        ("-", "-", "+"): PATTERN_GROWTH_FUNDED_BY_DEBT,
        ("-", "-", "-"): PATTERN_PRE_REVENUE,
    }
    return patterns[signature]


def calculate_cashflow_kpis(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Calculate annual cash-flow KPIs and patterns for every source record."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source_record in records:
        record = dict(source_record)
        company_id = str(record.get("company_id", "")).strip()
        if not company_id:
            raise ValueError("Cash-flow record is missing company_id")
        grouped.setdefault(company_id, []).append(record)

    output: list[dict[str, Any]] = []
    for company_id in sorted(grouped):
        company_records = sort_annual_records(grouped[company_id])
        for record in company_records:
            quality = assess_five_year_cfo_quality(
                company_records, end_year=record["year"]
            )
            fcf = free_cash_flow(
                record.get("operating_activity"),
                record.get("investing_activity"),
            )
            intensity = capex_intensity(
                record.get("investing_activity"), record.get("sales")
            )
            cfo_sign = cashflow_sign(record.get("operating_activity"))
            cfi_sign = cashflow_sign(record.get("investing_activity"))
            cff_sign = cashflow_sign(record.get("financing_activity"))
            output.append(
                {
                    "company_id": company_id,
                    "year": record["year"],
                    "free_cash_flow_cr": fcf,
                    "cfo_pat_ratio": cfo_pat_ratio(
                        record.get("operating_activity"),
                        record.get("net_profit"),
                    ),
                    "cfo_pat_ratio_5yr": quality.average_ratio,
                    "cfo_quality_label": quality.label,
                    "cfo_quality_years_used": quality.years_used,
                    "capex_cr": (
                        abs(float(record["investing_activity"]))
                        if _finite_number(record.get("investing_activity")) is not None
                        else None
                    ),
                    "capex_intensity_pct": intensity,
                    "capex_intensity_label": classify_capex_intensity(intensity),
                    "fcf_conversion_rate_pct": fcf_conversion_rate(
                        record.get("operating_activity"),
                        record.get("investing_activity"),
                        record.get("operating_profit"),
                    ),
                    "cfo_sign": cfo_sign,
                    "cfi_sign": cfi_sign,
                    "cff_sign": cff_sign,
                    "pattern_label": classify_capital_allocation(
                        record.get("operating_activity"),
                        record.get("investing_activity"),
                        record.get("financing_activity"),
                        cfo_pat_5yr_average=quality.average_ratio,
                    ),
                }
            )
    return output


CAPITAL_ALLOCATION_COLUMNS = (
    "company_id",
    "year",
    "cfo_sign",
    "cfi_sign",
    "cff_sign",
    "pattern_label",
)

CASHFLOW_KPI_COLUMNS = (
    "company_id",
    "year",
    "free_cash_flow_cr",
    "cfo_pat_ratio",
    "cfo_pat_ratio_5yr",
    "cfo_quality_label",
    "cfo_quality_years_used",
    "capex_cr",
    "capex_intensity_pct",
    "capex_intensity_label",
    "fcf_conversion_rate_pct",
    "cfo_sign",
    "cfi_sign",
    "cff_sign",
    "pattern_label",
)


def write_capital_allocation(
    records: Iterable[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Write eligible sign patterns and guarantee that every row is labelled."""
    rows = calculate_cashflow_kpis(records)
    eligible = [
        row
        for row in rows
        if all(row[field] is not None for field in ("cfo_sign", "cfi_sign", "cff_sign"))
    ]
    if any(not row["pattern_label"] for row in eligible):
        raise ValueError("Eligible capital-allocation row is missing pattern_label")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAPITAL_ALLOCATION_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {field: row[field] for field in CAPITAL_ALLOCATION_COLUMNS}
            for row in eligible
        )
    return path


def write_cashflow_kpi_audit(
    records: Iterable[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Write the complete annual KPI audit used for Day 12 integration."""
    rows = calculate_cashflow_kpis(records)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASHFLOW_KPI_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_cashflow_inputs(database_path: str | Path) -> list[dict[str, Any]]:
    """Load cash-flow rows and aligned P&L denominators from SQLite."""
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
                cf.company_id,
                cf.year,
                cf.operating_activity,
                cf.investing_activity,
                cf.financing_activity,
                p.net_profit,
                p.sales,
                p.operating_profit
            FROM cashflow AS cf
            LEFT JOIN profitandloss AS p
              ON p.company_id = cf.company_id
             AND p.year = cf.year
            ORDER BY cf.company_id, cf.year
            """
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the required capital-allocation CSV and full KPI audit."""
    parser = argparse.ArgumentParser(description="Generate N100 cash-flow KPIs")
    parser.add_argument("--database", default="db/nifty100.db")
    parser.add_argument("--output", default="output/capital_allocation.csv")
    parser.add_argument(
        "--audit-output", default="output/cashflow_kpis_day11.csv"
    )
    args = parser.parse_args(argv)

    records = load_cashflow_inputs(args.database)
    capital_path = write_capital_allocation(records, args.output)
    audit_path = write_cashflow_kpi_audit(records, args.audit_output)
    eligible = sum(
        all(_finite_number(row[field]) is not None for field in (
            "operating_activity", "investing_activity", "financing_activity"
        ))
        for row in records
    )
    print(
        f"Cash-flow outputs written: {capital_path} ({eligible} eligible rows); "
        f"{audit_path} ({len(records)} audit rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
