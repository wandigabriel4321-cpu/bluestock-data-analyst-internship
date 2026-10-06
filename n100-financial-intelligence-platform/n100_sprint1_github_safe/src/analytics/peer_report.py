"""Sprint 3 Day 20 peer-comparison Excel report.

The workbook contains exactly eleven worksheets, one for each official peer
group.  Every sheet presents two identifiers, twenty raw KPI columns and ten
percentile columns corresponding only to the metrics officially classified on
Day 18.  Each group ends with a recomputed median row.
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.analytics.peer import PEER_METRICS
from src.screener.composite_score import build_scored_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "peer_comparison.xlsx"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "output" / "peer_comparison_audit.csv"

OFFICIAL_GROUP_ORDER = (
    "Private Banks",
    "Public Sector Banks",
    "IT Services",
    "Pharmaceuticals",
    "Automobiles",
    "Life Insurance",
    "Oil & Gas",
    "Power & Utilities",
    "Steel",
    "FMCG",
    "Consumer Finance",
)

# The first ten official metric columns are populated from the same latest
# peer_percentiles observation that supplies the percentile shown beside it.
KPI_COLUMNS = (
    "sprint3_composite_score",
    "sector_relative_composite_score",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "free_cash_flow_cr",
    "fcf_cagr_5yr",
    "cfo_pat_ratio_5yr",
    "revenue_cagr_3yr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
    "sales",
)

PERCENTILE_COLUMNS: Mapping[str, str] = {
    "return_on_equity_pct": "return_on_equity_percentile",
    "return_on_capital_employed_pct": "return_on_capital_employed_percentile",
    "net_profit_margin_pct": "net_profit_margin_percentile",
    "debt_to_equity": "debt_to_equity_percentile",
    "free_cash_flow_cr": "free_cash_flow_percentile",
    "pat_cagr_5yr": "pat_cagr_5yr_percentile",
    "revenue_cagr_5yr": "revenue_cagr_5yr_percentile",
    "eps_cagr_5yr": "eps_cagr_5yr_percentile",
    "interest_coverage": "interest_coverage_percentile",
    "asset_turnover": "asset_turnover_percentile",
}

OUTPUT_COLUMNS = ("company_id", "company_name", *KPI_COLUMNS, *PERCENTILE_COLUMNS.values())
MEDIAN_ID = "GROUP_MEDIAN"

HEADER_FILL = PatternFill("solid", fgColor="17365D")
HEADER_FONT = Font(color="FFFFFF", bold=True)
BENCHMARK_FILL = PatternFill("solid", fgColor="F4B183")
MEDIAN_FILL = PatternFill("solid", fgColor="D9EAF7")
HIGH_FILL = PatternFill("solid", fgColor="C6EFCE")
MID_FILL = PatternFill("solid", fgColor="FFF2CC")
LOW_FILL = PatternFill("solid", fgColor="FFC7CE")
MISSING_FILL = PatternFill("solid", fgColor="E7E6E6")
THIN_GRAY = Side(style="thin", color="D9E1E8")

PERCENT_VALUE_COLUMNS = {
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "fcf_cagr_5yr",
    "revenue_cagr_3yr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "dividend_yield_pct",
}
CURRENCY_COLUMNS = {"free_cash_flow_cr", "sales"}
RATIO_COLUMNS = {
    "cfo_pat_ratio_5yr",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "pe_ratio",
    "pb_ratio",
}


def load_assignments(connection: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT pga.company_id, pga.peer_group_name, pga.is_benchmark,
                  c.company_name
           FROM peer_group_assignments AS pga
           JOIN companies AS c ON c.id = pga.company_id""",
        connection,
    )


def load_latest_official_peer_metrics(connection: sqlite3.Connection) -> pd.DataFrame:
    """Return latest non-null value/rank pairs for the ten official metrics."""

    return pd.read_sql_query(
        """WITH ranked AS (
               SELECT company_id, peer_group_name, metric, value,
                      percentile_rank, year,
                      ROW_NUMBER() OVER (
                          PARTITION BY company_id, metric
                          ORDER BY year DESC
                      ) AS row_number
               FROM peer_percentiles
               WHERE value IS NOT NULL AND percentile_rank IS NOT NULL
           )
           SELECT company_id, peer_group_name, metric, value,
                  percentile_rank, year
           FROM ranked
           WHERE row_number = 1
           ORDER BY peer_group_name, company_id, metric""",
        connection,
    )


def build_peer_report_rows(database_path: str | Path = DEFAULT_DATABASE_PATH) -> pd.DataFrame:
    """Build one report row for each of the 56 assigned companies."""

    database = Path(database_path)
    with sqlite3.connect(database) as connection:
        assignments = load_assignments(connection)
        official = load_latest_official_peer_metrics(connection)

    scored, _ = build_scored_snapshot(database)
    missing_kpis = set(KPI_COLUMNS).difference(scored.columns)
    if missing_kpis:
        raise ValueError("Scored snapshot is missing KPIs: " + ", ".join(sorted(missing_kpis)))
    base = assignments.merge(
        scored[["company_id", *KPI_COLUMNS]],
        on="company_id",
        how="left",
        validate="one_to_one",
    )

    value_pivot = official.pivot(index="company_id", columns="metric", values="value")
    rank_pivot = official.pivot(
        index="company_id", columns="metric", values="percentile_rank"
    )
    year_pivot = official.pivot(index="company_id", columns="metric", values="year")
    for metric, percentile_column in PERCENTILE_COLUMNS.items():
        value_map = value_pivot[metric] if metric in value_pivot else pd.Series(dtype=float)
        rank_map = rank_pivot[metric] if metric in rank_pivot else pd.Series(dtype=float)
        year_map = year_pivot[metric] if metric in year_pivot else pd.Series(dtype=object)
        # The raw official KPI and its percentile always originate from the
        # same peer_percentiles row and therefore cannot silently disagree.
        base[metric] = base["company_id"].map(value_map)
        base[percentile_column] = base["company_id"].map(rank_map)
        base[f"_{metric}_year"] = base["company_id"].map(year_map)

    if len(base) != 56 or base["company_id"].nunique() != 56:
        raise ValueError("Peer report must contain exactly 56 unique assigned companies")
    if base["peer_group_name"].nunique() != 11:
        raise ValueError("Peer report must contain exactly 11 official groups")
    return base


def _median_row(group_name: str, companies: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {
        "company_id": MEDIAN_ID,
        "company_name": f"{group_name} Median",
    }
    for column in (*KPI_COLUMNS, *PERCENTILE_COLUMNS.values()):
        values = pd.to_numeric(companies[column], errors="coerce")
        row[column] = float(values.median()) if values.notna().any() else None
    return row


def build_group_frames(rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return eleven frames, each ending with its calculated median row."""

    frames: dict[str, pd.DataFrame] = {}
    for group_name in OFFICIAL_GROUP_ORDER:
        companies = rows.loc[rows["peer_group_name"].eq(group_name)].copy()
        if companies.empty:
            raise ValueError(f"Official peer group is missing: {group_name}")
        companies = companies.sort_values(
            ["sprint3_composite_score", "company_id"],
            ascending=[False, True],
            na_position="last",
            kind="stable",
        )
        presentation = companies.loc[:, OUTPUT_COLUMNS].reset_index(drop=True)
        median = pd.DataFrame([_median_row(group_name, presentation)])
        frames[group_name] = pd.concat([presentation, median], ignore_index=True)
    if sum(len(frame) - 1 for frame in frames.values()) != 56:
        raise ValueError("Group frames do not preserve all 56 assigned companies")
    return frames


def _number_format(header: str) -> str:
    if header in PERCENT_VALUE_COLUMNS:
        return '0.00"%"'
    if header in CURRENCY_COLUMNS:
        return '₹#,##0.00 "Cr"'
    if header in RATIO_COLUMNS:
        return '0.00"x"'
    if header in PERCENTILE_COLUMNS.values():
        return "0.00"
    if header in {"sprint3_composite_score", "sector_relative_composite_score"}:
        return "0.00"
    return "0.00"


def percentile_fill(value: Any) -> PatternFill:
    """Apply official boundary precedence: >=75 green and <=25 red."""

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return MISSING_FILL
    number = float(value)
    if number >= 75.0:
        return HIGH_FILL
    if number <= 25.0:
        return LOW_FILL
    return MID_FILL


def style_peer_workbook(
    workbook_path: str | Path,
    benchmark_by_group: Mapping[str, str],
) -> None:
    workbook = load_workbook(workbook_path)
    for group_name in OFFICIAL_GROUP_ORDER:
        worksheet = workbook[group_name]
        worksheet.freeze_panes = "C2"
        worksheet.sheet_view.showGridLines = False
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.page_setup.orientation = "landscape"
        worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A3
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.print_title_rows = "1:1"
        company_last_row = worksheet.max_row - 1
        worksheet.auto_filter.ref = f"A1:{get_column_letter(worksheet.max_column)}{company_last_row}"
        worksheet.row_dimensions[1].height = 42
        for cell in worksheet[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=THIN_GRAY)

        headers = {str(cell.value): cell.column for cell in worksheet[1]}
        for percentile_column in PERCENTILE_COLUMNS.values():
            worksheet.cell(1, headers[percentile_column]).comment = Comment(
                "Official Day 18 percentile rank (0–100). D/E is inverted so lower is better.",
                "N100 Sprint 3",
            )

        benchmark_id = benchmark_by_group[group_name]
        for row_number in range(2, worksheet.max_row + 1):
            company_id = worksheet.cell(row_number, 1).value
            is_median = company_id == MEDIAN_ID
            is_benchmark = company_id == benchmark_id
            for column_number in range(1, worksheet.max_column + 1):
                cell = worksheet.cell(row_number, column_number)
                header = str(worksheet.cell(1, column_number).value)
                cell.alignment = Alignment(vertical="center", wrap_text=False)
                cell.border = Border(bottom=THIN_GRAY)
                if column_number > 2 and isinstance(cell.value, (int, float)):
                    cell.number_format = _number_format(header)
                if is_median:
                    cell.fill = MEDIAN_FILL
                    cell.font = Font(bold=True, color="17365D")
                elif is_benchmark:
                    cell.fill = BENCHMARK_FILL
                    cell.font = Font(bold=True, color="7F3F00")
                elif header in PERCENTILE_COLUMNS.values():
                    cell.fill = percentile_fill(cell.value)

        for column_number, cell in enumerate(worksheet[1], start=1):
            header = str(cell.value)
            if header == "company_id":
                width = 18
            elif header == "company_name":
                width = 30
            elif header in PERCENTILE_COLUMNS.values():
                width = 22
            else:
                width = min(max(len(header) + 2, 16), 28)
            worksheet.column_dimensions[get_column_letter(column_number)].width = width
    workbook.active = 0
    workbook.save(workbook_path)


def write_peer_workbook(
    frames: Mapping[str, pd.DataFrame],
    benchmark_by_group: Mapping[str, str],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destination, engine="openpyxl") as writer:
        for group_name in OFFICIAL_GROUP_ORDER:
            frames[group_name].to_excel(writer, sheet_name=group_name, index=False)
    style_peer_workbook(destination, benchmark_by_group)
    return destination


def validate_peer_workbook(
    workbook_path: str | Path,
    benchmark_by_group: Mapping[str, str],
) -> pd.DataFrame:
    workbook = load_workbook(workbook_path, data_only=False)
    if tuple(workbook.sheetnames) != OFFICIAL_GROUP_ORDER:
        raise ValueError("Workbook must contain exactly the 11 official peer-group sheets")
    audits: list[dict[str, Any]] = []
    all_company_ids: list[str] = []
    for group_name in OFFICIAL_GROUP_ORDER:
        worksheet = workbook[group_name]
        headers = [str(cell.value) for cell in worksheet[1]]
        if tuple(headers) != OUTPUT_COLUMNS:
            raise ValueError(f"Unexpected columns in worksheet {group_name}")
        rows = list(worksheet.iter_rows(min_row=2, values_only=True))
        records = pd.DataFrame(rows, columns=headers)
        median_rows = records.loc[records["company_id"].eq(MEDIAN_ID)]
        companies = records.loc[~records["company_id"].eq(MEDIAN_ID)].copy()
        all_company_ids.extend(companies["company_id"].astype(str).tolist())
        benchmark_id = benchmark_by_group[group_name]
        benchmark_count = int(companies["company_id"].eq(benchmark_id).sum())
        duplicate_count = int(companies["company_id"].duplicated().sum())

        median_correct = len(median_rows) == 1
        if median_correct:
            median = median_rows.iloc[0]
            for column in (*KPI_COLUMNS, *PERCENTILE_COLUMNS.values()):
                values = pd.to_numeric(companies[column], errors="coerce")
                expected = float(values.median()) if values.notna().any() else None
                actual = median[column]
                if expected is None:
                    valid = actual is None or pd.isna(actual)
                else:
                    valid = actual is not None and math.isclose(float(actual), expected, abs_tol=1e-9)
                if not valid:
                    median_correct = False
                    break

        percentile_values = companies[list(PERCENTILE_COLUMNS.values())].apply(
            pd.to_numeric, errors="coerce"
        )
        percentiles_in_range = bool(
            percentile_values.stack().between(0.0, 100.0, inclusive="both").all()
        )
        benchmark_row_number = int(
            companies.index[companies["company_id"].eq(benchmark_id)][0] + 2
        ) if benchmark_count == 1 else -1
        benchmark_gold = (
            benchmark_row_number > 0
            and worksheet.cell(benchmark_row_number, 1).fill.fgColor.rgb == "00F4B183"
        )
        median_styled = worksheet.cell(worksheet.max_row, 1).fill.fgColor.rgb == "00D9EAF7"
        status = "PASS" if all(
            [
                len(headers) == 32,
                benchmark_count == 1,
                duplicate_count == 0,
                median_correct,
                percentiles_in_range,
                benchmark_gold,
                median_styled,
                worksheet.freeze_panes == "C2",
                bool(worksheet.auto_filter.ref),
            ]
        ) else "FAIL"
        audits.append(
            {
                "sheet_name": group_name,
                "company_rows": len(companies),
                "column_count": len(headers),
                "kpi_columns": len(KPI_COLUMNS),
                "percentile_columns": len(PERCENTILE_COLUMNS),
                "benchmark_company_id": benchmark_id,
                "benchmark_count": benchmark_count,
                "benchmark_gold": benchmark_gold,
                "duplicate_companies": duplicate_count,
                "median_correct": median_correct,
                "median_styled": median_styled,
                "percentiles_in_range": percentiles_in_range,
                "freeze_panes": str(worksheet.freeze_panes),
                "auto_filter": worksheet.auto_filter.ref,
                "status": status,
            }
        )
    if len(all_company_ids) != 56 or len(set(all_company_ids)) != 56:
        raise ValueError("Workbook does not represent all 56 companies exactly once")
    audit = pd.DataFrame(audits)
    if not audit["status"].eq("PASS").all():
        raise ValueError("One or more peer-comparison worksheets failed validation")
    return audit


def run_day20(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    audit_path: str | Path = DEFAULT_AUDIT_PATH,
) -> dict[str, Any]:
    rows = build_peer_report_rows(database_path)
    benchmark_by_group = {
        str(group): str(frame.loc[frame["is_benchmark"].eq(1), "company_id"].iloc[0])
        for group, frame in rows.groupby("peer_group_name", sort=False)
    }
    if len(benchmark_by_group) != 11:
        raise ValueError("Expected one benchmark for each of 11 peer groups")
    frames = build_group_frames(rows)
    destination = write_peer_workbook(frames, benchmark_by_group, output_path)
    audit = validate_peer_workbook(destination, benchmark_by_group)
    audit_target = Path(audit_path)
    audit_target.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_target, index=False)
    return {
        "output_path": destination,
        "audit_path": audit_target,
        "rows": rows,
        "frames": frames,
        "audit": audit,
        "benchmark_by_group": benchmark_by_group,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_day20(args.database, output_path=args.output, audit_path=args.audit)
    print(
        f"Day 20 complete: {len(result['audit'])} sheets, "
        f"{len(result['rows'])} companies, {len(KPI_COLUMNS)} KPIs, "
        f"{len(PERCENTILE_COLUMNS)} percentile columns; all validations PASS."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
