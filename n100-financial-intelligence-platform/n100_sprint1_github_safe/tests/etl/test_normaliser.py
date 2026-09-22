from __future__ import annotations

import unittest

from src.etl.normaliser import is_missing, normalize_ticker, normalize_year


class NormaliserTests(unittest.TestCase):
    def test_missing_values(self):
        for value in [None, "", "   ", float("nan")]:
            with self.subTest(value=value):
                self.assertTrue(is_missing(value))

    def test_tickers(self):
        cases = [
        (" hdfcbank ", "HDFCBANK"),
        ("NSE: TCS", "TCS"),
        ("bse:wipro", "WIPRO"),
        ("BAJAJ-AUTO", "BAJAJ-AUTO"),
        ("M&M", "M&M"),
        (None, "MISSING"),
        ("", "MISSING"),
        ("   ", "MISSING"),
        ("infy", "INFY"),
        (" NSE:INFY ", "INFY"),
        ("BSE : RELIANCE", "RELIANCE"),
        (" bajaj - auto ", "BAJAJ-AUTO"),
        ("HDFC BANK", "HDFCBANK"),
        ("itc", "ITC"),
        ("LTIM", "LTIM"),
        ("pnb", "PNB"),
        (" tcs\n", "TCS"),
        ("\tSBIN\t", "SBIN"),
        ("ADANIENSOL", "ADANIENSOL"),
        ("nSe : m&m", "M&M"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ticker(raw), expected)

    def test_years(self):
        cases = [
        (2024, "2024-03"),
        (2024.0, "2024-03"),
        ("Mar 2024", "2024-03"),
        ("Mar-24", "2024-03"),
        ("Mar 23", "2023-03"),
        ("March-2023", "2023-03"),
        ("Dec 2012", "2012-12"),
        ("Dec-22", "2022-12"),
        ("Jun-23", "2023-06"),
        ("Sep-24", "2024-09"),
        ("December 2021", "2021-12"),
        ("June 2015", "2015-06"),
        ("September 2019", "2019-09"),
        ("FY24", "2024-03"),
        ("FY 2020", "2020-03"),
        ("2023-03", "2023-03"),
        ("Mar 2016 9m", "2016-03"),
        ("Mar 2023 15", "2023-03"),
        ("TTM", "PARSE_ERROR"),
        (2024.5, "PARSE_ERROR"),
        ("xyz", "PARSE_ERROR"),
        ("2024-13", "PARSE_ERROR"),
        (1899, "PARSE_ERROR"),
        (2101, "PARSE_ERROR"),
        (None, "PARSE_ERROR"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_year(raw), expected)


if __name__ == "__main__":
    unittest.main()
