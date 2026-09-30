from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.etl.loader import (
    EmptySourceFileError,
    ExcelLoader,
    InvalidFileFormatError,
    MissingWorksheetError,
    SchemaValidationError,
    detect_dataset,
    normalize_column_name,
    normalize_missing_value,
    parse_number,
    parse_percentage,
)
from src.etl.normaliser import normalize_ticker, normalize_year


class LoaderUnitTests(unittest.TestCase):
    def test_01_numeric_years(self):
        self.assertEqual(normalize_year(2024), "2024-03")
        self.assertEqual(normalize_year(2024.0), "2024-03")

    def test_02_text_years(self):
        self.assertEqual(normalize_year("Mar-23"), "2023-03")
        self.assertEqual(normalize_year("December 2021"), "2021-12")

    def test_03_financial_years(self):
        self.assertEqual(normalize_year("FY24"), "2024-03")
        self.assertEqual(normalize_year("FY 2020"), "2020-03")

    def test_04_ticker_whitespace(self):
        self.assertEqual(normalize_ticker("  HDFC BANK\n"), "HDFCBANK")

    def test_05_ticker_exchange_suffix(self):
        self.assertEqual(normalize_ticker("NSE: TCS"), "TCS")
        self.assertEqual(normalize_ticker("bse: wipro"), "WIPRO")

    def test_06_missing_values(self):
        self.assertTrue(pd.isna(normalize_missing_value(" NULL ")))
        self.assertTrue(pd.isna(normalize_missing_value("")))

    def test_07_numbers_with_commas(self):
        self.assertEqual(parse_number("1,234,567.50"), 1234567.5)
        self.assertEqual(parse_number("(1,234)"), -1234.0)

    def test_08_percentages(self):
        self.assertEqual(parse_percentage("12.5%"), 12.5)
        self.assertEqual(parse_percentage(18), 18.0)

    def test_09_column_normalisation(self):
        self.assertEqual(normalize_column_name(" Annual Report "), "annual_report")
        self.assertEqual(normalize_column_name("ROE (%)"), "roe_percentage")

    def test_10_detects_prefixed_source_and_table(self):
        spec = detect_dataset("1788501606103-7177b6c2-companies.xlsx")
        self.assertEqual(spec.table_name, "companies")
        self.assertEqual(spec.header_row, 1)

    def test_11_detects_supplementary_header(self):
        spec = detect_dataset("stock_prices.xlsx")
        self.assertEqual(spec.table_name, "stock_prices")
        self.assertEqual(spec.header_row, 0)

    def test_12_invalid_file_format(self):
        with self.assertRaises(InvalidFileFormatError):
            detect_dataset("companies.csv")

    def test_13_reads_core_sheet_and_converts_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "companies.xlsx"
            columns = [
                "id", "company_logo", "company_name", "chart_link", "about_company",
                "website", "nse_profile", "bse_profile", "face_value", "book_value",
                "roce_percentage", "roe_percentage",
            ]
            row = [" nse: tcs ", None, "TCS", None, "About", None, None, None,
                   "10", "1,234", "15%", 20]
            with pd.ExcelWriter(source, engine="openpyxl") as writer:
                pd.DataFrame([["metadata"]]).to_excel(
                    writer, sheet_name="Companies", index=False, header=False
                )
                pd.DataFrame([row], columns=columns).to_excel(
                    writer, sheet_name="Companies", index=False, startrow=1
                )
            result = ExcelLoader(root / "out").load_file(source)
            self.assertEqual(result.table_name, "companies")
            self.assertEqual(result.dataframe.loc[0, "id"], "TCS")
            self.assertEqual(result.dataframe.loc[0, "book_value"], 1234.0)

    def test_14_unexpected_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "peer_groups.xlsx"
            frame = pd.DataFrame({
                "id": [1], "peer_group_name": ["IT"], "company_id": ["TCS"],
                "is_benchmark": [1], "unexpected": ["x"],
            })
            frame.to_excel(source, sheet_name="Sheet1", index=False)
            with self.assertRaises(SchemaValidationError):
                ExcelLoader(root / "out").load_file(source)

    def test_15_empty_file_is_rejected_and_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "companies.xlsx"
            source.touch()
            loader = ExcelLoader(root / "out")
            with self.assertRaises(EmptySourceFileError):
                loader.load_file(source)
            self.assertIn("EmptySourceFileError", loader.error_path.read_text())

    def test_16_missing_sheet_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "companies.xlsx"
            pd.DataFrame({"id": [1]}).to_excel(source, sheet_name="Wrong", index=False)
            with self.assertRaises(MissingWorksheetError):
                ExcelLoader(root / "out").load_file(source)

    def test_17_invalid_numeric_value_is_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "peer_groups.xlsx"
            frame = pd.DataFrame({
                "id": ["not-a-number"], "peer_group_name": ["IT"],
                "company_id": [" tcs "], "is_benchmark": [1],
            })
            frame.to_excel(source, sheet_name="Sheet1", index=False)
            loader = ExcelLoader(root / "out")
            result = loader.load_file(source)
            self.assertTrue(pd.isna(result.dataframe.loc[0, "id"]))
            self.assertEqual(result.dataframe.loc[0, "company_id"], "TCS")
            self.assertEqual(result.errors[0]["error_type"], "NumericParseError")


if __name__ == "__main__":
    unittest.main()
