"""Populate and audit the Sprint 2 ``financial_ratios`` SQLite table.

The Day 12 engine builds the authoritative company-year universe from the
union of Profit & Loss, Balance Sheet and Cash Flow keys.  Each KPI is then
calculated from the validated Sprint 1 tables; the pre-computed workbook is
used only as a comparison reference and never as the database source.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.analytics.cagr import CAGR_METRICS, CAGR_WINDOWS, calculate_window_cagr
from src.analytics.cashflow_kpis import calculate_cashflow_kpis
from src.analytics.ratios import (
    assess_interest_coverage,
    asset_turnover,
    cross_check_operating_profit_margin,
    debt_to_equity,
    high_leverage_flag,
    is_financial_sector,
    net_debt,
    net_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
    safe_divide,
)
from src.analytics.sector_roce import (
    build_financial_sector_notes,
    sector_note_edge_cases,
    write_sector_roce_notes,
)
from src.etl.normaliser import normalize_ticker, normalize_year


MINIMUM_EXPECTED_ROWS = 1_100
EXPECTED_COMPANIES = 92

FINANCIAL_RATIO_COLUMNS = (
    "company_id",
    "year",
    "broad_sector",
    "is_financials",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "opm_source_pct",
    "opm_difference_pct_points",
    "opm_mismatch_flag",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "high_leverage_flag",
    "interest_coverage",
    "icr_label",
    "icr_warning_flag",
    "net_debt_cr",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "capex_intensity_pct",
    "capex_intensity_label",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",
    "revenue_cagr_3yr",
    "revenue_cagr_3yr_flag",
    "revenue_cagr_5yr",
    "revenue_cagr_5yr_flag",
    "revenue_cagr_10yr",
    "revenue_cagr_10yr_flag",
    "pat_cagr_3yr",
    "pat_cagr_3yr_flag",
    "pat_cagr_5yr",
    "pat_cagr_5yr_flag",
    "pat_cagr_10yr",
    "pat_cagr_10yr_flag",
    "eps_cagr_3yr",
    "eps_cagr_3yr_flag",
    "eps_cagr_5yr",
    "eps_cagr_5yr_flag",
    "eps_cagr_10yr",
    "eps_cagr_10yr_flag",
    "cfo_pat_ratio_5yr",
    "cfo_quality_label",
    "fcf_conversion_rate_pct",
    "composite_quality_score",
)

# The official reference workbook exposes these 13 comparable KPI columns.
REFERENCE_KPI_COLUMNS = (
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",
)

# The Day 12 task additionally requires the three principal five-year growth
# fields and a composite score.  Day 12 checks that none of these 17 fields is
# completely empty; row-level None remains legitimate for documented cases.
MANDATORY_KPI_COLUMNS = REFERENCE_KPI_COLUMNS + (
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "composite_quality_score",
)


@dataclass(frozen=True)
class RatioEngineResult:
    """Paths and verified counts produced by one Day 12 execution."""

    row_count: int
    company_count: int
    audit_path: Path
    null_audit_path: Path
    comparison_path: Path
    comparison_summary_path: Path
    sector_notes_path: Path
    edge_case_path: Path


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def book_value_per_share(
    equity_capital: Any, reserves: Any, face_value: Any
) -> float | None:
    """Return book value per share using the documented crore-unit formula."""
    equity = _finite_number(equity_capital)
    retained = _finite_number(reserves)
    face = _finite_number(face_value)
    if equity is None or retained is None or face is None or equity <= 0 or face <= 0:
        return None
    shares_crore = equity / face
    return safe_divide(equity + retained, shares_crore)


def company_year_universe(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return every distinct company-year key present in any annual source."""
    rows = connection.execute(
        """
        SELECT company_id, year FROM profitandloss
        UNION
        SELECT company_id, year FROM balancesheet
        UNION
        SELECT company_id, year FROM cashflow
        ORDER BY company_id, year
        """
    ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def _table_rows(
    connection: sqlite3.Connection, table_name: str
) -> list[dict[str, Any]]:
    allowed = {"companies", "profitandloss", "balancesheet", "cashflow", "sectors"}
    if table_name not in allowed:
        raise ValueError(f"Unsupported source table: {table_name}")
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table_name}"')]


def _by_key(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["company_id"]), str(row["year"])): dict(row)
        for row in rows
    }


def _profit_histories(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        histories[str(row["company_id"])].append(dict(row))
    return histories


def _cashflow_kpi_map(
    profit_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    cashflow_rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for source in cashflow_rows:
        row = dict(source)
        key = (str(row["company_id"]), str(row["year"]))
        profit = profit_by_key.get(key, {})
        row.update(
            net_profit=profit.get("net_profit"),
            sales=profit.get("sales"),
            operating_profit=profit.get("operating_profit"),
        )
        inputs.append(row)
    return {
        (str(row["company_id"]), str(row["year"])): row
        for row in calculate_cashflow_kpis(inputs)
    }


def _cagr_values(
    records: Iterable[Mapping[str, Any]], end_year: str
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    history = list(records)
    for metric_name, value_field in CAGR_METRICS.items():
        for window in CAGR_WINDOWS:
            result = calculate_window_cagr(
                history, value_field, window, end_year=end_year
            )
            column = f"{metric_name}_cagr_{window}yr"
            output[column] = result.value
            output[f"{column}_flag"] = result.flag
    return output


def _percentile(values: Sequence[float], quantile: float) -> float:
    """Return a deterministic linearly interpolated percentile."""
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty sequence")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return ordered[lower_index] + (
        ordered[upper_index] - ordered[lower_index]
    ) * fraction


def _winsorised_score(
    value: Any, lower: float, upper: float, *, inverse: bool = False
) -> float | None:
    """Map a metric to 0–100 after P10/P90 winsorisation."""
    number = _finite_number(value)
    if number is None:
        return None
    if upper == lower:
        score = 50.0
    else:
        clipped = min(max(number, lower), upper)
        score = (clipped - lower) / (upper - lower) * 100.0
    return 100.0 - score if inverse else score


def apply_composite_quality_scores(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Calculate the documented P10/P90-normalised composite quality score.

    The score is ``0.30*ROE + 0.25*FCF + 0.25*ROCE + 0.20*D/E`` after
    winsorised 0–100 scaling.  D/E is inverted so lower leverage receives the
    higher score.  A row remains ``None`` when any required component is
    unavailable, preserving rather than fabricating missing information.
    """
    components = {
        "return_on_equity_pct": False,
        "free_cash_flow_cr": False,
        "return_on_capital_employed_pct": False,
        "debt_to_equity": True,
    }
    bounds: dict[str, tuple[float, float]] = {}
    for column in components:
        values = [
            number
            for row in rows
            if (number := _finite_number(row.get(column))) is not None
        ]
        bounds[column] = (_percentile(values, 0.10), _percentile(values, 0.90))

    output: list[dict[str, Any]] = []
    weights = {
        "return_on_equity_pct": 0.30,
        "free_cash_flow_cr": 0.25,
        "return_on_capital_employed_pct": 0.25,
        "debt_to_equity": 0.20,
    }
    for source in rows:
        row = dict(source)
        scores = {
            column: _winsorised_score(
                row.get(column), *bounds[column], inverse=inverse
            )
            for column, inverse in components.items()
        }
        row["composite_quality_score"] = (
            sum(scores[column] * weights[column] for column in weights)
            if all(score is not None for score in scores.values())
            else None
        )
        output.append(row)
    return output


def build_financial_ratio_rows(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Calculate one authoritative output row per union company-year key."""
    connection.row_factory = sqlite3.Row
    companies = {str(row["id"]): dict(row) for row in _table_rows(connection, "companies")}
    sectors = {
        str(row["company_id"]): dict(row)
        for row in _table_rows(connection, "sectors")
    }
    profit_rows = _table_rows(connection, "profitandloss")
    balance_rows = _table_rows(connection, "balancesheet")
    cashflow_rows = _table_rows(connection, "cashflow")
    profit_by_key = _by_key(profit_rows)
    balance_by_key = _by_key(balance_rows)
    cashflow_by_key = _by_key(cashflow_rows)
    profit_histories = _profit_histories(profit_rows)
    cashflow_kpis = _cashflow_kpi_map(profit_by_key, cashflow_rows)

    output: list[dict[str, Any]] = []
    for company_id, year in company_year_universe(connection):
        key = (company_id, year)
        profit = profit_by_key.get(key, {})
        balance = balance_by_key.get(key, {})
        cashflow = cashflow_by_key.get(key, {})
        cash_kpis = cashflow_kpis.get(key, {})
        company = companies.get(company_id, {})
        broad_sector = sectors.get(company_id, {}).get("broad_sector")
        sub_sector = sectors.get(company_id, {}).get("sub_sector")

        opm = cross_check_operating_profit_margin(
            profit.get("operating_profit"),
            profit.get("sales"),
            profit.get("opm_percentage"),
            company_id=company_id,
            year=year,
        )
        debt_equity = debt_to_equity(
            balance.get("borrowings"),
            balance.get("equity_capital"),
            balance.get("reserves"),
        )
        coverage = assess_interest_coverage(
            profit.get("operating_profit"),
            profit.get("other_income"),
            profit.get("interest"),
            borrowings=balance.get("borrowings"),
        )
        operating_profit = _finite_number(profit.get("operating_profit"))
        depreciation = _finite_number(profit.get("depreciation"))
        ebit = (
            operating_profit - depreciation
            if operating_profit is not None and depreciation is not None
            else None
        )

        row: dict[str, Any] = {
            "company_id": company_id,
            "year": year,
            "broad_sector": broad_sector,
            "is_financials": int(is_financial_sector(broad_sector)),
            "net_profit_margin_pct": net_profit_margin(
                profit.get("net_profit"), profit.get("sales")
            ),
            "operating_profit_margin_pct": opm.calculated_opm_pct,
            "opm_source_pct": opm.source_opm_pct,
            "opm_difference_pct_points": opm.difference_pct_points,
            "opm_mismatch_flag": int(opm.exceeds_tolerance),
            "return_on_equity_pct": return_on_equity(
                profit.get("net_profit"),
                balance.get("equity_capital"),
                balance.get("reserves"),
            ),
            "return_on_capital_employed_pct": return_on_capital_employed(
                ebit,
                balance.get("equity_capital"),
                balance.get("reserves"),
                balance.get("borrowings"),
            ),
            "return_on_assets_pct": return_on_assets(
                profit.get("net_profit"), balance.get("total_assets")
            ),
            "debt_to_equity": debt_equity,
            "high_leverage_flag": (
                int(
                    high_leverage_flag(
                        debt_equity, broad_sector, sub_sector=sub_sector
                    )
                )
                if debt_equity is not None
                else None
            ),
            "interest_coverage": coverage.ratio,
            "icr_label": coverage.label,
            "icr_warning_flag": (
                int(coverage.warning_flag)
                if coverage.ratio is not None
                else None
            ),
            "net_debt_cr": net_debt(
                balance.get("borrowings"), balance.get("investments")
            ),
            "asset_turnover": asset_turnover(
                profit.get("sales"), balance.get("total_assets")
            ),
            "free_cash_flow_cr": cash_kpis.get("free_cash_flow_cr"),
            "capex_cr": cash_kpis.get("capex_cr"),
            "capex_intensity_pct": cash_kpis.get("capex_intensity_pct"),
            "capex_intensity_label": cash_kpis.get("capex_intensity_label"),
            "earnings_per_share": profit.get("eps"),
            "book_value_per_share": book_value_per_share(
                balance.get("equity_capital"),
                balance.get("reserves"),
                company.get("face_value"),
            ),
            "dividend_payout_ratio_pct": profit.get("dividend_payout"),
            "total_debt_cr": balance.get("borrowings"),
            "cash_from_operations_cr": cashflow.get("operating_activity"),
            "cfo_pat_ratio_5yr": cash_kpis.get("cfo_pat_ratio_5yr"),
            "cfo_quality_label": cash_kpis.get("cfo_quality_label"),
            "fcf_conversion_rate_pct": cash_kpis.get("fcf_conversion_rate_pct"),
            # Populated after the full cross-sectional metric set is assembled.
            "composite_quality_score": None,
        }
        row.update(_cagr_values(profit_histories.get(company_id, []), year))
        output.append({column: row.get(column) for column in FINANCIAL_RATIO_COLUMNS})

    return apply_composite_quality_scores(output)


def validate_ratio_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate Day 12 exit criteria before mutating SQLite."""
    keys = [(str(row["company_id"]), str(row["year"])) for row in rows]
    company_count = len({key[0] for key in keys})
    duplicate_count = len(keys) - len(set(keys))
    all_null_mandatory = [
        column
        for column in MANDATORY_KPI_COLUMNS
        if not any(row.get(column) is not None for row in rows)
    ]
    result = {
        "row_count": len(rows),
        "company_count": company_count,
        "duplicate_keys": duplicate_count,
        "mandatory_all_null_columns": all_null_mandatory,
    }
    if len(rows) < MINIMUM_EXPECTED_ROWS:
        raise ValueError(
            f"financial_ratios would contain {len(rows)} rows; "
            f"minimum is {MINIMUM_EXPECTED_ROWS}"
        )
    if company_count != EXPECTED_COMPANIES:
        raise ValueError(
            f"financial_ratios would contain {company_count} companies; "
            f"expected {EXPECTED_COMPANIES}"
        )
    if duplicate_count:
        raise ValueError(f"financial_ratios contains {duplicate_count} duplicate keys")
    if all_null_mandatory:
        raise ValueError(
            "Mandatory KPI columns are entirely null: " + ", ".join(all_null_mandatory)
        )
    return result


def ensure_schema(
    connection: sqlite3.Connection, schema_path: str | Path
) -> None:
    """Apply the current schema and verify that the Day 12 columns exist."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
    actual = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(financial_ratios)")
    }
    missing = [column for column in FINANCIAL_RATIO_COLUMNS if column not in actual]
    if missing:
        raise ValueError("financial_ratios schema is missing: " + ", ".join(missing))


def populate_financial_ratios(
    connection: sqlite3.Connection, rows: Sequence[Mapping[str, Any]]
) -> None:
    """Replace the analytical table atomically and idempotently."""
    validate_ratio_rows(rows)
    columns_sql = ", ".join(FINANCIAL_RATIO_COLUMNS)
    placeholders = ", ".join("?" for _ in FINANCIAL_RATIO_COLUMNS)
    values = [tuple(row.get(column) for column in FINANCIAL_RATIO_COLUMNS) for row in rows]
    with connection:
        connection.execute("DELETE FROM financial_ratios")
        connection.executemany(
            f"INSERT INTO financial_ratios ({columns_sql}) VALUES ({placeholders})",
            values,
        )


def _write_csv(
    path: str | Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def write_null_audit(
    rows: Sequence[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Record non-null coverage and Day 12 requirement status by column."""
    audit_rows = []
    for column in FINANCIAL_RATIO_COLUMNS:
        non_null = sum(row.get(column) is not None for row in rows)
        mandatory = column in MANDATORY_KPI_COLUMNS
        audit_rows.append(
            {
                "column": column,
                "mandatory_day12": mandatory,
                "non_null_rows": non_null,
                "null_rows": len(rows) - non_null,
                "non_null_pct": round(non_null / len(rows) * 100.0, 4),
                "status": "PASS" if (not mandatory or non_null > 0) else "FAIL",
            }
        )
    return _write_csv(
        output_path,
        audit_rows,
        ("column", "mandatory_day12", "non_null_rows", "null_rows", "non_null_pct", "status"),
    )


def _reference_candidates(
    workbook_path: str | Path,
) -> tuple[dict[tuple[str, str], dict[str, list[float]]], dict[str, int]]:
    import pandas as pd

    frame = pd.read_excel(Path(workbook_path), sheet_name="Sheet1")
    frame["company_id"] = frame["company_id"].map(normalize_ticker)
    frame["normalized_year"] = frame["year"].map(normalize_year)
    grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in frame.to_dict(orient="records"):
        key = (str(record["company_id"]), str(record["normalized_year"]))
        for metric in REFERENCE_KPI_COLUMNS:
            value = _finite_number(record.get(metric))
            if value is not None and value not in grouped[key][metric]:
                grouped[key][metric].append(value)
    group_sizes = frame.groupby(["company_id", "normalized_year"]).size()
    metadata = {
        "reference_rows": int(len(frame)),
        "reference_companies": int(frame["company_id"].nunique()),
        "reference_unique_keys": int(len(group_sizes)),
        "reference_duplicate_keys": int((group_sizes > 1).sum()),
    }
    return grouped, metadata


def compare_with_reference(
    rows: Sequence[Mapping[str, Any]], workbook_path: str | Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare every overlapping metric with all deterministic Excel candidates."""
    reference, metadata = _reference_candidates(workbook_path)
    comparisons: list[dict[str, Any]] = []
    engine_keys = {(str(row["company_id"]), str(row["year"])) for row in rows}
    for row in rows:
        key = (str(row["company_id"]), str(row["year"]))
        for metric in REFERENCE_KPI_COLUMNS:
            engine_value = _finite_number(row.get(metric))
            candidates = reference.get(key, {}).get(metric, [])
            closest = None
            absolute_difference = None
            relative_difference_pct = None
            if engine_value is None and not candidates:
                status = "BOTH_NULL_OR_UNAVAILABLE"
            elif engine_value is None:
                status = "ENGINE_NULL"
            elif not candidates:
                status = "REFERENCE_NULL_OR_KEY_ABSENT"
            else:
                closest = min(candidates, key=lambda value: abs(engine_value - value))
                absolute_difference = abs(engine_value - closest)
                relative_difference_pct = (
                    absolute_difference / abs(closest) * 100.0
                    if closest != 0
                    else (0.0 if absolute_difference == 0 else None)
                )
                status = (
                    "MATCH"
                    if math.isclose(engine_value, closest, rel_tol=0.001, abs_tol=0.05)
                    else "DIFFERENT"
                )
            comparisons.append(
                {
                    "company_id": key[0],
                    "year": key[1],
                    "metric": metric,
                    "engine_value": engine_value,
                    "closest_reference_value": closest,
                    "reference_candidate_count": len(candidates),
                    "absolute_difference": absolute_difference,
                    "relative_difference_pct": relative_difference_pct,
                    "status": status,
                }
            )

    statuses = Counter(row["status"] for row in comparisons)
    by_metric: dict[str, Counter[str]] = defaultdict(Counter)
    for comparison in comparisons:
        by_metric[str(comparison["metric"])][str(comparison["status"])] += 1
    overlapping_keys = len(engine_keys & set(reference))
    summary = {
        **metadata,
        "engine_rows": len(rows),
        "engine_companies": len({key[0] for key in engine_keys}),
        "engine_reference_overlapping_keys": overlapping_keys,
        "engine_keys_without_reference": len(engine_keys - set(reference)),
        "reference_keys_without_engine": len(set(reference) - engine_keys),
        "comparison_status_counts": dict(sorted(statuses.items())),
        "comparison_status_by_metric": {
            metric: dict(sorted(counts.items()))
            for metric, counts in sorted(by_metric.items())
        },
        "tolerance": "math.isclose(rel_tol=0.001, abs_tol=0.05)",
        "duplicate_policy": "compare engine value with closest distinct candidate per key/metric",
    }
    return comparisons, summary


def write_edge_case_log(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    additional_cases: Iterable[Mapping[str, Any]] = (),
) -> Path:
    """Write auditable denominator, cross-check and CAGR edge cases."""
    edge_cases: list[dict[str, Any]] = []
    for row in rows:
        base = {"company_id": row["company_id"], "year": row["year"]}
        if row.get("opm_mismatch_flag"):
            edge_cases.append(
                {**base, "category": "OPM_MISMATCH", "metric": "operating_profit_margin_pct", "detail": f"difference_pct_points={row.get('opm_difference_pct_points')}"}
            )
        if row.get("icr_label") == "Debt Free":
            edge_cases.append(
                {**base, "category": "DEBT_FREE", "metric": "interest_coverage", "detail": "zero interest and zero/unknown borrowings"}
            )
        for metric in ("net_profit_margin_pct", "return_on_equity_pct", "return_on_capital_employed_pct", "return_on_assets_pct", "debt_to_equity", "interest_coverage", "asset_turnover"):
            if row.get(metric) is None:
                edge_cases.append(
                    {**base, "category": "NULL_ALLOWED", "metric": metric, "detail": "source unavailable or documented denominator rule"}
                )
        for metric_name in CAGR_METRICS:
            for window in CAGR_WINDOWS:
                flag_column = f"{metric_name}_cagr_{window}yr_flag"
                flag = row.get(flag_column)
                if flag and flag != "OK":
                    edge_cases.append(
                        {**base, "category": "CAGR_EDGE_CASE", "metric": flag_column.removesuffix("_flag"), "detail": str(flag)}
                    )
    edge_cases.extend(dict(case) for case in additional_cases)
    return _write_csv(
        output_path,
        edge_cases,
        ("company_id", "year", "category", "metric", "detail"),
    )


def write_load_audit(
    connection: sqlite3.Connection,
    validation: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    """Write the Day 12 exit-gate checks in a compact CSV."""
    row_count, company_count = connection.execute(
        "SELECT COUNT(*), COUNT(DISTINCT company_id) FROM financial_ratios"
    ).fetchone()
    fk_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    all_null = validation["mandatory_all_null_columns"]
    audit_rows = [
        {"check": "financial_ratios_rows", "expected": f">={MINIMUM_EXPECTED_ROWS}", "actual": row_count, "status": "PASS" if row_count >= MINIMUM_EXPECTED_ROWS else "FAIL", "detail": "union of annual source keys"},
        {"check": "distinct_companies", "expected": EXPECTED_COMPANIES, "actual": company_count, "status": "PASS" if company_count == EXPECTED_COMPANIES else "FAIL", "detail": "COUNT(DISTINCT company_id)"},
        {"check": "duplicate_company_year_keys", "expected": 0, "actual": validation["duplicate_keys"], "status": "PASS" if validation["duplicate_keys"] == 0 else "FAIL", "detail": "UNIQUE(company_id, year)"},
        {"check": "mandatory_all_null_columns", "expected": 0, "actual": len(all_null), "status": "PASS" if not all_null else "FAIL", "detail": ", ".join(all_null) if all_null else "none"},
        {"check": "foreign_key_violations", "expected": 0, "actual": fk_violations, "status": "PASS" if fk_violations == 0 else "FAIL", "detail": "PRAGMA foreign_key_check"},
        {"check": "sqlite_integrity", "expected": "ok", "actual": integrity, "status": "PASS" if integrity.lower() == "ok" else "FAIL", "detail": "PRAGMA integrity_check"},
    ]
    if any(row["status"] != "PASS" for row in audit_rows):
        raise ValueError("Day 12 database audit failed")
    return _write_csv(
        output_path,
        audit_rows,
        ("check", "expected", "actual", "status", "detail"),
    )


def run_ratio_engine(
    *,
    database_path: str | Path = "db/nifty100.db",
    schema_path: str | Path = "db/schema.sql",
    reference_path: str | Path = "data/supporting/financial_ratios.xlsx",
    output_dir: str | Path = "output",
) -> RatioEngineResult:
    """Execute the complete Day 12 build, load, comparison and audit."""
    database = Path(database_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        ensure_schema(connection, schema_path)
        rows = build_financial_ratio_rows(connection)
        validation = validate_ratio_rows(rows)
        populate_financial_ratios(connection, rows)
        audit_path = write_load_audit(
            connection, validation, output / "ratio_engine_load_audit.csv"
        )
        null_audit_path = write_null_audit(
            rows, output / "financial_ratios_null_audit.csv"
        )
        comparisons, summary = compare_with_reference(rows, reference_path)
        comparison_path = _write_csv(
            output / "financial_ratios_reference_comparison.csv",
            comparisons,
            ("company_id", "year", "metric", "engine_value", "closest_reference_value", "reference_candidate_count", "absolute_difference", "relative_difference_pct", "status"),
        )
        comparison_summary_path = output / "financial_ratios_comparison_summary.json"
        summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        comparison_summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        sector_notes = build_financial_sector_notes(connection)
        sector_notes_path = write_sector_roce_notes(
            sector_notes, output / "sector_roce_notes.csv"
        )
        edge_case_path = write_edge_case_log(
            rows,
            output / "ratio_edge_cases.log",
            additional_cases=sector_note_edge_cases(sector_notes),
        )
        return RatioEngineResult(
            row_count=int(validation["row_count"]),
            company_count=int(validation["company_count"]),
            audit_path=audit_path,
            null_audit_path=null_audit_path,
            comparison_path=comparison_path,
            comparison_summary_path=comparison_summary_path,
            sector_notes_path=sector_notes_path,
            edge_case_path=edge_case_path,
        )
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Populate Sprint 2 financial ratios")
    parser.add_argument("--database", default="db/nifty100.db")
    parser.add_argument("--schema", default="db/schema.sql")
    parser.add_argument(
        "--reference", default="data/supporting/financial_ratios.xlsx"
    )
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args(argv)
    result = run_ratio_engine(
        database_path=args.database,
        schema_path=args.schema,
        reference_path=args.reference,
        output_dir=args.output_dir,
    )
    print(
        f"financial_ratios populated: {result.row_count} rows, "
        f"{result.company_count} companies; audit: {result.audit_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
