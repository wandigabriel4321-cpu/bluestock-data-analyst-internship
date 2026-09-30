"""Sprint 2 Day 14 final checks and reproducible review evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.etl.loader import ExcelLoader


REVIEW_SEED = "20260929"
SCREENER_MIN_COMPANIES = 15
SCREENER_MAX_COMPANIES = 50
STRICT_MANUAL_TOLERANCE = 0.1
GENERAL_MANUAL_TOLERANCE = 2.0

SCREENER_COLUMNS = (
    "company_id",
    "company_name",
    "year",
    "broad_sector",
    "return_on_equity_pct",
    "debt_to_equity",
    "business_review_status",
    "business_review_note",
)

MANUAL_VALIDATION_COLUMNS = (
    "sample_seed",
    "sample_rank",
    "company_id",
    "company_name",
    "start_year",
    "end_year",
    "source_net_profit",
    "source_equity_capital",
    "source_reserves",
    "manual_roe_pct",
    "database_roe_pct",
    "roe_abs_difference_pct_points",
    "source_sales_start",
    "source_sales_end",
    "manual_revenue_cagr_5yr_pct",
    "database_revenue_cagr_5yr_pct",
    "cagr_abs_difference_pct_points",
    "maximum_abs_difference_pct_points",
    "strict_below_0_1_pct",
    "general_within_2_pct",
    "review_status",
)


class Sprint2ReviewError(RuntimeError):
    """Raised when a Day 14 exit criterion is not satisfied."""


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def manual_roe(net_profit: Any, equity_capital: Any, reserves: Any) -> float | None:
    """Recalculate ROE from the original annual P&L and balance sheet."""
    profit = _finite_number(net_profit)
    equity = _finite_number(equity_capital)
    retained = _finite_number(reserves)
    if profit is None or equity is None or retained is None:
        return None
    capital_base = equity + retained
    if capital_base <= 0:
        return None
    return profit / capital_base * 100.0


def manual_cagr(start_value: Any, end_value: Any, years: int = 5) -> float | None:
    """Recalculate an ordinary positive-to-positive CAGR."""
    start = _finite_number(start_value)
    end = _finite_number(end_value)
    if start is None or end is None or start <= 0 or end <= 0 or years <= 0:
        return None
    return ((end / start) ** (1.0 / years) - 1.0) * 100.0


def _subtract_years(reporting_period: str, years: int) -> str:
    year, month = reporting_period.split("-", 1)
    return f"{int(year) - years:04d}-{month}"


def select_reproducible_ids(
    company_ids: Iterable[str], sample_size: int = 5, seed: str = REVIEW_SEED
) -> list[str]:
    """Select stable company IDs by SHA-256 rank."""
    unique = sorted({str(company_id) for company_id in company_ids})
    if len(unique) < sample_size:
        raise Sprint2ReviewError(
            f"Cannot sample {sample_size} companies from {len(unique)} eligible IDs"
        )
    return sorted(
        unique,
        key=lambda company_id: (
            hashlib.sha256(f"{seed}:{company_id}".encode("utf-8")).hexdigest(),
            company_id,
        ),
    )[:sample_size]


def build_screener_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the latest per-company rows meeting the preliminary screen."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        WITH latest AS (
            SELECT company_id, MAX(year) AS year
            FROM financial_ratios
            WHERE return_on_equity_pct IS NOT NULL
              AND debt_to_equity IS NOT NULL
            GROUP BY company_id
        )
        SELECT
            f.company_id,
            c.company_name,
            f.year,
            f.broad_sector,
            f.return_on_equity_pct,
            f.debt_to_equity
        FROM financial_ratios AS f
        JOIN latest AS l
          ON l.company_id = f.company_id AND l.year = f.year
        JOIN companies AS c ON c.id = f.company_id
        WHERE f.return_on_equity_pct > 15.0
          AND f.debt_to_equity < 1.0
        ORDER BY f.return_on_equity_pct DESC, f.company_id
        """
    ).fetchall()

    output: list[dict[str, Any]] = []
    for row in rows:
        roe = float(row["return_on_equity_pct"])
        needs_review = abs(roe) > 100.0
        output.append(
            {
                "company_id": row["company_id"],
                "company_name": row["company_name"],
                "year": row["year"],
                "broad_sector": row["broad_sector"],
                "return_on_equity_pct": roe,
                "debt_to_equity": float(row["debt_to_equity"]),
                "business_review_status": (
                    "REVIEW_SOURCE_BASE" if needs_review else "PASS"
                ),
                "business_review_note": (
                    "ROE exceeds 100%; inspect the source equity/reserve base before investment use."
                    if needs_review
                    else "Meets the preliminary ROE and D/E criteria."
                ),
            }
        )
    return output


def audit_edge_case_log(path: str | Path) -> dict[str, Any]:
    """Confirm every logged edge case has a usable explanation."""
    log_path = Path(path)
    if not log_path.exists():
        raise Sprint2ReviewError(f"Missing edge-case log: {log_path}")
    with log_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"company_id", "year", "category", "metric", "detail"}
    if not rows:
        raise Sprint2ReviewError("The edge-case log contains no review rows")
    if not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0]))
        raise Sprint2ReviewError(f"Edge-case log is missing columns: {missing}")
    unexplained = [
        row
        for row in rows
        if not str(row.get("category", "")).strip()
        or not str(row.get("metric", "")).strip()
        or not str(row.get("detail", "")).strip()
    ]
    categories = Counter(str(row["category"]).strip() for row in rows)
    return {
        "total_entries": len(rows),
        "explained_entries": len(rows) - len(unexplained),
        "unexplained_entries": len(unexplained),
        "category_counts": dict(sorted(categories.items())),
        "status": "PASS" if not unexplained else "FAIL",
    }


def _eligible_manual_rows(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        WITH latest AS (
            SELECT company_id, MAX(year) AS year
            FROM financial_ratios
            WHERE return_on_equity_pct IS NOT NULL
              AND revenue_cagr_5yr IS NOT NULL
            GROUP BY company_id
        )
        SELECT
            f.company_id,
            c.company_name,
            f.year,
            f.return_on_equity_pct,
            f.revenue_cagr_5yr
        FROM financial_ratios AS f
        JOIN latest AS l
          ON l.company_id = f.company_id AND l.year = f.year
        JOIN companies AS c ON c.id = f.company_id
        ORDER BY f.company_id
        """
    ).fetchall()
    return {str(row["company_id"]): row for row in rows}


def _source_row(
    frame: pd.DataFrame, company_id: str, reporting_period: str
) -> Mapping[str, Any]:
    selected = frame[
        frame["company_id"].astype(str).eq(company_id)
        & frame["year"].astype(str).eq(reporting_period)
    ]
    if len(selected) != 1:
        raise Sprint2ReviewError(
            f"Expected one original row for {company_id} {reporting_period}; found {len(selected)}"
        )
    return selected.iloc[0].to_dict()


def build_manual_validation_rows(
    connection: sqlite3.Connection,
    profitandloss: pd.DataFrame,
    balancesheet: pd.DataFrame,
    *,
    sample_size: int = 5,
    seed: str = REVIEW_SEED,
) -> list[dict[str, Any]]:
    """Recalculate ROE and five-year Revenue CAGR for a stable sample."""
    eligible = _eligible_manual_rows(connection)
    selected_ids = select_reproducible_ids(eligible, sample_size, seed)
    output: list[dict[str, Any]] = []

    for rank, company_id in enumerate(selected_ids, 1):
        database_row = eligible[company_id]
        end_year = str(database_row["year"])
        start_year = _subtract_years(end_year, 5)
        end_profit = _source_row(profitandloss, company_id, end_year)
        start_profit = _source_row(profitandloss, company_id, start_year)
        end_balance = _source_row(balancesheet, company_id, end_year)

        calculated_roe = manual_roe(
            end_profit["net_profit"],
            end_balance["equity_capital"],
            end_balance["reserves"],
        )
        calculated_cagr = manual_cagr(
            start_profit["sales"], end_profit["sales"], 5
        )
        if calculated_roe is None or calculated_cagr is None:
            raise Sprint2ReviewError(
                f"Manual formulas are not calculable for {company_id} {end_year}"
            )

        database_roe = float(database_row["return_on_equity_pct"])
        database_cagr = float(database_row["revenue_cagr_5yr"])
        roe_difference = abs(calculated_roe - database_roe)
        cagr_difference = abs(calculated_cagr - database_cagr)
        maximum_difference = max(roe_difference, cagr_difference)
        strict_pass = maximum_difference < STRICT_MANUAL_TOLERANCE
        general_pass = maximum_difference <= GENERAL_MANUAL_TOLERANCE
        output.append(
            {
                "sample_seed": seed,
                "sample_rank": rank,
                "company_id": company_id,
                "company_name": database_row["company_name"],
                "start_year": start_year,
                "end_year": end_year,
                "source_net_profit": end_profit["net_profit"],
                "source_equity_capital": end_balance["equity_capital"],
                "source_reserves": end_balance["reserves"],
                "manual_roe_pct": calculated_roe,
                "database_roe_pct": database_roe,
                "roe_abs_difference_pct_points": roe_difference,
                "source_sales_start": start_profit["sales"],
                "source_sales_end": end_profit["sales"],
                "manual_revenue_cagr_5yr_pct": calculated_cagr,
                "database_revenue_cagr_5yr_pct": database_cagr,
                "cagr_abs_difference_pct_points": cagr_difference,
                "maximum_abs_difference_pct_points": maximum_difference,
                "strict_below_0_1_pct": "PASS" if strict_pass else "FAIL",
                "general_within_2_pct": "PASS" if general_pass else "FAIL",
                "review_status": "PASS" if general_pass else "FAIL",
            }
        )
    return output


def _write_csv(
    rows: Iterable[Mapping[str, Any]], columns: Sequence[str], destination: Path
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return destination


def run_sprint2_review(
    *,
    database_path: str | Path = "db/nifty100.db",
    raw_dir: str | Path = "data/raw",
    output_dir: str | Path = "output",
    edge_case_path: str | Path = "output/ratio_edge_cases.log",
    seed: str = REVIEW_SEED,
) -> dict[str, Any]:
    """Run all data-based Day 14 review gates and write auditable evidence."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="n100_day14_source_") as temporary:
        loader = ExcelLoader(temporary)
        profitandloss = loader.load_file(Path(raw_dir) / "profitandloss.xlsx").dataframe
        balancesheet = loader.load_file(Path(raw_dir) / "balancesheet.xlsx").dataframe

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        foreign_key_violations = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        ratio_rows = int(
            connection.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
        )
        company_count = int(
            connection.execute(
                "SELECT COUNT(DISTINCT company_id) FROM financial_ratios"
            ).fetchone()[0]
        )
        screener_rows = build_screener_rows(connection)
        manual_rows = build_manual_validation_rows(
            connection, profitandloss, balancesheet, seed=seed
        )

    edge_review = audit_edge_case_log(edge_case_path)
    screener_path = _write_csv(
        screener_rows, SCREENER_COLUMNS, destination / "screener_preview.csv"
    )
    manual_path = _write_csv(
        manual_rows,
        MANUAL_VALIDATION_COLUMNS,
        destination / "manual_kpi_validation.csv",
    )

    strict_pass_count = sum(
        row["strict_below_0_1_pct"] == "PASS" for row in manual_rows
    )
    general_pass_count = sum(
        row["general_within_2_pct"] == "PASS" for row in manual_rows
    )
    screener_count = len(screener_rows)
    screener_gate = SCREENER_MIN_COMPANIES <= screener_count <= SCREENER_MAX_COMPANIES
    summary = {
        "review_date": datetime.now(timezone.utc).date().isoformat(),
        "ratio_rows": ratio_rows,
        "distinct_companies": company_count,
        "foreign_key_violations": foreign_key_violations,
        "database_integrity": integrity,
        "edge_case_review": edge_review,
        "screener": {
            "rule": "latest calculable ROE > 15% and D/E < 1",
            "company_count": screener_count,
            "required_minimum": SCREENER_MIN_COMPANIES,
            "required_maximum": SCREENER_MAX_COMPANIES,
            "source_base_review_count": sum(
                row["business_review_status"] != "PASS" for row in screener_rows
            ),
            "status": "PASS" if screener_gate else "FAIL",
            "output": str(screener_path),
        },
        "manual_validation": {
            "sample_seed": seed,
            "sample_size": len(manual_rows),
            "selected_companies": [row["company_id"] for row in manual_rows],
            "strict_below_0_1_pct_passes": strict_pass_count,
            "strict_required_passes": 3,
            "general_within_2_pct_passes": general_pass_count,
            "general_required_passes": len(manual_rows),
            "maximum_observed_difference_pct_points": max(
                row["maximum_abs_difference_pct_points"] for row in manual_rows
            ),
            "status": (
                "PASS"
                if strict_pass_count >= 3 and general_pass_count == len(manual_rows)
                else "FAIL"
            ),
            "output": str(manual_path),
        },
    }
    summary["overall_status"] = (
        "PASS"
        if ratio_rows >= 1_100
        and company_count == 92
        and foreign_key_violations == 0
        and integrity == "ok"
        and edge_review["status"] == "PASS"
        and screener_gate
        and summary["manual_validation"]["status"] == "PASS"
        else "FAIL"
    )
    summary_path = destination / "sprint2_final_review_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if summary["overall_status"] != "PASS":
        raise Sprint2ReviewError(f"Day 14 review failed; see {summary_path}")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Sprint 2 Day 14 review")
    parser.add_argument("--database", default="db/nifty100.db")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--edge-case-log", default="output/ratio_edge_cases.log")
    parser.add_argument("--seed", default=REVIEW_SEED)
    args = parser.parse_args(argv)
    summary = run_sprint2_review(
        database_path=args.database,
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        edge_case_path=args.edge_case_log,
        seed=args.seed,
    )
    print(
        "Sprint 2 final review PASS: "
        f"{summary['screener']['company_count']} screener companies; "
        f"{summary['manual_validation']['sample_size']} manual validations; "
        f"{summary['edge_case_review']['total_entries']} explained edge cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
