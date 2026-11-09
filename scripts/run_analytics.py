"""Run reusable parameterized PostgreSQL analytics queries for FlightInsight.

Examples (inside the analytics Docker Compose service):
    python scripts/run_analytics.py summary
    python scripts/run_analytics.py airlines --min-sample-size 500
    python scripts/run_analytics.py trends_daily --airline AA --date-from 2025-02-01
    python scripts/run_analytics.py summary --explain

SQL files under database/queries/ are also intended for use by the upcoming API.
No SQL is assembled using user-supplied values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = ROOT / "database" / "queries"
QUERIES = (
    "summary", "airlines", "airports_departure", "airports_arrival",
    "delays_weekday", "delays_hour", "cancellations", "delay_causes",
    "trends_daily",
)
DEFAULT_FROM = date(2025, 1, 1)
DEFAULT_TO = date(2025, 3, 31)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def optional_code(value: str | None, what: str) -> str | None:
    if value is None:
        return None
    candidate = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", candidate):
        raise ValueError(f"{what}: 2-10 ASCII letters or digits expected")
    return candidate


def get_parameters(
    date_from: date = DEFAULT_FROM, date_to: date = DEFAULT_TO,
    airline_code: str | None = None, origin_code: str | None = None,
    destination_code: str | None = None, min_sample_size: int = 100,
) -> dict[str, Any]:
    if date_from > date_to:
        raise ValueError("--date-from must be on or before --date-to")
    if not 0 <= min_sample_size <= 1_000_000:
        raise ValueError("--min-sample-size must be between 0 and 1000000")
    return {
        "date_from": date_from, "date_to": date_to,
        "airline_code": optional_code(airline_code, "airline"),
        "origin_code": optional_code(origin_code, "origin"),
        "destination_code": optional_code(destination_code, "destination"),
        "min_sample_size": min_sample_size,
    }


def load_query(name: str) -> str:
    # Fixed allow-list: no filesystem paths supplied by the caller.
    if name not in QUERIES:
        raise ValueError(f"Unknown query: {name}")
    return (QUERY_DIR / f"{name}.sql").read_text(encoding="utf-8")


def open_connection() -> Any:
    """Open a read-only connection. Imports psycopg only inside Docker."""
    import psycopg
    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "flightinsight"),
        user=os.environ.get("POSTGRES_USER", "flightinsight"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=15,
        autocommit=True,
    )
    try:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute("SET statement_timeout = '120s'")
    except Exception:
        conn.close()
        raise
    return conn


def execute_query(conn: Any, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(load_query(name), params)
        return list(cursor.fetchall())


def json_default(obj: Any) -> str | float:
    if isinstance(obj, (Decimal, date)):
        return str(obj)
    raise TypeError(f"Cannot serialize {type(obj).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FlightInsight SQL analytics on real BTS data")
    parser.add_argument("query", choices=(*QUERIES, "all"))
    parser.add_argument("--date-from", type=parse_iso_date, default=DEFAULT_FROM)
    parser.add_argument("--date-to", type=parse_iso_date, default=DEFAULT_TO)
    parser.add_argument("--airline", default=None, help="BTS reporting airline code, e.g. AA")
    parser.add_argument("--origin", default=None, help="Origin airport code, e.g. JFK")
    parser.add_argument("--destination", default=None, help="Destination airport code, e.g. LAX")
    parser.add_argument("--min-sample-size", type=int, default=100)
    parser.add_argument("--limit", type=int, default=7, help="Printed rows per query (0 = all)")
    parser.add_argument("--explain", action="store_true", help="Show PostgreSQL EXPLAIN ANALYZE and BUFFERS")
    args = parser.parse_args(argv)
    if args.explain and args.query == "all":
        parser.error("--explain requires a single query")
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    try:
        params = get_parameters(
            args.date_from, args.date_to, args.airline, args.origin,
            args.destination, args.min_sample_size,
        )
        with open_connection() as conn:
            for name in (QUERIES if args.query == "all" else (args.query,)):
                print(f"\n=== {name} ===", flush=True)
                if args.explain:
                    # SQL text is read from an internal fixed-file allow-list only.
                    with conn.cursor() as cursor:
                        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + load_query(name), params)
                        for line in cursor.fetchall():
                            print(line[0])
                else:
                    records = execute_query(conn, name, params)
                    display = records if args.limit == 0 else records[:args.limit]
                    print(json.dumps(display, indent=2, ensure_ascii=False, default=json_default))
                    if len(records) > len(display):
                        print(f"[INFO] Showing {len(display)} of {len(records)} rows; use --limit 0 for all")
        return 0
    except Exception as exc:
        print(f"[ERROR] Analytics failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
