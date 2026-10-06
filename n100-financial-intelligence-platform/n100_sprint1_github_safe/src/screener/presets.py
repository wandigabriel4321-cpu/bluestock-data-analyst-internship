"""Sprint 3 Day 16 official preset screeners and validation evidence.

The six presets are read from ``config/screener_config.yaml``.  Thresholds use
the strict operators stated in the assignment; the engine never widens a
threshold merely to force a result count into the expected 5--50 interval.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from src.screener.engine import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATABASE_PATH,
    SNAPSHOT_COLUMNS,
    ScreenerConfigError,
    ScreenerDataError,
    _normalised_text,
    load_latest_company_metrics,
    load_screener_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
EXPECTED_PRESET_KEYS = (
    "quality_compounder",
    "value_pick",
    "growth_accelerator",
    "dividend_champion",
    "debt_free_blue_chip",
    "turnaround_watch",
)
VALID_OPERATORS = {"gt", "lt", "eq"}
VALID_SPECIAL_RULES = {"debt_to_equity_declining"}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def load_preset_definitions(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, dict[str, Any]]:
    """Load and validate exactly the six official Day 16 presets."""

    config = load_screener_config(config_path)
    raw_presets = config.get("presets")
    if not isinstance(raw_presets, dict):
        raise ScreenerConfigError("Configuration must define a 'presets' mapping")
    if set(raw_presets) != set(EXPECTED_PRESET_KEYS):
        missing = sorted(set(EXPECTED_PRESET_KEYS).difference(raw_presets))
        extra = sorted(set(raw_presets).difference(EXPECTED_PRESET_KEYS))
        raise ScreenerConfigError(
            f"Day 16 requires exactly six official presets; missing={missing}, extra={extra}"
        )

    validated: dict[str, dict[str, Any]] = {}
    for key in EXPECTED_PRESET_KEYS:
        definition = raw_presets[key]
        if not isinstance(definition, dict):
            raise ScreenerConfigError(f"Preset '{key}' must be a mapping")
        label = definition.get("label")
        rules = definition.get("rules")
        if not isinstance(label, str) or not label.strip():
            raise ScreenerConfigError(f"Preset '{key}' requires a label")
        if not isinstance(rules, list) or not rules:
            raise ScreenerConfigError(f"Preset '{key}' requires at least one rule")

        checked_rules: list[dict[str, Any]] = []
        for position, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                raise ScreenerConfigError(
                    f"Preset '{key}' rule {position} must be a mapping"
                )
            rule_label = rule.get("label")
            if not isinstance(rule_label, str) or not rule_label.strip():
                raise ScreenerConfigError(
                    f"Preset '{key}' rule {position} requires a label"
                )

            special = rule.get("special")
            if special is not None:
                if special not in VALID_SPECIAL_RULES:
                    raise ScreenerConfigError(
                        f"Preset '{key}' uses unsupported special rule '{special}'"
                    )
                checked_rules.append({"label": rule_label, "special": special})
                continue

            column = rule.get("column")
            operator = rule.get("operator")
            threshold = rule.get("threshold")
            if column not in SNAPSHOT_COLUMNS:
                raise ScreenerConfigError(
                    f"Preset '{key}' uses unsupported column '{column}'"
                )
            if operator not in VALID_OPERATORS:
                raise ScreenerConfigError(
                    f"Preset '{key}' uses unsupported operator '{operator}'"
                )
            if not _finite_number(threshold):
                raise ScreenerConfigError(
                    f"Preset '{key}' threshold must be a finite number"
                )
            checked_rules.append(
                {
                    "label": rule_label,
                    "column": column,
                    "operator": operator,
                    "threshold": float(threshold),
                    "financials_exempt": bool(
                        rule.get("financials_exempt", False)
                    ),
                }
            )

        validated[key] = {"label": label.strip(), "rules": checked_rules}
    return validated


def _rule_required_columns(rule: Mapping[str, Any]) -> tuple[str, ...]:
    if rule.get("special") == "debt_to_equity_declining":
        return ("debt_to_equity", "previous_debt_to_equity")
    return (str(rule["column"]),)


def evaluate_rule(frame: pd.DataFrame, rule: Mapping[str, Any]) -> pd.Series:
    """Return a boolean mask for one strict preset rule."""

    required = set(_rule_required_columns(rule))
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        raise ScreenerDataError(
            f"Preset snapshot is missing columns: {sorted(missing_columns)}"
        )

    if rule.get("special") == "debt_to_equity_declining":
        current = pd.to_numeric(frame["debt_to_equity"], errors="coerce")
        previous = pd.to_numeric(frame["previous_debt_to_equity"], errors="coerce")
        return current.notna() & previous.notna() & current.lt(previous)

    values = pd.to_numeric(frame[str(rule["column"])], errors="coerce")
    threshold = float(rule["threshold"])
    operator = rule["operator"]
    if operator == "gt":
        passed = values.notna() & values.gt(threshold)
    elif operator == "lt":
        passed = values.notna() & values.lt(threshold)
    else:
        passed = values.notna() & values.sub(threshold).abs().le(1e-12)

    if rule.get("financials_exempt"):
        if "broad_sector" not in frame.columns:
            raise ScreenerDataError("Preset snapshot is missing 'broad_sector'")
        passed = passed | _normalised_text(frame["broad_sector"]).eq("financials")
    return passed.astype(bool)


def apply_preset(
    frame: pd.DataFrame, definition: Mapping[str, Any]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Apply every rule simultaneously and return results plus diagnostics."""

    if "company_id" not in frame.columns:
        raise ScreenerDataError("Preset snapshot is missing 'company_id'")
    keep = pd.Series(True, index=frame.index, dtype=bool)
    diagnostics: list[dict[str, Any]] = []
    for sequence, rule in enumerate(definition["rules"], start=1):
        input_count = int(keep.sum())
        passed = evaluate_rule(frame, rule)
        keep &= passed
        output_count = int(keep.sum())
        missing_by_column = {
            column: int(pd.to_numeric(frame[column], errors="coerce").isna().sum())
            for column in _rule_required_columns(rule)
        }
        diagnostics.append(
            {
                "rule_sequence": sequence,
                "rule": rule["label"],
                "input_companies": input_count,
                "remaining_companies": output_count,
                "eliminated_companies": input_count - output_count,
                "missing_values_in_universe": json.dumps(
                    missing_by_column, sort_keys=True
                ),
            }
        )

    result = frame.loc[keep].copy()
    sort_columns = ["company_id"]
    ascending = [True]
    if "composite_quality_score" in result.columns:
        sort_columns = ["composite_quality_score", "company_id"]
        ascending = [False, True]
    return (
        result.sort_values(
            sort_columns,
            ascending=ascending,
            na_position="last",
            kind="mergesort",
        ).reset_index(drop=True),
        diagnostics,
    )


def _thresholds_text(definition: Mapping[str, Any]) -> str:
    return " | ".join(str(rule["label"]) for rule in definition["rules"])


def _missing_by_rule(
    frame: pd.DataFrame, definition: Mapping[str, Any]
) -> dict[str, int]:
    missing: dict[str, int] = {}
    for rule in definition["rules"]:
        columns = _rule_required_columns(rule)
        missing[rule["label"]] = int(
            frame[list(columns)].apply(pd.to_numeric, errors="coerce").isna().any(axis=1).sum()
        )
    return missing


def build_preset_outputs(
    snapshot: pd.DataFrame,
    definitions: Mapping[str, Mapping[str, Any]],
    *,
    expected_min: int = 5,
    expected_max: int = 50,
    expected_universe: int = 92,
    manual_sample_size: int = 3,
) -> dict[str, pd.DataFrame]:
    """Build result, validation, diagnostic and manual-check DataFrames."""

    if snapshot["company_id"].nunique() != len(snapshot):
        raise ScreenerDataError("Preset universe must contain one row per company")

    result_parts: list[pd.DataFrame] = []
    reports: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    manual_rows: list[dict[str, Any]] = []
    universe_count = int(snapshot["company_id"].nunique())

    for key in EXPECTED_PRESET_KEYS:
        definition = definitions[key]
        result, diagnostics = apply_preset(snapshot, definition)
        result = result.copy()
        result.insert(0, "preset_key", key)
        result.insert(1, "preset_name", definition["label"])
        result.insert(2, "preset_rank", range(1, len(result) + 1))
        result_parts.append(result)

        missing = _missing_by_rule(snapshot, definition)
        count = int(len(result))
        range_status = "PASS" if expected_min <= count <= expected_max else "FAIL"
        universe_status = "PASS" if universe_count == expected_universe else "FAIL"
        notes = "Result count is within the official interval."
        if range_status == "FAIL":
            notes = (
                "Official thresholds retained; see preset_diagnostics.csv for "
                "the limiting rule investigation."
            )
        reports.append(
            {
                "preset_key": key,
                "preset_name": definition["label"],
                "company_count": count,
                "expected_min": expected_min,
                "expected_max": expected_max,
                "thresholds_applied": _thresholds_text(definition),
                "missing_values_total": int(sum(missing.values())),
                "missing_values_by_rule": json.dumps(missing, sort_keys=True),
                "range_status": range_status,
                "universe_companies": universe_count,
                "universe_status": universe_status,
                "status": "PASS" if range_status == universe_status == "PASS" else "FAIL",
                "notes": notes,
            }
        )

        for diagnostic in diagnostics:
            diagnostic_rows.append(
                {
                    "preset_key": key,
                    "preset_name": definition["label"],
                    **diagnostic,
                }
            )

        for _, row in result.head(manual_sample_size).iterrows():
            evidence = []
            all_pass = True
            source_row = snapshot.loc[
                snapshot["company_id"].eq(row["company_id"])
            ].iloc[[0]]
            for rule in definition["rules"]:
                passed = bool(evaluate_rule(source_row, rule).iloc[0])
                all_pass &= passed
                evidence.append(f"{rule['label']}={'PASS' if passed else 'FAIL'}")
            manual_rows.append(
                {
                    "preset_key": key,
                    "preset_name": definition["label"],
                    "company_id": row["company_id"],
                    "company_name": row.get("company_name"),
                    "financial_year": row.get("financial_year"),
                    "manual_rule_evidence": " | ".join(evidence),
                    "manual_status": "PASS" if all_pass else "FAIL",
                }
            )

    results = pd.concat(result_parts, ignore_index=True) if result_parts else pd.DataFrame()
    return {
        "results": results,
        "validation": pd.DataFrame(reports),
        "diagnostics": pd.DataFrame(diagnostic_rows),
        "manual_checks": pd.DataFrame(manual_rows),
    }


def run_all_presets(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, pd.DataFrame]:
    """Execute all presets on the database and write the Day 16 evidence."""

    snapshot = load_latest_company_metrics(database_path)
    definitions = load_preset_definitions(config_path)
    outputs = build_preset_outputs(snapshot, definitions)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs["results"].to_csv(destination / "preset_screener_results.csv", index=False)
    outputs["validation"].to_csv(
        destination / "preset_validation_report.csv", index=False
    )
    outputs["diagnostics"].to_csv(destination / "preset_diagnostics.csv", index=False)
    outputs["manual_checks"].to_csv(
        destination / "preset_manual_checks.csv", index=False
    )
    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    outputs = run_all_presets(
        args.database, config_path=args.config, output_dir=args.output_dir
    )
    validation = outputs["validation"]
    print(
        json.dumps(
            {
                "universe_companies": int(validation["universe_companies"].iloc[0]),
                "preset_counts": dict(
                    zip(validation["preset_name"], validation["company_count"])
                ),
                "pass_count": int(validation["status"].eq("PASS").sum()),
                "fail_count": int(validation["status"].eq("FAIL").sum()),
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
