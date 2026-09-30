"""Data-quality validator implementing the official N100 DQ-01–DQ-16 rules."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import pandas as pd

try:  # Optional at runtime; requirements.txt still installs it for production.
    import requests
except ModuleNotFoundError:  # pragma: no cover - environment-dependent branch
    requests = None


YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")
TICKER_PATTERN = re.compile(r"^[A-Z0-9&-]{2,12}$")
ANNUAL_TABLES = ("profitandloss", "balancesheet", "cashflow")
CHILD_TABLES = (
    "profitandloss", "balancesheet", "cashflow", "analysis", "documents",
    "prosandcons", "sectors", "market_cap", "stock_prices",
)
YEAR_TABLES = ("profitandloss", "balancesheet", "cashflow", "documents", "market_cap")


RULE_NAMES = {
    "DQ-01": "Company PK Uniqueness",
    "DQ-02": "Annual PK Uniqueness",
    "DQ-03": "FK Integrity",
    "DQ-04": "Balance Sheet Balance",
    "DQ-05": "OPM Cross-Check",
    "DQ-06": "Positive Sales",
    "DQ-07": "Year Format",
    "DQ-08": "Ticker Format",
    "DQ-09": "Net Cash Check",
    "DQ-10": "Non-Negative Fixed Assets",
    "DQ-11": "Tax Rate Range",
    "DQ-12": "Dividend Payout Cap",
    "DQ-13": "URL Validity",
    "DQ-14": "EPS Sign Consistency",
    "DQ-15": "Strict Balance Counter",
    "DQ-16": "Coverage Check",
}


@dataclass
class ValidationFailure:
    rule_id: str
    severity: str
    table_name: str
    row_number: int | str = ""
    record_id: Any = ""
    company_id: Any = ""
    year: Any = ""
    column_name: str = ""
    raw_value: Any = ""
    observed_value: Any = ""
    expected: str = ""
    action: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": RULE_NAMES[self.rule_id],
            "severity": self.severity,
            "table_name": self.table_name,
            "row_number": self.row_number,
            "record_id": self.record_id,
            "company_id": self.company_id,
            "year": self.year,
            "column_name": self.column_name,
            "raw_value": self.raw_value,
            "observed_value": self.observed_value,
            "expected": self.expected,
            "action": self.action,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    tables: dict[str, pd.DataFrame]
    failures: list[ValidationFailure]
    audit: dict[str, Any] = field(default_factory=dict)
    load_blocked: bool = False

    def failures_for(self, rule_id: str) -> list[ValidationFailure]:
        return [failure for failure in self.failures if failure.rule_id == rule_id]


def default_url_checker(url: str, timeout: float = 5.0) -> int:
    if requests is not None:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return response.status_code
    request = Request(url, method="HEAD")
    with urlopen(request, timeout=timeout) as response:
        return response.status


class DataQualityValidator:
    """Validate and safely correct normalised Sprint 1 dataframes."""

    def __init__(
        self,
        tables: dict[str, pd.DataFrame],
        *,
        check_urls: bool = False,
        url_checker: Callable[[str], int] | None = None,
        loader_errors: pd.DataFrame | None = None,
    ) -> None:
        self.tables = {name: frame.copy(deep=True) for name, frame in tables.items()}
        self.check_urls = check_urls
        self.url_checker = url_checker or default_url_checker
        self.loader_errors = loader_errors if loader_errors is not None else pd.DataFrame()
        self.failures: list[ValidationFailure] = []
        self.audit: dict[str, Any] = {}
        self.load_blocked = False

    @staticmethod
    def _clean_scalar(value: Any) -> Any:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        return value

    def _raw_year_values(self, table_name: str) -> list[Any]:
        if self.loader_errors.empty or "error_type" not in self.loader_errors.columns:
            return []
        matches = self.loader_errors[
            self.loader_errors["error_type"].eq("YearParseError")
            & self.loader_errors["table_name"].eq(table_name)
        ]
        return matches.get("raw_value", pd.Series(dtype=object)).tolist()

    def validate(self) -> ValidationResult:
        # DQ-01 is the only rule whose required action is a hard load stop.
        self._dq01_company_pk()
        # Format checks precede composite-key and FK checks.
        self._dq08_ticker_format()
        self._dq07_year_format()
        self._dq02_annual_pk()
        self._dq03_fk_integrity()

        self._dq04_balance_sheet()
        self._dq05_opm()
        self._dq06_positive_sales()
        self._dq09_net_cash()
        self._dq10_fixed_assets()
        self._dq11_tax_rate()
        self._dq12_dividend_payout()
        self._dq13_urls()
        self._dq14_eps_sign()
        self._dq15_strict_balance()
        self._dq16_coverage()

        self.failures.sort(
            key=lambda failure: (
                int(failure.rule_id.split("-")[1]), failure.table_name,
                str(failure.row_number), str(failure.company_id),
            )
        )
        self.audit.update({
            "critical_failures": sum(f.severity == "CRITICAL" for f in self.failures),
            "warning_failures": sum(f.severity == "WARNING" for f in self.failures),
            "load_blocked": self.load_blocked,
        })
        return ValidationResult(self.tables, self.failures, self.audit, self.load_blocked)

    def _dq01_company_pk(self) -> None:
        frame = self.tables.get("companies")
        if frame is None or "id" not in frame:
            return
        duplicates = frame["id"].duplicated(keep=False)
        for index, row in frame.loc[duplicates].iterrows():
            self._add(
                "DQ-01", "CRITICAL", "companies", index, row=row,
                column_name="id", observed_value=row["id"], expected="unique ticker",
                action="Halt load and investigate duplicate ticker",
                message="Duplicate companies.id value",
            )
        if duplicates.any():
            self.load_blocked = True

    def _dq08_ticker_format(self) -> None:
        for table_name, frame in list(self.tables.items()):
            column = "id" if table_name == "companies" else "company_id"
            if column not in frame:
                continue
            invalid_indices = []
            for index, row in frame.iterrows():
                raw = row[column]
                ticker = "" if pd.isna(raw) else str(raw)
                valid = (
                    ticker != "MISSING"
                    and ticker == ticker.strip().upper()
                    and bool(TICKER_PATTERN.fullmatch(ticker))
                )
                if not valid:
                    invalid_indices.append(index)
                    self._add(
                        "DQ-08", "CRITICAL", table_name, index, row=row,
                        column_name=column, raw_value=raw, observed_value=ticker,
                        expected="uppercase trimmed ticker, length 2–12",
                        action="Reject row",
                        message="Invalid ticker format",
                    )
            if invalid_indices:
                self.tables[table_name] = frame.drop(index=invalid_indices).reset_index(drop=True)

    def _dq07_year_format(self) -> None:
        for table_name in YEAR_TABLES:
            frame = self.tables.get(table_name)
            if frame is None or "year" not in frame:
                continue
            raw_values = iter(self._raw_year_values(table_name))
            invalid_indices = []
            for index, row in frame.iterrows():
                year = "" if pd.isna(row["year"]) else str(row["year"])
                if not YEAR_PATTERN.fullmatch(year):
                    invalid_indices.append(index)
                    raw = next(raw_values, row["year"])
                    self._add(
                        "DQ-07", "CRITICAL", table_name, index, row=row,
                        column_name="year", raw_value=raw, observed_value=year,
                        expected="YYYY-MM", action="Reject row",
                        message="Unparseable reporting period",
                    )
            if invalid_indices:
                self.tables[table_name] = frame.drop(index=invalid_indices).reset_index(drop=True)

    def _dq02_annual_pk(self) -> None:
        for table_name in ANNUAL_TABLES:
            frame = self.tables.get(table_name)
            if frame is None or not {"company_id", "year"}.issubset(frame.columns):
                continue
            discarded = frame.duplicated(["company_id", "year"], keep="last")
            for index, row in frame.loc[discarded].iterrows():
                key = f"({row['company_id']}, {row['year']})"
                self._add(
                    "DQ-02", "CRITICAL", table_name, index, row=row,
                    column_name="company_id,year", observed_value=key,
                    expected="unique (company_id, year)",
                    action="Discard duplicate; keep last occurrence",
                    message="Duplicate annual composite key",
                )
            if discarded.any():
                self.tables[table_name] = frame.loc[~discarded].reset_index(drop=True)

    def _dq03_fk_integrity(self) -> None:
        companies = self.tables.get("companies")
        if companies is None or "id" not in companies:
            return
        master = set(companies["id"].dropna().astype(str))
        for table_name in CHILD_TABLES:
            frame = self.tables.get(table_name)
            if frame is None or "company_id" not in frame:
                continue
            orphan = ~frame["company_id"].isin(master)
            for index, row in frame.loc[orphan].iterrows():
                self._add(
                    "DQ-03", "CRITICAL", table_name, index, row=row,
                    column_name="company_id", observed_value=row["company_id"],
                    expected="company_id present in companies.id",
                    action="Reject orphan row", message="Foreign-key orphan",
                )
            if orphan.any():
                self.tables[table_name] = frame.loc[~orphan].reset_index(drop=True)

    def _dq04_balance_sheet(self) -> None:
        frame = self.tables.get("balancesheet")
        if frame is None:
            return
        for index, row in frame.iterrows():
            assets, liabilities = row.get("total_assets"), row.get("total_liabilities")
            if pd.isna(assets) or pd.isna(liabilities):
                continue
            ratio = float("inf") if float(assets) == 0 else abs(assets - liabilities) / abs(assets)
            if ratio >= 0.01:
                self._add(
                    "DQ-04", "WARNING", "balancesheet", index, row=row,
                    column_name="total_assets,total_liabilities",
                    observed_value=ratio, expected="relative difference < 0.01",
                    action="Flag for analyst review; retain row",
                    message="Balance sheet does not balance within 1% tolerance",
                )

    def _dq05_opm(self) -> None:
        frame = self.tables.get("profitandloss")
        if frame is None:
            return
        for index, row in frame.iterrows():
            sales, profit, source_opm = (
                row.get("sales"), row.get("operating_profit"), row.get("opm_percentage")
            )
            if any(pd.isna(value) for value in (sales, profit, source_opm)) or sales == 0:
                continue
            computed = profit / sales * 100
            difference = abs(source_opm - computed)
            if difference >= 1.0:
                self._add(
                    "DQ-05", "WARNING", "profitandloss", index, row=row,
                    column_name="opm_percentage", raw_value=source_opm,
                    observed_value=computed, expected="absolute difference < 1 percentage point",
                    action="Retain source; use computed OPM in Ratio Engine",
                    message=f"OPM differs by {difference:.4f} percentage points",
                )

    def _dq06_positive_sales(self) -> None:
        frame = self.tables.get("profitandloss")
        if frame is None:
            return
        bank_tickers: set[str] = set()
        sectors = self.tables.get("sectors")
        if sectors is not None and {"company_id", "sub_sector"}.issubset(sectors.columns):
            bank_mask = sectors["sub_sector"].fillna("").str.contains("bank", case=False)
            bank_tickers = set(sectors.loc[bank_mask, "company_id"].astype(str))
        invalid = frame["sales"].notna() & frame["sales"].le(0) & ~frame["company_id"].isin(bank_tickers)
        for index, row in frame.loc[invalid].iterrows():
            self._add(
                "DQ-06", "WARNING", "profitandloss", index, row=row,
                column_name="sales", observed_value=row["sales"], expected="sales > 0",
                action="Flag row and exclude from growth CAGR",
                message="Non-bank company has non-positive sales",
            )

    def _dq09_net_cash(self) -> None:
        frame = self.tables.get("cashflow")
        if frame is None:
            return
        for index, row in frame.iterrows():
            values = [row.get(name) for name in (
                "operating_activity", "investing_activity", "financing_activity", "net_cash_flow"
            )]
            if any(pd.isna(value) for value in values):
                continue
            computed = values[0] + values[1] + values[2]
            difference = abs(values[3] - computed)
            if difference > 10:
                self._add(
                    "DQ-09", "WARNING", "cashflow", index, row=row,
                    column_name="net_cash_flow", raw_value=values[3],
                    observed_value=difference, expected="difference <= 10 crore",
                    action="Replace net_cash_flow with component sum",
                    message=f"Net cash mismatch; computed value is {computed}",
                )
                frame.at[index, "net_cash_flow"] = computed
        self.tables["cashflow"] = frame

    def _dq10_fixed_assets(self) -> None:
        frame = self.tables.get("balancesheet")
        if frame is None:
            return
        invalid = frame["fixed_assets"].notna() & frame["fixed_assets"].lt(0)
        for index, row in frame.loc[invalid].iterrows():
            self._add(
                "DQ-10", "WARNING", "balancesheet", index, row=row,
                column_name="fixed_assets", raw_value=row["fixed_assets"],
                observed_value=row["fixed_assets"], expected="fixed_assets >= 0",
                action="Coerce fixed_assets to zero",
                message="Negative fixed-assets value",
            )
            frame.at[index, "fixed_assets"] = 0.0
        self.tables["balancesheet"] = frame

    def _dq11_tax_rate(self) -> None:
        frame = self.tables.get("profitandloss")
        if frame is None:
            return
        invalid = frame["tax_percentage"].notna() & ~frame["tax_percentage"].between(0, 60)
        for index, row in frame.loc[invalid].iterrows():
            self._add(
                "DQ-11", "WARNING", "profitandloss", index, row=row,
                column_name="tax_percentage", observed_value=row["tax_percentage"],
                expected="0 <= tax_percentage <= 60",
                action="Flag for analyst review; retain source value",
                message="Tax rate outside permitted review range",
            )

    def _dq12_dividend_payout(self) -> None:
        frame = self.tables.get("profitandloss")
        if frame is None:
            return
        invalid = frame["dividend_payout"].notna() & frame["dividend_payout"].gt(200)
        for index, row in frame.loc[invalid].iterrows():
            self._add(
                "DQ-12", "WARNING", "profitandloss", index, row=row,
                column_name="dividend_payout", observed_value=row["dividend_payout"],
                expected="dividend_payout <= 200",
                action="Flag for analyst confirmation; retain source value",
                message="Dividend payout exceeds 200%",
            )

    @staticmethod
    def _valid_http_url(value: Any) -> bool:
        if value is None or pd.isna(value):
            return False
        parsed = urlparse(str(value).strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _dq13_urls(self) -> None:
        frame = self.tables.get("documents")
        if frame is None or "annual_report" not in frame:
            return
        status_cache: dict[str, Any] = {}
        for index, row in frame.iterrows():
            url = row.get("annual_report")
            if not self._valid_http_url(url):
                self._add(
                    "DQ-13", "WARNING", "documents", index, row=row,
                    column_name="annual_report", raw_value=url,
                    observed_value="missing or malformed URL", expected="HTTP HEAD status 200",
                    action="Log inaccessible URL; retain row",
                    message="Annual-report URL is missing or malformed",
                )
                continue
            if not self.check_urls:
                continue
            url = str(url).strip()
            if url not in status_cache:
                try:
                    status_cache[url] = self.url_checker(url)
                except Exception as exc:  # network and injected-checker failures
                    status_cache[url] = f"CHECK_ERROR: {exc}"
            status = status_cache[url]
            if status != 200:
                self._add(
                    "DQ-13", "WARNING", "documents", index, row=row,
                    column_name="annual_report", raw_value=url,
                    observed_value=status, expected="HTTP HEAD status 200",
                    action="Log inaccessible URL; retain row",
                    message="Annual-report URL did not return HTTP 200",
                )

    def _dq14_eps_sign(self) -> None:
        frame = self.tables.get("profitandloss")
        if frame is None:
            return
        invalid = frame["net_profit"].gt(0) & (frame["eps"].isna() | frame["eps"].le(0))
        for index, row in frame.loc[invalid].iterrows():
            self._add(
                "DQ-14", "WARNING", "profitandloss", index, row=row,
                column_name="eps", observed_value=row["eps"],
                expected="eps > 0 when net_profit > 0",
                action="Flag mismatch; retain source value",
                message="Positive net profit with non-positive or missing EPS",
            )

    def _dq15_strict_balance(self) -> None:
        frame = self.tables.get("balancesheet")
        if frame is None:
            return
        comparable = frame["total_assets"].notna() & frame["total_liabilities"].notna()
        matches = comparable & frame["total_assets"].eq(frame["total_liabilities"])
        self.audit["DQ-15.comparable_rows"] = int(comparable.sum())
        self.audit["DQ-15.strict_balance_matches"] = int(matches.sum())
        self.audit["DQ-15.strict_balance_mismatches"] = int(comparable.sum() - matches.sum())

    def _dq16_coverage(self) -> None:
        companies = self.tables.get("companies")
        if companies is None:
            return
        company_ids = companies["id"].dropna().astype(str)
        for table_name in ANNUAL_TABLES:
            frame = self.tables.get(table_name)
            if frame is None:
                continue
            counts = frame.groupby("company_id")["year"].nunique()
            for company_id in company_ids:
                count = int(counts.get(company_id, 0))
                if count < 5:
                    action = "Flag limited history"
                    if count < 3:
                        action += "; exclude company from CAGR"
                    self._add(
                        "DQ-16", "WARNING", table_name,
                        company_id=company_id,
                        observed_value=count, expected="at least 5 unique years",
                        action=action,
                        message="Insufficient annual history",
                    )

    # Supports both physical-row failures and aggregate failures such as DQ-16.
    def _add(self, rule_id: str, severity: str, table_name: str, row_index: Any = "", **kwargs: Any) -> None:
        row = kwargs.pop("row", None)
        company_id_override = kwargs.pop("company_id", None)
        row = row if row is not None else pd.Series(dtype=object)
        row_number = int(row_index) + 2 if isinstance(row_index, int) else row_index
        company_id = row.get("company_id", row.get("id", ""))
        if company_id_override is not None:
            company_id = company_id_override
        self.failures.append(ValidationFailure(
            rule_id=rule_id,
            severity=severity,
            table_name=table_name,
            row_number=row_number,
            record_id=self._clean_scalar(row.get("id", "")),
            company_id=self._clean_scalar(company_id),
            year=self._clean_scalar(row.get("year", "")),
            column_name=kwargs.get("column_name", ""),
            raw_value=self._clean_scalar(kwargs.get("raw_value", "")),
            observed_value=self._clean_scalar(kwargs.get("observed_value", "")),
            expected=kwargs.get("expected", ""),
            action=kwargs.get("action", ""),
            message=kwargs.get("message", ""),
        ))


FAILURE_FIELDS = (
    "rule_id", "rule_name", "severity", "table_name", "row_number", "record_id",
    "company_id", "year", "column_name", "raw_value", "observed_value",
    "expected", "action", "message",
)


def write_validation_outputs(result: ValidationResult, output_dir: str | Path) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    failure_path = destination / "validation_failures.csv"
    with failure_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILURE_FIELDS)
        writer.writeheader()
        writer.writerows(failure.as_dict() for failure in result.failures)

    summary_path = destination / "validation_summary.csv"
    summary_rows = [
        {"metric": key, "value": value} for key, value in sorted(result.audit.items())
    ]
    pd.DataFrame(summary_rows, columns=("metric", "value")).to_csv(summary_path, index=False)
    return failure_path, summary_path


def read_processed_tables(processed_dir: str | Path) -> dict[str, pd.DataFrame]:
    root = Path(processed_dir)
    tables: dict[str, pd.DataFrame] = {}
    for path in sorted(root.glob("*.csv")):
        tables[path.stem] = pd.read_csv(path)
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Run N100 DQ-01–DQ-16 validation")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--loader-errors", type=Path, default=Path("output/read_errors.csv"))
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()

    tables = read_processed_tables(args.processed_dir)
    loader_errors = (
        pd.read_csv(args.loader_errors) if args.loader_errors.exists() else pd.DataFrame()
    )
    result = DataQualityValidator(
        tables, check_urls=args.check_urls, loader_errors=loader_errors
    ).validate()
    failure_path, summary_path = write_validation_outputs(result, args.output_dir)
    print(f"Validated {len(result.tables)} table(s)")
    print(f"Failures: {len(result.failures)} -> {failure_path}")
    print(f"Summary: {summary_path}")
    print(f"Load blocked: {result.load_blocked}")


if __name__ == "__main__":
    main()
