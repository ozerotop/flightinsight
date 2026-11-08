"""Profile BTS ZIP CSV files (Jan-Mar 2025) without extracting them.

Run from repository root:
    python scripts/inspect_bts.py

This script does not modify any dataset and requires only Python stdlib.
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
YEAR = 2025
MONTHS = (1, 2, 3)

REQUIRED_COLUMNS = (
    "FlightDate",
    "Reporting_Airline",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
    "DepTime",
    "CRSArrTime",
    "ArrTime",
    "DepDelay",
    "ArrDelay",
    "Cancelled",
    "Diverted",
    "CarrierDelay",
    "WeatherDelay",
    "NASDelay",
    "SecurityDelay",
    "LateAircraftDelay",
)

IDENTITY_COLUMNS = (
    "FlightDate",
    "Reporting_Airline",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
)


def is_true(raw: str) -> bool | None:
    if raw in {"0", "0.0", "0.00"}:
        return False
    if raw in {"1", "1.0", "1.00"}:
        return True
    return None


def inspect_month(month: int) -> tuple[str, ...]:
    path = RAW_DIR / f"bts_{YEAR}_{month:02d}.zip"
    if not path.is_file():
        raise FileNotFoundError(f"Missing ZIP: {path}")

    counts: Counter[str] = Counter()
    first_date: date | None = None
    last_date: date | None = None
    seen_flights: set[tuple[str, ...]] = set()

    with zipfile.ZipFile(path) as archive:
        csv_files = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(csv_files) != 1:
            raise ValueError(f"Expected one CSV in {path.name}, found {csv_files}")
        with archive.open(csv_files[0]) as stream:
            reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
            source_headers = next(reader)
            trailing_empty_header = bool(source_headers and not source_headers[-1].strip())
            headers = source_headers[:-1] if trailing_empty_header else source_headers
            if len(headers) != len(set(headers)):
                raise ValueError(f"Duplicate column names in {path.name}")
            missing_columns = set(REQUIRED_COLUMNS) - set(headers)
            if missing_columns:
                raise ValueError(f"Missing columns: {sorted(missing_columns)}")

            index = {name: pos for pos, name in enumerate(headers)}
            for row in reader:
                if trailing_empty_header and len(row) == len(source_headers):
                    if row[-1].strip():
                        counts["nonempty_trailing_column"] += 1
                    row = row[:-1]
                if len(row) != len(headers):
                    counts["malformed_rows"] += 1
                    continue
                counts["rows"] += 1

                def get(name: str) -> str:
                    return row[index[name]].strip()

                for field in REQUIRED_COLUMNS:
                    if not get(field):
                        counts[f"empty_{field}"] += 1

                raw_date = get("FlightDate")
                try:
                    flight_date = date.fromisoformat(raw_date)
                except ValueError:
                    counts["invalid_dates"] += 1
                else:
                    if flight_date.year != YEAR or flight_date.month != month:
                        counts["wrong_month"] += 1
                    first_date = min(first_date, flight_date) if first_date else flight_date
                    last_date = max(last_date, flight_date) if last_date else flight_date

                cancellation = is_true(get("Cancelled"))
                diversion = is_true(get("Diverted"))
                if cancellation is None or diversion is None:
                    counts["invalid_status"] += 1
                elif cancellation:
                    counts["cancelled"] += 1
                elif diversion:
                    counts["diverted"] += 1
                else:
                    counts["completed"] += 1
                    if not get("ArrDelay"):
                        counts["completed_missing_arr_delay"] += 1
                    else:
                        try:
                            arrival_delay = float(get("ArrDelay"))
                        except ValueError:
                            counts["completed_invalid_arr_delay"] += 1
                        else:
                            if arrival_delay >= 15:
                                counts["delayed_15min"] += 1

                if all(get(name) for name in IDENTITY_COLUMNS):
                    candidate_key = tuple(get(name) for name in IDENTITY_COLUMNS)
                    if candidate_key in seen_flights:
                        counts["repeated_candidate_key"] += 1
                    else:
                        seen_flights.add(candidate_key)
                else:
                    counts["missing_candidate_key"] += 1

    print(f"\n== {YEAR}-{month:02d} ==")
    print(f"Archive: {path.name}")
    print(f"Columns: {len(headers)} (plus trailing blank: {trailing_empty_header})")
    print(f"Rows: {counts['rows']:,}")
    print(f"Date range: {first_date} .. {last_date}")
    print(f"Completed: {counts['completed']:,}")
    print(f"Cancelled: {counts['cancelled']:,}")
    print(f"Diverted: {counts['diverted']:,}")
    print(f"Arrivals delayed >=15 min: {counts['delayed_15min']:,}")
    print(f"Completed with missing ArrDelay: {counts['completed_missing_arr_delay']:,}")
    print(f"Completed with invalid ArrDelay: {counts['completed_invalid_arr_delay']:,}")
    print(f"Invalid status values: {counts['invalid_status']:,}")
    print(f"Invalid dates: {counts['invalid_dates']:,}")
    print(f"Rows from wrong month: {counts['wrong_month']:,}")
    print(f"Malformed CSV rows: {counts['malformed_rows']:,}")
    print(f"Nonempty trailing fields: {counts['nonempty_trailing_column']:,}")
    print(f"Repeated candidate keys (not confirmed duplicates): {counts['repeated_candidate_key']:,}")
    print(f"Missing candidate keys: {counts['missing_candidate_key']:,}")

    print("Missing values in required columns (nonzero only):")
    for name in REQUIRED_COLUMNS:
        missing = counts[f"empty_{name}"]
        if missing:
            print(f"  {name}: {missing:,}")
    return tuple(headers)


def main() -> int:
    baseline: tuple[str, ...] | None = None
    try:
        for month in MONTHS:
            current = inspect_month(month)
            if baseline is not None and current != baseline:
                print(f"WARNING: schema differs in month {month}")
            if baseline is None:
                baseline = current
    except (FileNotFoundError, ValueError, OSError, zipfile.BadZipFile, StopIteration) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\nInspection completed for January, February, March 2025.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
