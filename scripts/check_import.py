"""Verify all three BTS months in PostgreSQL against Stage 2 observed totals.

Only requires Python stdlib and the existing Docker Compose PostgreSQL service.
Run from the repository root: python scripts/check_import.py
"""

from __future__ import annotations

import shlex
import subprocess
import sys

EXPECTED = {
    "2025-01": (539747, 16312, 1166, 98130),
    "2025-02": (504884, 7405, 1003, 103102),
    "2025-03": (600872, 6923, 1648, 116034),
}

MONTHLY_SQL = """
SELECT TO_CHAR(flight_date, 'YYYY-MM') || ',' ||
       COUNT(*) || ',' ||
       COUNT(*) FILTER (WHERE cancelled) || ',' ||
       COUNT(*) FILTER (WHERE NOT cancelled AND diverted) || ',' ||
       COUNT(*) FILTER (
           WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15
       )
FROM flights
GROUP BY TO_CHAR(flight_date, 'YYYY-MM')
ORDER BY TO_CHAR(flight_date, 'YYYY-MM');
"""

BATCH_SQL = """
SELECT filename || ',' || status || ',' || rows_processed || ',' ||
       rows_loaded || ',' || rows_rejected || ',' || rows_skipped
FROM import_batches ORDER BY filename;
"""


def run_sql(sql: str) -> list[str]:
    shell_sql = 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c ' + shlex.quote(sql)
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c", shell_sql],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    try:
        records = run_sql(MONTHLY_SQL)
        batches = run_sql(BATCH_SQL)
        actual = {}
        for line in records:
            fields = line.split(",")
            if len(fields) != 5:
                raise ValueError(f"Unexpected monthly row: {line!r}")
            key = fields[0]
            if key in actual:
                raise ValueError(f"Duplicate month in output: {key}")
            actual[key] = tuple(int(v) for v in fields[1:])

        print("MONTH        FLIGHTS   CANCELLED   DIVERTED   DELAYED_15+")
        for month, expected in EXPECTED.items():
            received = actual.get(month)
            label = "OK" if received == expected else "MISMATCH"
            print(f"[{label}] {month}: {received} (expected {expected})")
        print("\nImport batches:")
        for line in batches:
            print("  " + line)

        if actual != EXPECTED:
            print("[ERROR] DB flight counts differ from the Stage 2 source profile")
            return 1
        if len(batches) != 3:
            print(f"[ERROR] Expected exactly 3 import batches, found {len(batches)}")
            return 1
        total_loaded = 0
        for line in batches:
            fields = line.split(",")
            if len(fields) != 6 or fields[1] != "completed":
                print(f"[ERROR] Unexpected batch: {line}")
                return 1
            processed, loaded, rejected, skipped = map(int, fields[2:])
            if processed != loaded + rejected + skipped or rejected:
                print(f"[ERROR] Invalid import accounting for {fields[0]}")
                return 1
            total_loaded += loaded
        if total_loaded != 1_645_503:
            print("[ERROR] Loaded batch totals do not match the flight dataset")
            return 1
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] Import check failed: {exc}", file=sys.stderr)
        return 1

    print("\n[OK] 1,645,503 BTS flights verified in PostgreSQL")
    print("[OK] All three import batches completed; no rejected rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
