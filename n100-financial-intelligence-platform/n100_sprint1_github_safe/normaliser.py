"""Shared normalisation functions for N100 source files.

The functions in this module are deliberately deterministic: the same raw
value always produces the same normalised value. Source-specific deduplication
is handled by the loader after the official reporting-period rules are known.
"""

from __future__ import annotations

import math
import re
import calendar
from datetime import date, datetime
from typing import Any


_EXCHANGE_PREFIX = re.compile(r"^(?:NSE|BSE)\s*:\s*", re.IGNORECASE)
_NORMALISED_PERIOD = re.compile(r"^((?:19|20)\d{2})-(0[1-9]|1[0-2])$")
_FY_PERIOD = re.compile(r"(?i)^FY\s*[-']?\s*(\d{2}|(?:19|20)\d{2})$")
_MONTH_YEAR = re.compile(
    r"(?i)^(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)[-\s']+(\d{2}|(?:19|20)\d{2})(?:\s+.*)?$"
)


def is_missing(value: Any) -> bool:
    """Return True for None, NaN and blank text values."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def normalize_ticker(value: Any) -> str | None:
    """Normalise an NSE/BSE company identifier without changing valid symbols.

    Hyphens and ampersands are preserved because they are legitimate characters
    in identifiers such as ``BAJAJ-AUTO`` and ``M&M``.
    """
    if is_missing(value):
        return "MISSING"
    ticker = str(value).strip().upper()
    ticker = _EXCHANGE_PREFIX.sub("", ticker)
    ticker = re.sub(r"\s+", "", ticker)
    return ticker or "MISSING"


def normalize_year(value: Any) -> str:
    """Convert supported reporting periods to the official ``YYYY-MM`` form.

    Integer years and ``FY`` labels assume an Indian March financial-year end,
    as required by the project specification. Unsupported values return the
    explicit ``PARSE_ERROR`` marker so the validator can reject and log them.
    """
    if is_missing(value):
        return "PARSE_ERROR"
    if isinstance(value, (datetime, date)):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, int):
        return f"{value:04d}-03" if 1900 <= value <= 2100 else "PARSE_ERROR"
    if isinstance(value, float):
        if value.is_integer():
            integer = int(value)
            return f"{integer:04d}-03" if 1900 <= integer <= 2100 else "PARSE_ERROR"
        return "PARSE_ERROR"

    text = str(value).strip()
    match = _NORMALISED_PERIOD.fullmatch(text)
    if match:
        return text

    match = _FY_PERIOD.fullmatch(text)
    if match:
        year = _expand_year(match.group(1))
        return f"{year:04d}-03" if year is not None else "PARSE_ERROR"

    if re.fullmatch(r"(?:19|20)\d{2}", text):
        return f"{int(text):04d}-03"

    match = _MONTH_YEAR.fullmatch(text)
    if match:
        month_token, year_token = match.groups()
        year = _expand_year(year_token)
        month = _month_number(month_token)
        if year is not None and month is not None:
            return f"{year:04d}-{month:02d}"

    return "PARSE_ERROR"


def _expand_year(token: str) -> int | None:
    year = int(token)
    if len(token) == 2:
        return 2000 + year if year <= 69 else 1900 + year
    return year if 1900 <= year <= 2100 else None


def _month_number(token: str) -> int | None:
    normalized = token[:3].title()
    month_lookup = {calendar.month_abbr[i]: i for i in range(1, 13)}
    return month_lookup.get(normalized)
