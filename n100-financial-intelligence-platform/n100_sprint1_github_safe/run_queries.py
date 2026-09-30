"""Execute and audit the ten Day 21 exploratory queries."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd


QUERY_PATTERN = re.compile(
    r"-- Q(?P<number>\d{2}): (?P<title>[^\n]+)\n"
    r"(?P<sql>.*?;)(?=\n\n-- Q\d{2}:|\Z)",
    flags=re.DOTALL,
)


def parse_queries(path: str | Path) -> list[dict[str, str]]:
    text = Path(path).read_text(encoding="utf-8").strip()
    queries = [match.groupdict() for match in QUERY_PATTERN.finditer(text)]
    if len(queries) != 10:
        raise ValueError(f"Expected 10 exploratory queries; found {len(queries)}")
    return queries


def run_queries(
    database_path: str | Path = "db/nifty100.db",
    sql_path: str | Path = "notebooks/exploratory_queries.sql",
    output_dir: str | Path = "output/exploratory_results",
) -> Path:
    queries = parse_queries(sql_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for query in queries:
            frame = pd.read_sql_query(query["sql"], connection)
            result_path = destination / f"Q{query['number']}.csv"
            frame.to_csv(result_path, index=False)
            summary_rows.append({
                "query_id": f"Q{query['number']}",
                "title": query["title"],
                "status": "PASS",
                "row_count": len(frame),
                "output_file": result_path.name,
            })
    summary_path = destination.parent / "exploratory_query_audit.csv"
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run N100 exploratory SQL queries")
    parser.add_argument("--database", type=Path, default=Path("db/nifty100.db"))
    parser.add_argument(
        "--sql", type=Path, default=Path("notebooks/exploratory_queries.sql")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/exploratory_results")
    )
    args = parser.parse_args()
    summary = run_queries(args.database, args.sql, args.output_dir)
    print(f"Exploratory query audit: {summary}")


if __name__ == "__main__":
    main()
