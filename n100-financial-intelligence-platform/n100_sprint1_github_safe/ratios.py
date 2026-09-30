"""Profitability ratio primitives for the N100 financial-ratio engine.

The functions in this module are intentionally small and deterministic.  They
do not round results because rounding belongs at the reporting boundary, not in
the calculation engine.  Invalid or unavailable denominators return ``None``
instead of raising an exception or fabricating a value.
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OPM_TOLERANCE_PCT_POINTS = 1.0
DEFAULT_HIGH_LEVERAGE_THRESHOLD = 5.0
DEFAULT_ICR_WARNING_THRESHOLD = 1.5
FINANCIALS_SECTOR = "financials"
FINANCIAL_ENTITY_BANK = "BANK"
FINANCIAL_ENTITY_NBFC = "NBFC"
FINANCIAL_ENTITY_INSURANCE = "INSURANCE"
FINANCIAL_ENTITY_OTHER = "OTHER_FINANCIAL"
NON_FINANCIAL_ENTITY = "NON_FINANCIAL"


def _finite_number(value: Any) -> float | None:
    """Convert a finite numeric value to ``float``; otherwise return ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(
    numerator: Any, denominator: Any, *, multiplier: float = 1.0
) -> float | None:
    """Divide two finite values without propagating invalid arithmetic.

    ``None`` is returned when either operand is unavailable, the denominator is
    zero, or any operand is not finite.  Negative denominators remain valid at
    this generic layer; ratio-specific functions apply their own business rules.
    """
    valid_numerator = _finite_number(numerator)
    valid_denominator = _finite_number(denominator)
    valid_multiplier = _finite_number(multiplier)
    if (
        valid_numerator is None
        or valid_denominator is None
        or valid_multiplier is None
        or valid_denominator == 0
    ):
        return None
    return (valid_numerator / valid_denominator) * valid_multiplier


def net_profit_margin(net_profit: Any, sales: Any) -> float | None:
    """Return net profit divided by sales as a percentage."""
    return safe_divide(net_profit, sales, multiplier=100.0)


def operating_profit_margin(operating_profit: Any, sales: Any) -> float | None:
    """Return operating profit divided by sales as a percentage."""
    return safe_divide(operating_profit, sales, multiplier=100.0)


def return_on_equity(
    net_profit: Any, equity_capital: Any, reserves: Any
) -> float | None:
    """Return ROE, or ``None`` when equity plus reserves is non-positive."""
    equity = _finite_number(equity_capital)
    retained_reserves = _finite_number(reserves)
    if equity is None or retained_reserves is None:
        return None
    denominator = equity + retained_reserves
    if denominator <= 0:
        return None
    return safe_divide(net_profit, denominator, multiplier=100.0)


def return_on_capital_employed(
    ebit: Any,
    equity_capital: Any,
    reserves: Any,
    borrowings: Any,
) -> float | None:
    """Return ROCE using equity, reserves and borrowings as capital employed.

    The arithmetic is identical for every company.  Financial-sector companies
    are identified separately so later benchmarking can use sector-relative
    thresholds rather than applying a misleading absolute threshold.
    """
    equity = _finite_number(equity_capital)
    retained_reserves = _finite_number(reserves)
    debt = _finite_number(borrowings)
    if equity is None or retained_reserves is None or debt is None:
        return None
    capital_employed = equity + retained_reserves + debt
    if capital_employed <= 0:
        return None
    return safe_divide(ebit, capital_employed, multiplier=100.0)


def return_on_assets(net_profit: Any, total_assets: Any) -> float | None:
    """Return ROA, or ``None`` when total assets are zero or unavailable."""
    assets = _finite_number(total_assets)
    if assets is None or assets == 0:
        return None
    return safe_divide(net_profit, assets, multiplier=100.0)


def is_financial_sector(broad_sector: Any) -> bool:
    """Identify the official ``Financials`` broad-sector classification."""
    if broad_sector is None:
        return False
    return str(broad_sector).strip().casefold() == FINANCIALS_SECTOR


def classify_financial_entity(broad_sector: Any, sub_sector: Any) -> str:
    """Classify the supplied sector row for Financials-specific treatment."""
    if not is_financial_sector(broad_sector):
        return NON_FINANCIAL_ENTITY
    label = "" if sub_sector is None else str(sub_sector).strip().casefold()
    if "bank" in label:
        return FINANCIAL_ENTITY_BANK
    if "insurance" in label:
        return FINANCIAL_ENTITY_INSURANCE
    if label in {
        "consumer finance",
        "speciality finance",
        "specialty finance",
        "diversified financials",
    }:
        return FINANCIAL_ENTITY_NBFC
    return FINANCIAL_ENTITY_OTHER


def uses_financial_leverage_treatment(
    broad_sector: Any, sub_sector: Any
) -> bool:
    """Return whether the ordinary D/E warning must be suppressed."""
    return classify_financial_entity(broad_sector, sub_sector) in {
        FINANCIAL_ENTITY_BANK,
        FINANCIAL_ENTITY_NBFC,
        FINANCIAL_ENTITY_INSURANCE,
    }


def debt_to_equity(
    borrowings: Any, equity_capital: Any, reserves: Any
) -> float | None:
    """Return borrowings divided by equity plus reserves.

    Debt-free companies explicitly return ``0.0``. When debt exists, a missing
    or non-positive equity base returns ``None`` because the ratio would not be
    economically meaningful.
    """
    debt = _finite_number(borrowings)
    if debt is None:
        return None
    if debt == 0:
        return 0.0

    equity = _finite_number(equity_capital)
    retained_reserves = _finite_number(reserves)
    if equity is None or retained_reserves is None:
        return None
    denominator = equity + retained_reserves
    if denominator <= 0:
        return None
    return safe_divide(debt, denominator)


def high_leverage_flag(
    debt_equity_ratio: Any,
    broad_sector: Any,
    *,
    sub_sector: Any = None,
    threshold: float = DEFAULT_HIGH_LEVERAGE_THRESHOLD,
) -> bool:
    """Flag D/E above the threshold, with the financial-sector carve-out.

    Banks, NBFCs and insurers do not use the ordinary industrial-company D/E
    threshold.  When ``sub_sector`` is unavailable, the broader historical
    Financials suppression is retained for backward compatibility.
    """
    valid_threshold = _finite_number(threshold)
    if valid_threshold is None or valid_threshold < 0:
        raise ValueError("High-leverage threshold must be finite and non-negative")
    ratio = _finite_number(debt_equity_ratio)
    if sub_sector is None:
        exempt = is_financial_sector(broad_sector)
    else:
        exempt = uses_financial_leverage_treatment(broad_sector, sub_sector)
    return bool(ratio is not None and ratio > valid_threshold and not exempt)


def interest_coverage_ratio(
    operating_profit: Any, other_income: Any, interest: Any
) -> float | None:
    """Return (operating profit + other income) divided by interest.

    Zero interest returns ``None`` as required by the Sprint 2 specification.
    Missing or non-finite inputs also return ``None``.
    """
    operating = _finite_number(operating_profit)
    other = _finite_number(other_income)
    interest_expense = _finite_number(interest)
    if operating is None or other is None or interest_expense is None:
        return None
    if interest_expense == 0:
        return None
    return safe_divide(operating + other, interest_expense)


def interest_coverage_label(interest: Any, borrowings: Any = None) -> str | None:
    """Return ``Debt Free`` for a zero-interest, zero-borrowings company.

    When borrowings are unavailable, zero interest is accepted as the project's
    debt-free proxy. Supplying a non-zero borrowing value prevents an incorrect
    debt-free label while retaining the required ``None`` ICR result.
    """
    interest_expense = _finite_number(interest)
    debt = _finite_number(borrowings)
    if interest_expense != 0:
        return None
    if borrowings is None or debt == 0:
        return "Debt Free"
    return None


def interest_coverage_warning(
    interest_coverage: Any,
    *,
    threshold: float = DEFAULT_ICR_WARNING_THRESHOLD,
) -> bool:
    """Flag an available ICR that is strictly below the warning threshold."""
    valid_threshold = _finite_number(threshold)
    if valid_threshold is None or valid_threshold < 0:
        raise ValueError("ICR warning threshold must be finite and non-negative")
    ratio = _finite_number(interest_coverage)
    return bool(ratio is not None and ratio < valid_threshold)


@dataclass(frozen=True)
class InterestCoverageAssessment:
    """Combined ICR value, display label and risk flag."""

    ratio: float | None
    label: str | None
    warning_flag: bool


def assess_interest_coverage(
    operating_profit: Any,
    other_income: Any,
    interest: Any,
    *,
    borrowings: Any = None,
    warning_threshold: float = DEFAULT_ICR_WARNING_THRESHOLD,
) -> InterestCoverageAssessment:
    """Calculate all Interest Coverage outputs in one consistent operation."""
    ratio = interest_coverage_ratio(operating_profit, other_income, interest)
    return InterestCoverageAssessment(
        ratio=ratio,
        label=interest_coverage_label(interest, borrowings),
        warning_flag=interest_coverage_warning(
            ratio, threshold=warning_threshold
        ),
    )


def net_debt(borrowings: Any, investments: Any) -> float | None:
    """Return borrowings minus investments used as the liquid-asset proxy."""
    debt = _finite_number(borrowings)
    liquid_assets = _finite_number(investments)
    if debt is None or liquid_assets is None:
        return None
    return debt - liquid_assets


def asset_turnover(sales: Any, total_assets: Any) -> float | None:
    """Return sales divided by total assets for a positive asset base."""
    assets = _finite_number(total_assets)
    if assets is None or assets <= 0:
        return None
    return safe_divide(sales, assets)


@dataclass(frozen=True)
class OPMCrossCheck:
    """Auditable comparison between calculated and supplied OPM percentages."""

    company_id: str | None
    year: str | None
    calculated_opm_pct: float | None
    source_opm_pct: float | None
    difference_pct_points: float | None
    exceeds_tolerance: bool
    tolerance_pct_points: float

    def as_dict(self) -> dict[str, Any]:
        """Return a CSV-ready representation of the comparison."""
        return asdict(self)


def cross_check_operating_profit_margin(
    operating_profit: Any,
    sales: Any,
    source_opm_percentage: Any,
    *,
    company_id: str | None = None,
    year: str | None = None,
    tolerance_pct_points: float = DEFAULT_OPM_TOLERANCE_PCT_POINTS,
) -> OPMCrossCheck:
    """Compare calculated OPM with the supplied value in percentage points.

    A difference is flagged only when it is strictly greater than the supplied
    tolerance, matching the project rule "difference > 1%".
    """
    tolerance = _finite_number(tolerance_pct_points)
    if tolerance is None or tolerance < 0:
        raise ValueError("OPM tolerance must be a finite non-negative number")

    calculated = operating_profit_margin(operating_profit, sales)
    source = _finite_number(source_opm_percentage)
    difference = (
        abs(calculated - source)
        if calculated is not None and source is not None
        else None
    )
    return OPMCrossCheck(
        company_id=company_id,
        year=year,
        calculated_opm_pct=calculated,
        source_opm_pct=source,
        difference_pct_points=difference,
        exceeds_tolerance=difference is not None and difference > tolerance,
        tolerance_pct_points=tolerance,
    )


def write_opm_mismatch_log(
    checks: Iterable[OPMCrossCheck], output_path: str | Path
) -> Path:
    """Write only OPM comparisons that exceed the configured tolerance."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mismatches = [check.as_dict() for check in checks if check.exceeds_tolerance]
    fieldnames = [
        "company_id",
        "year",
        "calculated_opm_pct",
        "source_opm_pct",
        "difference_pct_points",
        "exceeds_tolerance",
        "tolerance_pct_points",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mismatches)
    return path
