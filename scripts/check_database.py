"""Smoke-check the local Docker Compose PostgreSQL schema without extra packages.

Usage (Windows CMD / PowerShell):
    python scripts/check_database.py
"""

from __future__ import annotations

import shlex
import subprocess
import sys

SQL = """
SELECT
  (SELECT count(*) FROM information_schema.tables
   WHERE table_schema = 'public' AND table_name IN
   ('airlines', 'airports', 'flights', 'import_batches'))::text
  || ',' ||
  (SELECT count(*) FROM pg_indexes
   WHERE schemaname = 'public' AND indexname IN
   ('idx_flights_airline_date', 'idx_flights_origin_date',
    'idx_flights_destination_date', 'idx_flights_import_batch',
    'idx_flights_delayed_date'))::text
  || ',' ||
  (SELECT count(*) FROM pg_constraint
   WHERE conrelid = 'public.flights'::regclass AND contype = 'f')::text;
"""


def main() -> int:
    # shlex.quote targets /bin/sh inside the Linux container, not Windows CMD.
    shell_command = (
        'exec psql -X -v ON_ERROR_STOP=1 '
        '-U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c '
        + shlex.quote(SQL)
    )
    command = [
        "docker", "compose", "exec", "-T", "postgres", "sh", "-c", shell_command
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print("[ERROR] Docker CLI is not available", file=sys.stderr)
        return 1

    if result.returncode:
        print("[ERROR] Database not ready or schema check failed", file=sys.stderr)
        print((result.stderr or result.stdout).strip(), file=sys.stderr)
        return 1

    received = result.stdout.strip()
    if received != "4,5,4":
        print(f"[ERROR] Schema mismatch: expected tables,indexes,FKs=4,5,4; got {received}")
        return 1
    print("[OK] PostgreSQL reachable")
    print("[OK] 4 tables: airlines, airports, flights, import_batches")
    print("[OK] 5 analytics/ETL indexes")
    print("[OK] 4 foreign keys on flights")
    print("[INFO] Flight data will be imported in Stage 4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
