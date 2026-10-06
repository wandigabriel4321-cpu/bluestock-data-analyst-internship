"""Sprint 3 Day 15 configurable financial screener.

The engine builds one current snapshot per company from the latest available
row in each source table.  Missing values remain missing: they are never
replaced by zero.  A company with a missing value fails only the filter that
requires that value, except for the two documented business rules:

* Financials are exempt from the ordinary maximum Debt-to-Equity filter.
* ``icr_label = 'Debt Free'`` is treated as infinite Interest Coverage.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "db" / "nifty100.db"

ALLOWED_DIRECTIONS = {"min", "max", "eq"}
SNAPSHOT_COLUMNS = {
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "operating_profit_margin_pct",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
    "interest_coverage",
    "market_cap_crore",
    "net_profit",
    "eps_cagr_5yr",
    "asset_turnover",
    "sales",
    "dividend_payout_ratio_pct",
    "revenue_cagr_3yr",
    "previous_debt_to_equity",
    "cfo_pat_ratio_5yr",
}


class ScreenerConfigError(ValueError):
    """Raised when the YAML configuration or requested filters are invalid."""


class ScreenerDataError(RuntimeError):
    """Raised when the SQLite source cannot provide a valid company snapshot."""


LATEST_COMPANY_SNAPSHOT_SQL = """
WITH ranked_ratios AS (
    SELECT fr.*,
           ROW_NUMBER() OVER (
               PARTITION BY fr.company_id
               ORDER BY fr.year DESC, fr.id DESC
           ) AS row_number
    FROM financial_ratios AS fr
    WHERE fr.return_on_equity_pct IS NOT NULL
       OR fr.free_cash_flow_cr IS NOT NULL
       OR fr.revenue_cagr_5yr IS NOT NULL
       OR fr.pat_cagr_5yr IS NOT NULL
       OR fr.operating_profit_margin_pct IS NOT NULL
       OR fr.interest_coverage IS NOT NULL
       OR fr.icr_label = 'Debt Free'
       OR fr.eps_cagr_5yr IS NOT NULL
       OR fr.asset_turnover IS NOT NULL
),
latest_ratios AS (
    SELECT * FROM ranked_ratios WHERE row_number = 1
),
previous_ratios AS (
    SELECT * FROM ranked_ratios WHERE row_number = 2
),
latest_market_cap AS (
    SELECT *
    FROM (
        SELECT mc.*,
               ROW_NUMBER() OVER (
                   PARTITION BY mc.company_id
                   ORDER BY mc.year DESC, mc.id DESC
               ) AS row_number
        FROM market_cap AS mc
    )
    WHERE row_number = 1
),
latest_profitandloss AS (
    SELECT *
    FROM (
        SELECT pl.*,
               ROW_NUMBER() OVER (
                   PARTITION BY pl.company_id
                   ORDER BY pl.year DESC, pl.id DESC
               ) AS row_number
        FROM profitandloss AS pl
    )
    WHERE row_number = 1
)
SELECT
    c.id AS company_id,
    c.company_name,
    COALESCE(s.broad_sector, fr.broad_sector) AS broad_sector,
    s.sub_sector,
    fr.year AS financial_year,
    mc.year AS market_cap_year,
    pl.year AS profitandloss_year,
    fr.return_on_equity_pct,
    fr.return_on_capital_employed_pct,
    fr.net_profit_margin_pct,
    fr.debt_to_equity,
    fr.free_cash_flow_cr,
    fr.revenue_cagr_3yr,
    fr.revenue_cagr_5yr,
    fr.pat_cagr_5yr,
    fr.operating_profit_margin_pct,
    mc.pe_ratio,
    mc.pb_ratio,
    mc.dividend_yield_pct,
    fr.interest_coverage,
    fr.icr_label,
    mc.market_cap_crore,
    pl.net_profit,
    fr.eps_cagr_5yr,
    fr.asset_turnover,
    fr.dividend_payout_ratio_pct,
    fr.cfo_pat_ratio_5yr,
    previous_fr.year AS previous_financial_year,
    previous_fr.debt_to_equity AS previous_debt_to_equity,
    pl.sales,
    fr.composite_quality_score
FROM companies AS c
LEFT JOIN latest_ratios AS fr ON fr.company_id = c.id
LEFT JOIN previous_ratios AS previous_fr ON previous_fr.company_id = c.id
LEFT JOIN latest_market_cap AS mc ON mc.company_id = c.id
LEFT JOIN latest_profitandloss AS pl ON pl.company_id = c.id
LEFT JOIN sectors AS s ON s.company_id = c.id
ORDER BY c.id
"""


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_metric_definitions(metrics: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(metrics, dict) or not metrics:
        raise ScreenerConfigError("Configuration must define a non-empty 'metrics' mapping")

    validated: dict[str, dict[str, Any]] = {}
    for key, definition in metrics.items():
        if not isinstance(key, str) or not key.strip():
            raise ScreenerConfigError("Every metric key must be a non-empty string")
        if not isinstance(definition, dict):
            raise ScreenerConfigError(f"Metric '{key}' must be a mapping")

        column = definition.get("column")
        direction = definition.get("direction")
        if column not in SNAPSHOT_COLUMNS:
            raise ScreenerConfigError(
                f"Metric '{key}' refers to unsupported snapshot column '{column}'"
            )
        if direction not in ALLOWED_DIRECTIONS:
            raise ScreenerConfigError(
                f"Metric '{key}' direction must be one of {sorted(ALLOWED_DIRECTIONS)}"
            )

        validated[key] = {
            "column": column,
            "direction": direction,
            "financials_exempt": bool(definition.get("financials_exempt", False)),
            "debt_free_as_infinity": bool(
                definition.get("debt_free_as_infinity", False)
            ),
            "label": str(definition.get("label", key)),
        }
    return validated


def validate_filters(
    filters: Any,
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> dict[str, float]:
    """Validate filter names and finite numeric thresholds."""

    if filters is None:
        return {}
    if not isinstance(filters, Mapping):
        raise ScreenerConfigError("Filters must be supplied as a mapping")

    validated: dict[str, float] = {}
    for key, threshold in filters.items():
        if key not in metric_definitions:
            raise ScreenerConfigError(f"Unknown screener metric: {key}")
        if threshold is None:
            continue
        if not _is_number(threshold):
            raise ScreenerConfigError(
                f"Threshold for '{key}' must be a finite number, not {threshold!r}"
            )
        validated[key] = float(threshold)
    return validated


def load_screener_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and validate the analyst-editable YAML configuration."""

    config_path = Path(path)
    if not config_path.is_file():
        raise ScreenerConfigError(f"Screener configuration not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScreenerConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ScreenerConfigError("Screener configuration root must be a mapping")

    metrics = _validate_metric_definitions(raw.get("metrics"))
    active_filters = validate_filters(raw.get("active_filters", {}), metrics)
    output = raw.get("output", {})
    if not isinstance(output, dict):
        raise ScreenerConfigError("The 'output' section must be a mapping")

    return {
        **raw,
        "metrics": metrics,
        "active_filters": active_filters,
        "output": output,
    }


def load_latest_company_metrics(database_path: str | Path) -> pd.DataFrame:
    """Return one row per company using the latest substantive source rows.

    A balance-sheet-only interim row is not allowed to replace a more recent
    row containing the operating, cash-flow, growth or efficiency metrics used
    by the screener. Market-cap and P&L records keep their own latest periods.
    """

    path = Path(database_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ScreenerDataError(f"SQLite database is missing or empty: {path}")

    try:
        with sqlite3.connect(path) as connection:
            frame = pd.read_sql_query(LATEST_COMPANY_SNAPSHOT_SQL, connection)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise ScreenerDataError(f"Unable to build screener snapshot: {exc}") from exc

    if frame.empty:
        raise ScreenerDataError("The screener snapshot contains no companies")
    if frame["company_id"].isna().any():
        raise ScreenerDataError("The screener snapshot contains a missing company_id")
    duplicates = frame["company_id"].duplicated(keep=False)
    if duplicates.any():
        ids = sorted(frame.loc[duplicates, "company_id"].astype(str).unique())
        raise ScreenerDataError(f"Duplicate companies in screener snapshot: {ids}")
    return frame


def _normalised_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.casefold()


def apply_filters(
    frame: pd.DataFrame,
    filters: Mapping[str, Any],
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    """Apply simultaneous filters and return results sorted by quality score."""

    validated = validate_filters(filters, metric_definitions)
    required_base = {"company_id", "broad_sector", "icr_label"}
    missing_base = required_base.difference(frame.columns)
    if missing_base:
        raise ScreenerDataError(
            f"Snapshot is missing required columns: {sorted(missing_base)}"
        )

    result = frame.copy()
    keep = pd.Series(True, index=result.index, dtype=bool)
    sectors = _normalised_text(result["broad_sector"])
    icr_labels = _normalised_text(result["icr_label"])

    for key, threshold in validated.items():
        definition = metric_definitions[key]
        column = str(definition["column"])
        if column not in result.columns:
            raise ScreenerDataError(
                f"Snapshot column required by metric '{key}' is missing: {column}"
            )

        values = pd.to_numeric(result[column], errors="coerce")
        direction = definition["direction"]
        if direction == "min":
            passed = values.notna() & values.ge(threshold)
        elif direction == "max":
            passed = values.notna() & values.le(threshold)
        else:
            passed = values.notna() & values.sub(threshold).abs().le(1e-12)

        if definition.get("financials_exempt"):
            passed = passed | sectors.eq("financials")
        if definition.get("debt_free_as_infinity"):
            passed = passed | icr_labels.eq("debt free")
        keep &= passed

    result = result.loc[keep].copy()
    if "composite_quality_score" in result.columns:
        result = result.sort_values(
            ["composite_quality_score", "company_id"],
            ascending=[False, True],
            na_position="last",
            kind="mergesort",
        )
    else:
        result = result.sort_values("company_id", kind="mergesort")
    return result.reset_index(drop=True)


def run_screener(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    filters: Mapping[str, Any] | None = None,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> pd.DataFrame:
    """Load the current 92-company universe and apply custom thresholds."""

    config = load_screener_config(config_path)
    requested = config["active_filters"] if filters is None else filters
    snapshot = load_latest_company_metrics(database_path)
    return apply_filters(snapshot, requested, config["metrics"])


def _parse_cli_filters(items: Sequence[str]) -> dict[str, float]:
    filters: dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise ScreenerConfigError(
                f"CLI filter must use metric=value syntax: {item!r}"
            )
        key, value = item.split("=", 1)
        try:
            filters[key.strip()] = float(value.strip())
        except ValueError as exc:
            raise ScreenerConfigError(f"Invalid numeric threshold: {item!r}") from exc
    return filters


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="METRIC=VALUE",
        help="Override YAML active_filters; may be repeated",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    cli_filters = _parse_cli_filters(args.filter)
    results = run_screener(
        args.database,
        filters=cli_filters if args.filter else None,
        config_path=args.config,
    )
    config = load_screener_config(args.config)
    output = args.output or Path(
        config["output"].get("csv_path", "output/day15_custom_screener.csv")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    print(
        json.dumps(
            {
                "database": str(args.database),
                "companies_returned": int(len(results)),
                "filters": cli_filters if args.filter else config["active_filters"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
