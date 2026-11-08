"""Import BTS January-March 2025 ZIP files into the Stage 3 PostgreSQL schema.

The importer is intended to run inside the Docker Compose ETL service:
    docker compose run --build --rm etl

Each ZIP is imported in one transaction. Source ZIP SHA-256 and the unique
scheduled-flight constraint make repeated runs idempotent. All source CSV rows
are streamed directly from ZIP through PostgreSQL COPY; no pandas-sized data
frame is held in memory.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import sys
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
YEAR = 2025
MONTHS = (1, 2, 3)
PROGRESS_INTERVAL = 100_000

# Fields are ordered exactly as the temporary PostgreSQL staging table.
STAGE_COLUMNS = (
    "flight_date", "airline_code", "bts_airline_id", "flight_number",
    "origin_code", "origin_bts_id", "origin_city", "origin_state",
    "destination_code", "destination_bts_id", "destination_city", "destination_state",
    "scheduled_departure_hhmm", "actual_departure_hhmm",
    "scheduled_arrival_hhmm", "actual_arrival_hhmm",
    "departure_delay", "arrival_delay", "cancelled", "diverted",
    "cancellation_code", "carrier_delay", "weather_delay", "nas_delay",
    "security_delay", "late_aircraft_delay",
)

SOURCE_COLUMNS = (
    "FlightDate", "Reporting_Airline", "DOT_ID_Reporting_Airline",
    "Flight_Number_Reporting_Airline", "Origin", "OriginAirportID",
    "OriginCityName", "OriginState", "Dest", "DestAirportID",
    "DestCityName", "DestState", "CRSDepTime", "DepTime",
    "CRSArrTime", "ArrTime", "DepDelay", "ArrDelay",
    "Cancelled", "Diverted", "CancellationCode", "CarrierDelay",
    "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay",
)

STAGE_DDL = """
CREATE TEMP TABLE stage_flights (
    flight_date DATE NOT NULL,
    airline_code VARCHAR(10) NOT NULL,
    bts_airline_id INTEGER,
    flight_number VARCHAR(15) NOT NULL,
    origin_code VARCHAR(10) NOT NULL,
    origin_bts_id INTEGER,
    origin_city TEXT,
    origin_state VARCHAR(2),
    destination_code VARCHAR(10) NOT NULL,
    destination_bts_id INTEGER,
    destination_city TEXT,
    destination_state VARCHAR(2),
    scheduled_departure_hhmm SMALLINT NOT NULL,
    actual_departure_hhmm SMALLINT,
    scheduled_arrival_hhmm SMALLINT NOT NULL,
    actual_arrival_hhmm SMALLINT,
    departure_delay NUMERIC(9,2),
    arrival_delay NUMERIC(9,2),
    cancelled BOOLEAN NOT NULL,
    diverted BOOLEAN NOT NULL,
    cancellation_code CHAR(1),
    carrier_delay NUMERIC(9,2),
    weather_delay NUMERIC(9,2),
    nas_delay NUMERIC(9,2),
    security_delay NUMERIC(9,2),
    late_aircraft_delay NUMERIC(9,2)
) ON COMMIT DROP;
"""

UPSERT_AIRLINES = """
INSERT INTO airlines (airline_code, bts_airline_id)
SELECT airline_code, MAX(bts_airline_id)
FROM stage_flights
GROUP BY airline_code
ON CONFLICT (airline_code) DO UPDATE
SET bts_airline_id = COALESCE(airlines.bts_airline_id, EXCLUDED.bts_airline_id);
"""

UPSERT_AIRPORTS = """
WITH appearances AS (
    SELECT origin_code AS code, origin_bts_id AS bts_id,
           origin_city AS city, origin_state AS state
    FROM stage_flights
    UNION ALL
    SELECT destination_code, destination_bts_id, destination_city, destination_state
    FROM stage_flights
), grouped AS (
    SELECT code, MAX(bts_id) AS bts_id, MAX(city) AS city, MAX(state) AS state
    FROM appearances
    GROUP BY code
)
INSERT INTO airports (airport_code, bts_airport_id, city, state)
SELECT code, bts_id, city, state FROM grouped WHERE TRUE
ON CONFLICT (airport_code) DO UPDATE SET
    bts_airport_id = COALESCE(airports.bts_airport_id, EXCLUDED.bts_airport_id),
    city = COALESCE(airports.city, EXCLUDED.city),
    state = COALESCE(airports.state, EXCLUDED.state);
"""

INSERT_FLIGHTS = """
WITH inserted AS (
    INSERT INTO flights (
        flight_date, airline_id, flight_number,
        origin_airport_id, destination_airport_id,
        scheduled_departure_hhmm, actual_departure_hhmm,
        scheduled_arrival_hhmm, actual_arrival_hhmm,
        departure_delay, arrival_delay, cancelled, diverted,
        cancellation_code, carrier_delay, weather_delay,
        nas_delay, security_delay, late_aircraft_delay,
        import_batch_id
    )
    SELECT
        s.flight_date, a.airline_id, s.flight_number,
        o.airport_id, d.airport_id,
        s.scheduled_departure_hhmm, s.actual_departure_hhmm,
        s.scheduled_arrival_hhmm, s.actual_arrival_hhmm,
        s.departure_delay, s.arrival_delay, s.cancelled, s.diverted,
        s.cancellation_code, s.carrier_delay, s.weather_delay,
        s.nas_delay, s.security_delay, s.late_aircraft_delay,
        %s
    FROM stage_flights s
    JOIN airlines a ON a.airline_code = s.airline_code
    JOIN airports o ON o.airport_code = s.origin_code
    JOIN airports d ON d.airport_code = s.destination_code
    WHERE TRUE
    ON CONFLICT ON CONSTRAINT flights_source_identity_unique DO NOTHING
    RETURNING flight_id
)
SELECT COUNT(*) FROM inserted;
"""


@dataclass
class Counters:
    processed: int = 0
    accepted: int = 0
    rejected: int = 0
    loaded: int = 0
    skipped: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_text(value: str, name: str, limit: int) -> str:
    result = value.strip()
    if not result or len(result) > limit:
        raise ValueError(f"{name}: missing or longer than {limit} characters")
    return result


def optional_int(value: str, name: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name}: not an integer") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"{name}: not an integer")
    result = int(number)
    if not -(2**31) <= result < 2**31:
        raise ValueError(f"{name}: outside PostgreSQL INTEGER")
    return result


def hhmm(value: str, name: str, required: bool = False) -> int | None:
    n = optional_int(value, name)
    if n is None:
        if required:
            raise ValueError(f"{name}: missing scheduled time")
        return None
    if n != 2400 and not (0 <= n <= 2359 and n % 100 < 60):
        raise ValueError(f"{name}: invalid local HHMM {n}")
    return n


def optional_decimal(value: str, name: str, cause: bool = False) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name}: not numeric") from exc
    if not result.is_finite() or abs(result) > Decimal("9999999.99"):
        raise ValueError(f"{name}: outside NUMERIC(9,2)")
    if result.as_tuple().exponent < -2 and result != result.quantize(Decimal("0.01")):
        raise ValueError(f"{name}: more than two decimal places")
    if cause and result < 0:
        raise ValueError(f"{name}: negative cause delay")
    return result


def status_flag(value: str, name: str) -> bool:
    number = optional_decimal(value, name)
    if number == 1:
        return True
    if number == 0:
        return False
    raise ValueError(f"{name}: expected 0 or 1")


def city_name(raw: str, state: str | None) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if state and value.endswith(", " + state):
        return value[: -(len(state) + 2)]
    return value


def parse_record(record: dict[str, str], month: int) -> tuple[Any, ...]:
    def read(field: str) -> str:
        return record[field].strip()

    try:
        flight_date = date.fromisoformat(read("FlightDate"))
    except ValueError as exc:
        raise ValueError("FlightDate: invalid date") from exc
    if flight_date.year != YEAR or flight_date.month != month:
        raise ValueError("FlightDate: does not match the source month")

    airline_code = required_text(read("Reporting_Airline"), "Reporting_Airline", 10)
    flight_number = required_text(read("Flight_Number_Reporting_Airline"), "Flight_Number", 15)
    origin_code = required_text(read("Origin"), "Origin", 10)
    dest_code = required_text(read("Dest"), "Dest", 10)

    origin_state = read("OriginState") or None
    dest_state = read("DestState") or None
    if origin_state is not None and len(origin_state) != 2:
        raise ValueError("OriginState: expected two-character state code")
    if dest_state is not None and len(dest_state) != 2:
        raise ValueError("DestState: expected two-character state code")

    cancelled = status_flag(read("Cancelled"), "Cancelled")
    diverted = status_flag(read("Diverted"), "Diverted")
    arrival_delay = optional_decimal(read("ArrDelay"), "ArrDelay")
    if not cancelled and not diverted and arrival_delay is None:
        raise ValueError("ArrDelay: missing for a normally completed flight")

    cancellation_code = read("CancellationCode") or None
    if cancellation_code is not None and cancellation_code not in ("A", "B", "C", "D"):
        raise ValueError("CancellationCode: unsupported value")

    return (
        flight_date,
        airline_code,
        optional_int(read("DOT_ID_Reporting_Airline"), "DOT_ID_Reporting_Airline"),
        flight_number,
        origin_code,
        optional_int(read("OriginAirportID"), "OriginAirportID"),
        city_name(read("OriginCityName"), origin_state),
        origin_state,
        dest_code,
        optional_int(read("DestAirportID"), "DestAirportID"),
        city_name(read("DestCityName"), dest_state),
        dest_state,
        hhmm(read("CRSDepTime"), "CRSDepTime", required=True),
        hhmm(read("DepTime"), "DepTime"),
        hhmm(read("CRSArrTime"), "CRSArrTime", required=True),
        hhmm(read("ArrTime"), "ArrTime"),
        optional_decimal(read("DepDelay"), "DepDelay"),
        arrival_delay,
        cancelled,
        diverted,
        cancellation_code,
        optional_decimal(read("CarrierDelay"), "CarrierDelay", cause=True),
        optional_decimal(read("WeatherDelay"), "WeatherDelay", cause=True),
        optional_decimal(read("NASDelay"), "NASDelay", cause=True),
        optional_decimal(read("SecurityDelay"), "SecurityDelay", cause=True),
        optional_decimal(read("LateAircraftDelay"), "LateAircraftDelay", cause=True),
    )


def load_csv_to_staging(cur: Any, path: Path, month: int, counters: Counters) -> None:
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"{path.name}: expected exactly one CSV, got {csv_names}")
        with archive.open(csv_names[0]) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
            headers = next(reader)
            trailing = bool(headers and not headers[-1].strip())
            columns = headers[:-1] if trailing else headers
            if len(set(columns)) != len(columns):
                raise ValueError(f"{path.name}: duplicate CSV column names")
            missing = sorted(set(SOURCE_COLUMNS) - set(columns))
            if missing:
                raise ValueError(f"{path.name}: missing columns: {missing}")
            copy_sql = "COPY stage_flights (" + ", ".join(STAGE_COLUMNS) + ") FROM STDIN"
            problems: list[str] = []
            with cur.copy(copy_sql) as copier:
                for line, row in enumerate(reader, start=2):
                    counters.processed += 1
                    if trailing and len(row) == len(headers):
                        if row[-1].strip():
                            counters.rejected += 1
                            if len(problems) < 5:
                                problems.append(f"line {line}: unexpected nonempty final column")
                            continue
                        row = row[:-1]
                    if len(row) != len(columns):
                        counters.rejected += 1
                        if len(problems) < 5:
                            problems.append(f"line {line}: expected {len(columns)} fields, got {len(row)}")
                        continue
                    try:
                        transformed = parse_record(dict(zip(columns, row)), month)
                    except (ValueError, KeyError) as exc:
                        counters.rejected += 1
                        if len(problems) < 5:
                            problems.append(f"line {line}: {exc}")
                        continue
                    copier.write_row(transformed)
                    counters.accepted += 1
                    if counters.processed % PROGRESS_INTERVAL == 0:
                        print(f"[PROGRESS] {path.name}: {counters.processed:,} source rows", flush=True)
            if counters.rejected:
                raise ValueError(
                    f"{path.name}: {counters.rejected} invalid rows; no data committed. "
                    + " | ".join(problems)
                )
            if not counters.processed:
                raise ValueError(f"{path.name}: empty CSV")


def verify_staging(cur: Any, counters: Counters) -> None:
    cur.execute("SELECT COUNT(*) FROM stage_flights")
    staged = cur.fetchone()[0]
    if staged != counters.accepted:
        raise ValueError(f"COPY row count mismatch: Python={counters.accepted}, SQL={staged}")

    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM stage_flights
            GROUP BY flight_date, airline_code, flight_number,
                     origin_code, destination_code, scheduled_departure_hhmm
            HAVING COUNT(*) > 1
        )
    """)
    if cur.fetchone()[0]:
        raise ValueError("Duplicate scheduled-flight candidate keys within one BTS source")


def record_failure(conn: Any, path: Path, sha256: str, counters: Counters, message: str) -> None:
    """Persist failure information outside the rolled-back data transaction."""
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO import_batches (
                        filename, source_sha256, imported_at, finished_at,
                        rows_processed, rows_loaded, rows_rejected,
                        rows_skipped, status, error_message
                    ) VALUES (%s, %s, now(), now(), %s, 0, %s, 0, 'failed', %s)
                    ON CONFLICT (source_sha256) DO UPDATE SET
                        filename = EXCLUDED.filename,
                        finished_at = now(),
                        rows_processed = EXCLUDED.rows_processed,
                        rows_loaded = 0,
                        rows_rejected = EXCLUDED.rows_rejected,
                        rows_skipped = 0,
                        status = 'failed',
                        error_message = EXCLUDED.error_message
                    WHERE import_batches.status <> 'completed'
                """, (path.name, sha256, counters.processed, counters.rejected, message[:3000]))
    except Exception as exc:
        print(f"[WARNING] Could not save failed batch status: {exc}", file=sys.stderr)


def import_one(conn: Any, path: Path, month: int) -> bool:
    """Return True when loaded, False when matching completed SHA is skipped."""
    checksum = sha256_file(path)
    counters = Counters()
    print(f"\n[START] {path.name} sha256={checksum[:12]}...", flush=True)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                # Lock is held until this transaction commits or rolls back.
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)", (checksum,))
                cur.execute("SELECT batch_id, status FROM import_batches WHERE source_sha256 = %s", (checksum,))
                found = cur.fetchone()
                if found is not None and found[1] == "completed":
                    print(f"[SKIP] {path.name}: this SHA-256 was already fully imported", flush=True)
                    return False

                if found is None:
                    cur.execute("""
                        INSERT INTO import_batches (filename, source_sha256, status)
                        VALUES (%s, %s, 'running') RETURNING batch_id
                    """, (path.name, checksum))
                    batch_id = cur.fetchone()[0]
                else:
                    batch_id = found[0]
                    cur.execute("""
                        UPDATE import_batches SET
                            filename = %s, imported_at = now(), finished_at = NULL,
                            rows_processed = 0, rows_loaded = 0,
                            rows_rejected = 0, rows_skipped = 0,
                            status = 'running', error_message = NULL
                        WHERE batch_id = %s
                    """, (path.name, batch_id))

                cur.execute(STAGE_DDL)
                load_csv_to_staging(cur, path, month, counters)
                verify_staging(cur, counters)
                cur.execute(UPSERT_AIRLINES)
                cur.execute(UPSERT_AIRPORTS)
                cur.execute(INSERT_FLIGHTS, (batch_id,))
                counters.loaded = cur.fetchone()[0]
                counters.skipped = counters.accepted - counters.loaded
                if counters.skipped < 0:
                    raise ValueError("Impossible row counts after database INSERT")
                cur.execute("""
                    UPDATE import_batches SET
                        finished_at = now(), rows_processed = %s,
                        rows_loaded = %s, rows_rejected = %s,
                        rows_skipped = %s, status = 'completed', error_message = NULL
                    WHERE batch_id = %s
                """, (
                    counters.processed, counters.loaded, counters.rejected,
                    counters.skipped, batch_id
                ))
        print(
            f"[OK] {path.name}: processed={counters.processed:,}, "
            f"loaded={counters.loaded:,}, skipped={counters.skipped:,}, "
            f"rejected={counters.rejected:,}",
            flush=True,
        )
        return True
    except Exception as exc:
        print(f"[ERROR] {path.name}: {exc}", file=sys.stderr, flush=True)
        record_failure(conn, path, checksum, counters, str(exc))
        raise


def main() -> int:
    try:
        import psycopg
    except ImportError:
        print("[ERROR] psycopg not installed. Run with docker compose run --build --rm etl", file=sys.stderr)
        return 1

    missing = [str(RAW_DIR / f"bts_{YEAR}_{month:02d}.zip") for month in MONTHS
               if not (RAW_DIR / f"bts_{YEAR}_{month:02d}.zip").is_file()]
    if missing:
        print("[ERROR] ZIP files missing: " + ", ".join(missing), file=sys.stderr)
        print("[INFO] Run python scripts/download_bts.py on the host first", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "flightinsight"),
            user=os.environ.get("POSTGRES_USER", "flightinsight"),
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=15,
            autocommit=True,
        ) as conn:
            for month in MONTHS:
                path = RAW_DIR / f"bts_{YEAR}_{month:02d}.zip"
                import_one(conn, path, month)
    except Exception as exc:
        print(f"[FAILED] Import stopped: {type(exc).__name__}", file=sys.stderr)
        return 1

    print("\n[DONE] Three BTS archives processed. Check results with scripts/check_import.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
