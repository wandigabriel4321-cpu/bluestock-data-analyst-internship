"""Excel loader and source normalisation for the N100 project.

The loader keeps source discovery, schema validation and value conversion in
one deterministic place.  It never edits an input workbook.  Read failures
and cell-level conversion failures are written to ``read_errors.csv`` so that
the original value remains auditable.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.etl.normaliser import is_missing, normalize_ticker, normalize_year


LOGGER = logging.getLogger(__name__)


class LoaderError(Exception):
    """Base class for controlled source-loading failures."""


class UnknownSourceError(LoaderError):
    """Raised when a filename has no registered destination table."""


class InvalidFileFormatError(LoaderError):
    """Raised when a source is not an XLSX workbook."""


class EmptySourceFileError(LoaderError):
    """Raised when a source file or its required worksheet is empty."""


class MissingWorksheetError(LoaderError):
    """Raised when the configured worksheet does not exist."""


class SchemaValidationError(LoaderError):
    """Raised when required, unexpected or duplicate columns are found."""


@dataclass(frozen=True)
class DatasetSpec:
    source_name: str
    table_name: str
    sheet_name: str
    header_row: int
    sprint: int
    required_columns: tuple[str, ...]
    ticker_columns: tuple[str, ...] = ()
    year_columns: tuple[str, ...] = ()
    date_columns: tuple[str, ...] = ()
    numeric_columns: tuple[str, ...] = ()
    percentage_columns: tuple[str, ...] = ()


@dataclass
class LoadResult:
    source_file: str
    table_name: str
    dataframe: pd.DataFrame
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.dataframe)


def _spec(
    source_name: str,
    table_name: str,
    sheet_name: str,
    header_row: int,
    sprint: int,
    columns: Iterable[str],
    *,
    tickers: Iterable[str] = (),
    years: Iterable[str] = (),
    dates: Iterable[str] = (),
    numeric: Iterable[str] = (),
    percentages: Iterable[str] = (),
) -> DatasetSpec:
    return DatasetSpec(
        source_name=source_name,
        table_name=table_name,
        sheet_name=sheet_name,
        header_row=header_row,
        sprint=sprint,
        required_columns=tuple(columns),
        ticker_columns=tuple(tickers),
        year_columns=tuple(years),
        date_columns=tuple(dates),
        numeric_columns=tuple(numeric),
        percentage_columns=tuple(percentages),
    )


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    _spec(
        "companies.xlsx", "companies", "Companies", 1, 1,
        ("id", "company_logo", "company_name", "chart_link", "about_company",
         "website", "nse_profile", "bse_profile", "face_value", "book_value",
         "roce_percentage", "roe_percentage"),
        tickers=("id",), numeric=("face_value", "book_value"),
        percentages=("roce_percentage", "roe_percentage"),
    ),
    _spec(
        "profitandloss.xlsx", "profitandloss", "Profit & Loss", 1, 1,
        ("id", "company_id", "year", "sales", "expenses", "operating_profit",
         "opm_percentage", "other_income", "interest", "depreciation",
         "profit_before_tax", "tax_percentage", "net_profit", "eps",
         "dividend_payout"),
        tickers=("company_id",), years=("year",), numeric=("id", "sales",
        "expenses", "operating_profit", "other_income", "interest",
        "depreciation", "profit_before_tax", "net_profit", "eps"),
        percentages=("opm_percentage", "tax_percentage", "dividend_payout"),
    ),
    _spec(
        "balancesheet.xlsx", "balancesheet", "Balance Sheet", 1, 1,
        ("id", "company_id", "year", "equity_capital", "reserves", "borrowings",
         "other_liabilities", "total_liabilities", "fixed_assets", "cwip",
         "investments", "other_asset", "total_assets"),
        tickers=("company_id",), years=("year",),
        numeric=("id", "equity_capital", "reserves", "borrowings",
        "other_liabilities", "total_liabilities", "fixed_assets", "cwip",
        "investments", "other_asset", "total_assets"),
    ),
    _spec(
        "cashflow.xlsx", "cashflow", "Cash Flow", 1, 1,
        ("id", "company_id", "year", "operating_activity", "investing_activity",
         "financing_activity", "net_cash_flow"),
        tickers=("company_id",), years=("year",), numeric=("id",
        "operating_activity", "investing_activity", "financing_activity",
        "net_cash_flow"),
    ),
    _spec(
        "analysis.xlsx", "analysis", "Analysis", 1, 1,
        ("id", "company_id", "compounded_sales_growth",
         "compounded_profit_growth", "stock_price_cagr", "roe"),
        tickers=("company_id",), numeric=("id",),
    ),
    _spec(
        "documents.xlsx", "documents", "Documents", 1, 1,
        ("id", "company_id", "year", "annual_report"),
        tickers=("company_id",), years=("year",), numeric=("id",),
    ),
    _spec(
        "prosandcons.xlsx", "prosandcons", "Pros & Cons", 1, 1,
        ("id", "company_id", "pros", "cons"),
        tickers=("company_id",), numeric=("id",),
    ),
    _spec(
        "sectors.xlsx", "sectors", "Sheet1", 0, 1,
        ("id", "company_id", "broad_sector", "sub_sector", "index_weight_pct",
         "market_cap_category"),
        tickers=("company_id",), numeric=("id",), percentages=("index_weight_pct",),
    ),
    _spec(
        "market_cap.xlsx", "market_cap", "Sheet1", 0, 1,
        ("id", "company_id", "year", "market_cap_crore",
         "enterprise_value_crore", "pe_ratio", "pb_ratio", "ev_ebitda",
         "dividend_yield_pct"),
        tickers=("company_id",), years=("year",), numeric=("id",
        "market_cap_crore", "enterprise_value_crore", "pe_ratio", "pb_ratio",
        "ev_ebitda"), percentages=("dividend_yield_pct",),
    ),
    _spec(
        "stock_prices.xlsx", "stock_prices", "Sheet1", 0, 1,
        ("id", "company_id", "date", "open_price", "high_price", "low_price",
         "close_price", "volume", "adjusted_close"),
        tickers=("company_id",), dates=("date",), numeric=("id", "open_price",
        "high_price", "low_price", "close_price", "volume", "adjusted_close"),
    ),
    _spec(
        "financial_ratios.xlsx", "financial_ratios", "Sheet1", 0, 2,
        ("id", "company_id", "year", "net_profit_margin_pct",
         "operating_profit_margin_pct", "return_on_equity_pct", "debt_to_equity",
         "interest_coverage", "asset_turnover", "free_cash_flow_cr", "capex_cr",
         "earnings_per_share", "book_value_per_share",
         "dividend_payout_ratio_pct", "total_debt_cr", "cash_from_operations_cr"),
        tickers=("company_id",), years=("year",), numeric=("id", "debt_to_equity",
        "interest_coverage", "asset_turnover", "free_cash_flow_cr", "capex_cr",
        "earnings_per_share", "book_value_per_share", "total_debt_cr",
        "cash_from_operations_cr"), percentages=("net_profit_margin_pct",
        "operating_profit_margin_pct", "return_on_equity_pct",
        "dividend_payout_ratio_pct"),
    ),
    _spec(
        "peer_groups.xlsx", "peer_groups", "Sheet1", 0, 3,
        ("id", "peer_group_name", "company_id", "is_benchmark"),
        tickers=("company_id",), numeric=("id",),
    ),
)


_MISSING_MARKERS = {"", "NA", "N/A", "NAN", "NONE", "NULL", "NIL", "-", "—"}
_CURRENCY_TOKEN = re.compile(r"(?i)(?:₹|INR|RS\.?)")
_INVALID_COLUMN_CHARS = re.compile(r"[^a-z0-9]+")


def normalize_column_name(value: Any) -> str:
    """Convert a source heading to stable lowercase ``snake_case``."""
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("%", " percentage ").replace("&", " and ")
    text = _INVALID_COLUMN_CHARS.sub("_", text.lower()).strip("_")
    return re.sub(r"_+", "_", text)


def normalize_column_names(columns: Iterable[Any]) -> list[str]:
    """Normalise headings and reject names that collapse to duplicates."""
    normalized = [normalize_column_name(column) for column in columns]
    duplicates = sorted({name for name in normalized if normalized.count(name) > 1})
    if duplicates:
        raise SchemaValidationError(
            f"Duplicate columns after normalisation: {', '.join(duplicates)}"
        )
    return normalized


def normalize_missing_value(value: Any) -> Any:
    """Convert blank and conventional missing markers to ``pandas.NA``."""
    if is_missing(value):
        return pd.NA
    if isinstance(value, str):
        text = value.strip()
        return pd.NA if text.upper() in _MISSING_MARKERS else text
    return value


def normalize_missing_values(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.map(normalize_missing_value)


def parse_number(value: Any) -> float | Any:
    """Parse ordinary, comma-separated, currency and accounting numbers."""
    value = normalize_missing_value(value)
    if value is pd.NA or pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        raise ValueError("Boolean value is not a valid number")
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace("−", "-")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    text = _CURRENCY_TOKEN.sub("", text).replace(",", "").replace(" ", "")
    if text.endswith("%"):
        text = text[:-1]
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise ValueError(f"Invalid numeric value: {value!r}")
    number = float(text)
    return -number if negative else number


def parse_percentage(value: Any) -> float | Any:
    """Return percentages in percentage-point form (``12.5%`` -> ``12.5``)."""
    return parse_number(value)


def detect_dataset(path: str | Path) -> DatasetSpec:
    """Resolve prefixed upload filenames to their registered source table."""
    source = Path(path)
    if source.suffix.lower() != ".xlsx":
        raise InvalidFileFormatError(f"Expected an .xlsx workbook: {source.name}")
    lowered = source.name.lower()
    for spec in DATASET_SPECS:
        if lowered.endswith(spec.source_name.lower()):
            return spec
    raise UnknownSourceError(f"No destination table registered for {source.name}")


class ExcelLoader:
    """Read, validate and normalise registered N100 Excel workbooks."""

    ERROR_FIELDS = (
        "timestamp_utc", "source_file", "table_name", "sheet_name", "error_type",
        "message", "row_number", "column_name", "raw_value",
    )

    def __init__(self, output_dir: str | Path = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.error_path = self.output_dir / "read_errors.csv"

    def _error(
        self,
        path: Path,
        spec: DatasetSpec | None,
        error_type: str,
        message: str,
        *,
        row_number: int | None = None,
        column_name: str | None = None,
        raw_value: Any = None,
    ) -> dict[str, Any]:
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_file": path.name,
            "table_name": spec.table_name if spec else "",
            "sheet_name": spec.sheet_name if spec else "",
            "error_type": error_type,
            "message": message,
            "row_number": row_number if row_number is not None else "",
            "column_name": column_name or "",
            "raw_value": "" if raw_value is None else str(raw_value),
        }

    def _record_errors(self, errors: Iterable[dict[str, Any]]) -> None:
        rows = list(errors)
        if not rows:
            return
        new_file = not self.error_path.exists()
        with self.error_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.ERROR_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerows(rows)

    def _raise_and_record(
        self, path: Path, spec: DatasetSpec | None, exc: LoaderError
    ) -> None:
        self._record_errors([self._error(path, spec, type(exc).__name__, str(exc))])
        LOGGER.error("%s: %s", path.name, exc)
        raise exc

    def load_file(self, path: str | Path, *, strict_schema: bool = True) -> LoadResult:
        source = Path(path)
        spec: DatasetSpec | None = None
        try:
            spec = detect_dataset(source)
            if not source.exists() or source.stat().st_size == 0:
                raise EmptySourceFileError(f"Source file is missing or empty: {source.name}")

            with pd.ExcelFile(source, engine="openpyxl") as workbook:
                if spec.sheet_name not in workbook.sheet_names:
                    raise MissingWorksheetError(
                        f"Required sheet {spec.sheet_name!r} not found; available: "
                        f"{', '.join(workbook.sheet_names) or 'none'}"
                    )

                frame = pd.read_excel(
                    workbook, sheet_name=spec.sheet_name, header=spec.header_row,
                    dtype=object,
                )
            # Empty rows are irrelevant, but required columns must remain even
            # when every value in a column happens to be missing.
            frame = frame.dropna(axis=0, how="all")
            if frame.empty:
                raise EmptySourceFileError(
                    f"Required sheet {spec.sheet_name!r} contains no data rows"
                )

            frame.columns = normalize_column_names(frame.columns)
            actual = set(frame.columns)
            required = set(spec.required_columns)
            missing = sorted(required - actual)
            unexpected = sorted(actual - required)
            if missing or (strict_schema and unexpected):
                messages = []
                if missing:
                    messages.append(f"missing columns: {', '.join(missing)}")
                if unexpected:
                    messages.append(f"unexpected columns: {', '.join(unexpected)}")
                raise SchemaValidationError("; ".join(messages))
            if unexpected:
                frame = frame.drop(columns=unexpected)

            frame = frame.loc[:, list(spec.required_columns)]
            frame = normalize_missing_values(frame)
            errors: list[dict[str, Any]] = []

            for column in spec.ticker_columns:
                frame[column] = frame[column].map(normalize_ticker)

            for column in spec.year_columns:
                raw_values = frame[column].copy()
                frame[column] = raw_values.map(normalize_year)
                for index in frame.index[frame[column].eq("PARSE_ERROR")]:
                    errors.append(self._error(
                        source, spec, "YearParseError", "Unsupported reporting period",
                        row_number=int(index) + spec.header_row + 2,
                        column_name=column, raw_value=raw_values.loc[index],
                    ))

            for column in spec.date_columns:
                raw_values = frame[column].copy()
                converted = pd.to_datetime(raw_values, errors="coerce")
                frame[column] = converted.dt.strftime("%Y-%m-%d")
                frame.loc[converted.isna(), column] = pd.NA
                for index in frame.index[converted.isna() & raw_values.notna()]:
                    errors.append(self._error(
                        source, spec, "DateParseError", "Unsupported date value",
                        row_number=int(index) + spec.header_row + 2,
                        column_name=column, raw_value=raw_values.loc[index],
                    ))

            converters = {
                **{column: parse_number for column in spec.numeric_columns},
                **{column: parse_percentage for column in spec.percentage_columns},
            }
            for column, converter in converters.items():
                converted: list[Any] = []
                for index, raw_value in frame[column].items():
                    try:
                        converted.append(converter(raw_value))
                    except (TypeError, ValueError) as exc:
                        converted.append(pd.NA)
                        errors.append(self._error(
                            source, spec, "NumericParseError", str(exc),
                            row_number=int(index) + spec.header_row + 2,
                            column_name=column, raw_value=raw_value,
                        ))
                frame[column] = pd.Series(converted, index=frame.index, dtype="Float64")

            self._record_errors(errors)
            return LoadResult(source.name, spec.table_name, frame.reset_index(drop=True), errors)

        except LoaderError as exc:
            self._raise_and_record(source, spec, exc)
        except Exception as exc:  # corrupt ZIP/XML and other engine failures
            wrapped = LoaderError(f"Could not read {source.name}: {exc}")
            self._raise_and_record(source, spec, wrapped)
        raise AssertionError("unreachable")

    def load_directories(
        self,
        directories: Iterable[str | Path],
        *,
        maximum_sprint: int = 1,
        strict_schema: bool = True,
    ) -> tuple[list[LoadResult], list[dict[str, str]]]:
        """Load all registered workbooks without stopping at the first failure."""
        results: list[LoadResult] = []
        failures: list[dict[str, str]] = []
        paths = sorted(
            path for directory in directories for path in Path(directory).glob("*.xlsx")
        )
        for path in paths:
            try:
                spec = detect_dataset(path)
                if spec.sprint > maximum_sprint:
                    continue
                results.append(self.load_file(path, strict_schema=strict_schema))
            except LoaderError as exc:
                failures.append({"source_file": path.name, "error": str(exc)})
        return results, failures


def write_results(
    results: Iterable[LoadResult], processed_dir: str | Path, output_dir: str | Path
) -> Path:
    processed = Path(processed_dir)
    output = Path(output_dir)
    processed.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    audit_rows = []
    for result in results:
        destination = processed / f"{result.table_name}.csv"
        result.dataframe.to_csv(destination, index=False)
        audit_rows.append({
            "source_file": result.source_file,
            "table_name": result.table_name,
            "rows_loaded": result.row_count,
            "conversion_errors": len(result.errors),
            "output_file": destination.name,
        })
    audit_path = output / "load_audit.csv"
    pd.DataFrame(audit_rows).to_csv(audit_path, index=False)
    return audit_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and normalise N100 Excel sources")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--supporting-dir", type=Path, default=Path("data/supporting"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--maximum-sprint", type=int, default=1, choices=(1, 2, 3))
    parser.add_argument("--allow-extra-columns", action="store_true")
    args = parser.parse_args()

    loader = ExcelLoader(args.output_dir)
    results, failures = loader.load_directories(
        (args.input_dir, args.supporting_dir),
        maximum_sprint=args.maximum_sprint,
        strict_schema=not args.allow_extra_columns,
    )
    audit_path = write_results(results, args.processed_dir, args.output_dir)
    print(f"Loaded {len(results)} workbook(s); {len(failures)} failure(s)")
    print(f"Audit: {audit_path}")
    if failures:
        for failure in failures:
            print(f"ERROR {failure['source_file']}: {failure['error']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
