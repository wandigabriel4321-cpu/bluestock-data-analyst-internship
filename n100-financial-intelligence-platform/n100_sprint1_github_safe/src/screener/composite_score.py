"""Sprint 3 Day 17 composite score.

This module intentionally keeps the Sprint 2 ``composite_quality_score`` as a
legacy audit field.  The Sprint 3 score uses the new ten-component formula,
P10/P90 winsorisation and 0--100 min-max scaling.  Missing components are not
turned into zero: they receive the neutral normalised value 50 and score
coverage is reported beside every result.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from src.analytics.cagr import CAGRResult, calculate_window_cagr
from src.screener.engine import DEFAULT_DATABASE_PATH, load_latest_company_metrics


@dataclass(frozen=True)
class ScoreComponent:
    source: str
    weight: float
    inverse: bool = False
    binary_positive: bool = False


COMPONENTS: dict[str, ScoreComponent] = {
    "roe": ScoreComponent("return_on_equity_pct", 0.15),
    "roce": ScoreComponent("return_on_capital_employed_pct", 0.10),
    "net_profit_margin": ScoreComponent("net_profit_margin_pct", 0.10),
    "fcf_cagr_5yr": ScoreComponent("fcf_cagr_5yr", 0.15),
    "cfo_pat_ratio": ScoreComponent("cfo_pat_ratio_5yr", 0.10),
    "fcf_positive": ScoreComponent("free_cash_flow_cr", 0.05, binary_positive=True),
    "revenue_cagr": ScoreComponent("revenue_cagr_5yr", 0.10),
    "pat_cagr": ScoreComponent("pat_cagr_5yr", 0.10),
    "debt_to_equity": ScoreComponent("debt_to_equity", 0.10, inverse=True),
    "interest_coverage": ScoreComponent("effective_interest_coverage", 0.05),
}


def validate_component_weights(
    components: Mapping[str, ScoreComponent] = COMPONENTS,
) -> None:
    """Reject an incomplete or mathematically invalid scoring formula."""

    if len(components) != 10:
        raise ValueError("Sprint 3 composite score requires exactly 10 components")
    if any(not math.isfinite(item.weight) or item.weight <= 0 for item in components.values()):
        raise ValueError("Every component weight must be positive and finite")
    if not math.isclose(sum(item.weight for item in components.values()), 1.0):
        raise ValueError("Sprint 3 composite weights must sum to 1.0")


def winsorized_minmax(
    values: pd.Series,
    *,
    inverse: bool = False,
    lower_quantile: float = 0.10,
    upper_quantile: float = 0.90,
) -> tuple[pd.Series, float | None, float | None]:
    """Winsorise finite values at P10/P90 and scale them to 0--100.

    Missing and non-finite values remain missing.  A constant distribution is
    assigned the neutral score 50 because no observation can be ranked above
    another.  ``inverse=True`` makes the lowest value score highest.
    """

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    numeric = numeric.where(np.isfinite(numeric), np.nan)
    available = numeric.dropna()
    if available.empty:
        return pd.Series(np.nan, index=values.index, dtype=float), None, None
    lower = float(available.quantile(lower_quantile, interpolation="linear"))
    upper = float(available.quantile(upper_quantile, interpolation="linear"))
    if math.isclose(lower, upper, rel_tol=0.0, abs_tol=1e-12):
        score = pd.Series(np.nan, index=values.index, dtype=float)
        score.loc[numeric.notna()] = 50.0
    else:
        score = (numeric.clip(lower=lower, upper=upper) - lower) / (upper - lower) * 100.0
    if inverse:
        score = score.where(score.isna(), 100.0 - score)
    return score, lower, upper


def calculate_fcf_cagr_5yr(
    records: Iterable[Mapping[str, Any]], *, end_year: str
) -> CAGRResult:
    """Calculate FCF CAGR across the exact five-year reporting window."""

    return calculate_window_cagr(
        records,
        "free_cash_flow_cr",
        5,
        end_year=end_year,
    )


def load_fcf_history(database_path: str | Path = DEFAULT_DATABASE_PATH) -> pd.DataFrame:
    """Load the annual FCF history used by the exact-window calculation."""

    with sqlite3.connect(database_path) as connection:
        return pd.read_sql_query(
            """
            SELECT company_id, year, free_cash_flow_cr
            FROM financial_ratios
            WHERE free_cash_flow_cr IS NOT NULL
            ORDER BY company_id, year
            """,
            connection,
        )


def attach_fcf_cagr_5yr(
    snapshot: pd.DataFrame, fcf_history: pd.DataFrame
) -> pd.DataFrame:
    """Attach value, flag and exact endpoints to the current company snapshot."""

    required_snapshot = {"company_id", "financial_year"}
    required_history = {"company_id", "year", "free_cash_flow_cr"}
    if not required_snapshot.issubset(snapshot.columns):
        raise ValueError("Snapshot is missing company_id or financial_year")
    if not required_history.issubset(fcf_history.columns):
        raise ValueError("FCF history is missing required columns")

    grouped = {
        str(company_id): group.to_dict("records")
        for company_id, group in fcf_history.groupby("company_id", sort=False)
    }
    rows: list[dict[str, Any]] = []
    for _, source in snapshot.iterrows():
        company_id = str(source["company_id"])
        end_year = str(source["financial_year"])
        result = calculate_fcf_cagr_5yr(grouped.get(company_id, []), end_year=end_year)
        rows.append(
            {
                "company_id": company_id,
                "fcf_cagr_5yr": result.value,
                "fcf_cagr_5yr_flag": result.flag,
                "fcf_cagr_start_year": result.start_year,
                "fcf_cagr_end_year": result.end_year,
            }
        )
    return snapshot.merge(pd.DataFrame(rows), on="company_id", how="left", validate="one_to_one")


def _effective_interest_coverage(frame: pd.DataFrame) -> pd.Series:
    values = pd.to_numeric(frame["interest_coverage"], errors="coerce").astype(float)
    finite = values[np.isfinite(values)]
    replacement = float(finite.max()) if not finite.empty else 1.0
    debt_free = frame["icr_label"].fillna("").astype(str).str.strip().str.casefold().eq("debt free")
    return values.mask(debt_free, replacement)


def _component_scores(
    frame: pd.DataFrame,
    *,
    scope: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    scored = pd.DataFrame(index=frame.index)
    bounds: list[dict[str, Any]] = []
    for name, definition in COMPONENTS.items():
        if definition.binary_positive:
            source = pd.to_numeric(frame[definition.source], errors="coerce")
            scored[name] = source.map(
                lambda value: np.nan if pd.isna(value) else (100.0 if value > 0 else 0.0)
            )
            lower = upper = None
        else:
            scored[name], lower, upper = winsorized_minmax(
                frame[definition.source], inverse=definition.inverse
            )
        bounds.append(
            {
                "scope": scope,
                "component": name,
                "source_column": definition.source,
                "weight_pct": definition.weight * 100,
                "inverse": definition.inverse,
                "p10": lower,
                "p90": upper,
                "available_values": int(scored[name].notna().sum()),
            }
        )
    return scored, bounds


def _weighted_available_score(scores: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    weights = pd.Series({key: value.weight for key, value in COMPONENTS.items()})
    available_weights = scores.notna().mul(weights, axis=1).sum(axis=1)
    # A neutral 50 preserves the official weights without rewarding missing
    # data through weight redistribution or penalising it as fabricated zero.
    result = scores.fillna(50.0).mul(weights, axis=1).sum(axis=1)
    result = result.where(available_weights.gt(0))
    return result, available_weights * 100.0


def compute_composite_scores(
    snapshot: pd.DataFrame,
    fcf_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate global and broad-sector-relative Sprint 3 scores."""

    validate_component_weights()
    frame = attach_fcf_cagr_5yr(snapshot.copy(), fcf_history)
    if "composite_quality_score" not in frame.columns:
        raise ValueError("Legacy Sprint 2 composite score is missing")
    frame = frame.rename(
        columns={"composite_quality_score": "legacy_composite_quality_score"}
    )
    frame["effective_interest_coverage"] = _effective_interest_coverage(frame)

    global_scores, bounds = _component_scores(frame, scope="GLOBAL")
    for column in global_scores:
        frame[f"global_{column}_score"] = global_scores[column]
    frame["sprint3_composite_score"], frame["global_score_coverage_pct"] = (
        _weighted_available_score(global_scores)
    )

    sector_score_parts: list[pd.DataFrame] = []
    for sector, group in frame.groupby("broad_sector", dropna=False, sort=True):
        group_scores, group_bounds = _component_scores(
            group, scope=f"SECTOR:{sector if pd.notna(sector) else 'MISSING'}"
        )
        sector_score_parts.append(group_scores)
        bounds.extend(group_bounds)
    sector_scores = pd.concat(sector_score_parts).sort_index()
    for column in sector_scores:
        frame[f"sector_{column}_score"] = sector_scores[column]
    (
        frame["sector_relative_composite_score"],
        frame["sector_score_coverage_pct"],
    ) = _weighted_available_score(sector_scores)

    frame["sprint3_composite_score"] = frame["sprint3_composite_score"].round(6)
    frame["sector_relative_composite_score"] = frame[
        "sector_relative_composite_score"
    ].round(6)
    frame["global_score_coverage_pct"] = frame["global_score_coverage_pct"].round(2)
    frame["sector_score_coverage_pct"] = frame["sector_score_coverage_pct"].round(2)
    return frame, pd.DataFrame(bounds)


def build_scored_snapshot(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load current company data and return scores plus normalisation bounds."""

    snapshot = load_latest_company_metrics(database_path)
    history = load_fcf_history(database_path)
    return compute_composite_scores(snapshot, history)
