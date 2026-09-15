#!/usr/bin/env python3
"""Extract historical exchange rates from the Frankfurter REST API.

The script demonstrates:
1. A GET request to a public REST API.
2. Query parameters for date range, base currency and quote currencies.
3. JSON inspection and validation.
4. Conversion of the API response into an analysis-ready CSV file.

No API key or third-party Python package is required.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.frankfurter.dev/v2/rates"
START_DATE = "2026-08-12"
END_DATE = "2026-09-11"
BASE_CURRENCY = "USD"
QUOTE_CURRENCIES = ("INR", "EUR", "GBP")

OUTPUT_DIR = Path(__file__).resolve().parent
RAW_JSON_PATH = OUTPUT_DIR / "USD_Exchange_Rates_2026-08-12_to_2026-09-11_Raw.json"
CSV_PATH = OUTPUT_DIR / "USD_Exchange_Rates_2026-08-12_to_2026-09-11.csv"


def build_url() -> str:
    """Build the endpoint URL with safely encoded query parameters."""
    parameters = {
        "from": START_DATE,
        "to": END_DATE,
        "base": BASE_CURRENCY,
        "quotes": ",".join(QUOTE_CURRENCIES),
    }
    return f"{API_URL}?{urlencode(parameters)}"


def fetch_json(url: str) -> list[dict]:
    """Send a GET request and return the decoded JSON array."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Bluestock-Week2-API-Assignment/1.0",
        },
        method="GET",
    )

    with urlopen(request, timeout=30) as response:
        status_code = response.status
        content_type = response.headers.get("Content-Type", "")
        response_text = response.read().decode("utf-8")

    if status_code != 200:
        raise RuntimeError(f"API returned HTTP {status_code}")
    if "json" not in content_type.lower():
        raise RuntimeError(f"Expected JSON but received {content_type!r}")

    payload = json.loads(response_text)
    if not isinstance(payload, list):
        raise ValueError("Expected the top-level JSON value to be an array")
    return payload


def validate_records(records: list[dict]) -> list[dict]:
    """Keep the required fields and reject incomplete or invalid records."""
    required_fields = {"date", "base", "quote", "rate"}
    cleaned_records: list[dict] = []

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} is not a JSON object")
        missing = required_fields.difference(record)
        if missing:
            raise ValueError(f"Record {index} is missing fields: {sorted(missing)}")
        if record["base"] != BASE_CURRENCY:
            raise ValueError(f"Unexpected base currency in record {index}")
        if record["quote"] not in QUOTE_CURRENCIES:
            raise ValueError(f"Unexpected quote currency in record {index}")
        if not isinstance(record["rate"], (int, float)) or record["rate"] <= 0:
            raise ValueError(f"Invalid exchange rate in record {index}")

        cleaned_records.append(
            {
                "date": record["date"],
                "base_currency": record["base"],
                "quote_currency": record["quote"],
                "exchange_rate": record["rate"],
            }
        )

    cleaned_records.sort(key=lambda row: (row["date"], row["quote_currency"]))
    return cleaned_records


def save_raw_json(records: list[dict]) -> None:
    """Preserve the API response in readable JSON format."""
    RAW_JSON_PATH.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def save_csv(records: list[dict]) -> None:
    """Write a rectangular CSV that can be opened in Excel or Google Sheets."""
    fieldnames = ["date", "base_currency", "quote_currency", "exchange_rate"]
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def print_summary(records: list[dict], url: str) -> None:
    """Print evidence that the request and conversion completed successfully."""
    print(f"HTTP GET: {url}")
    print(f"Validated rows: {len(records)}")
    print(f"Date range: {records[0]['date']} to {records[-1]['date']}")
    print(f"Currencies: {', '.join(sorted({r['quote_currency'] for r in records}))}")
    print(f"Raw JSON: {RAW_JSON_PATH.name}")
    print(f"CSV: {CSV_PATH.name}")


def main() -> None:
    url = build_url()
    raw_records = fetch_json(url)
    clean_records = validate_records(raw_records)
    if not clean_records:
        raise ValueError("The API returned no exchange-rate records")
    save_raw_json(raw_records)
    save_csv(clean_records)
    print_summary(clean_records, url)


if __name__ == "__main__":
    main()
