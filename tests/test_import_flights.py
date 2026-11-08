"""Fast ETL parsing tests (stdlib only; don't need Docker or PostgreSQL)."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import io
import zipfile
from contextlib import contextmanager
from decimal import Decimal

from scripts.import_flights import (
    SOURCE_COLUMNS, STAGE_COLUMNS, city_name, hhmm,
    optional_decimal, parse_record, status_flag, load_csv_to_staging, Counters,
)


class TestBTSParsing(unittest.TestCase):
    def sample(self) -> dict[str, str]:
        row = {col: "" for col in SOURCE_COLUMNS}
        row.update({
            "FlightDate": "2025-01-01",
            "Reporting_Airline": "AA",
            "DOT_ID_Reporting_Airline": "19805",
            "Flight_Number_Reporting_Airline": "123",
            "Origin": "JFK", "OriginAirportID": "12478",
            "OriginCityName": "New York, NY", "OriginState": "NY",
            "Dest": "LAX", "DestAirportID": "12892",
            "DestCityName": "Los Angeles, CA", "DestState": "CA",
            "CRSDepTime": "2355", "DepTime": "2400",
            "CRSArrTime": "0300", "ArrTime": "0250",
            "DepDelay": "5.00", "ArrDelay": "-10.00",
            "Cancelled": "0.00", "Diverted": "0.00",
        })
        return row

    def test_regular_flight(self):
        row = parse_record(self.sample(), 1)
        self.assertEqual(len(row), len(STAGE_COLUMNS))
        self.assertEqual(row[0], date(2025, 1, 1))
        self.assertEqual(row[6], "New York")
        self.assertEqual(row[13], 2400)
        self.assertEqual(row[17], Decimal("-10.00"))
        self.assertFalse(row[18])

    def test_cancelled_flight_can_have_no_arrival_delay(self):
        source = self.sample()
        source["Cancelled"] = "1.00"
        source["ArrDelay"] = ""
        parsed = parse_record(source, 1)
        self.assertTrue(parsed[18])
        self.assertIsNone(parsed[17])

    def test_completed_missing_arrival_is_rejected(self):
        source = self.sample()
        source["ArrDelay"] = ""
        with self.assertRaises(ValueError):
            parse_record(source, 1)

    def test_wrong_month_rejected(self):
        with self.assertRaises(ValueError):
            parse_record(self.sample(), 2)

    def test_local_clock_2400_is_valid_and_2461_is_not(self):
        self.assertEqual(hhmm("2400", "CRSDepTime"), 2400)
        self.assertEqual(hhmm("0000", "CRSDepTime"), 0)
        for value in ("2461", "2360", "-1", "2500", "3.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hhmm(value, "CRSDepTime")

    def test_status_and_delay(self):
        self.assertTrue(status_flag("1.00", "Cancelled"))
        self.assertFalse(status_flag("0.00", "Cancelled"))
        with self.assertRaises(ValueError):
            status_flag("2.00", "Cancelled")
        self.assertEqual(optional_decimal("-12.00", "ArrDelay"), -12)
        self.assertIsNone(optional_decimal("", "CarrierDelay", cause=True))
        with self.assertRaises(ValueError):
            optional_decimal("-1", "CarrierDelay", cause=True)

    def test_city_without_state_suffix(self):
        self.assertEqual(city_name("New York, NY", "NY"), "New York")
        self.assertEqual(city_name("Unknown city", "NY"), "Unknown city")

    def test_stream_zip_csv_with_empty_final_column(self):
        class FakeCursor:
            def __init__(self):
                self.rows = []
                self.sql = None

            @contextmanager
            def copy(self, sql):
                self.sql = sql
                yield self

            def write_row(self, row):
                self.rows.append(row)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.zip"
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow([*SOURCE_COLUMNS, ""])
            record = self.sample()
            writer.writerow([*(record[name] for name in SOURCE_COLUMNS), ""])
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("synthetic.csv", output.getvalue())
            fake_cursor = FakeCursor()
            counters = Counters()
            load_csv_to_staging(fake_cursor, path, 1, counters)
            self.assertEqual((counters.processed, counters.accepted, counters.rejected), (1, 1, 0))
            self.assertEqual(len(fake_cursor.rows), 1)
            self.assertTrue(fake_cursor.sql.startswith("COPY stage_flights ("))


if __name__ == "__main__":
    unittest.main()
