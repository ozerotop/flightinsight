"""Fast stdlib tests for analytic query contracts (no DB needed).

Actual SQL result correctness is verified in scripts/check_analytics.py against PostgreSQL.
"""
import unittest
from datetime import date
from pathlib import Path

from scripts.run_analytics import QUERIES, get_parameters, load_query, optional_code


class AnalyticsContractTests(unittest.TestCase):
    def test_sql_files_exist_for_all_known_reports(self):
        for name in QUERIES:
            with self.subTest(name=name):
                sql = load_query(name)
                self.assertIn("WITH scoped AS (", sql)
                self.assertIn("SELECT", sql)
                self.assertIn("%(date_from)s", sql)
                self.assertIn("%(date_to)s", sql)
                self.assertIn("%(airline_code)s", sql)
                self.assertIn("%(origin_code)s", sql)
                self.assertIn("%(destination_code)s", sql)
                self.assertNotIn("DROP TABLE", sql.upper())

    def test_min_sample_required_in_rankings(self):
        for name in ("airlines", "airports_departure", "airports_arrival"):
            with self.subTest(name=name):
                self.assertIn("%(min_sample_size)s", load_query(name))

    def test_parameter_defaults_and_normalization(self):
        params = get_parameters(airline_code=" aa ", origin_code="jfk")
        self.assertEqual(params["airline_code"], "AA")
        self.assertEqual(params["origin_code"], "JFK")
        self.assertEqual(params["date_from"], date(2025, 1, 1))
        self.assertEqual(params["date_to"], date(2025, 3, 31))
        self.assertEqual(params["min_sample_size"], 100)

    def test_reject_invalid_inputs(self):
        with self.assertRaises(ValueError):
            get_parameters(date_from=date(2025, 2, 2), date_to=date(2025, 2, 1))
        with self.assertRaises(ValueError):
            get_parameters(min_sample_size=-1)
        for code in ("A'A", "AA;DROP", "", "AA-01"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                optional_code(code, "airline")
        with self.assertRaises(ValueError):
            load_query("../../.env")

    def test_days_and_hours_are_local_and_rolling_weighted(self):
        self.assertIn("ISODOW", load_query("delays_weekday"))
        self.assertIn("scheduled_departure_hhmm = 2400", load_query("delays_hour"))
        rolling = load_query("trends_daily")
        self.assertIn("generate_series", rolling)
        self.assertIn("SUM(delayed_15_flights) OVER", rolling)
        self.assertIn("SUM(arrival_sample) OVER", rolling)


if __name__ == "__main__":
    unittest.main()
