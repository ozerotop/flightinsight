"""Unit tests for Stage 7 helpers, no Streamlit install or database required."""

import csv
import io
import json
import unittest
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app.dashboard.client import FlightInsightAPIError, fetch_json, prepare_params
from app.dashboard.helpers import chart_pairs, count_text, export_csv, minutes_text, percent_text, safe_number


class DashboardHelperTests(unittest.TestCase):
    def test_metric_rendering_and_missing_values(self):
        self.assertEqual(count_text(1645503), "1 645 503")
        self.assertEqual(count_text(None), "—")
        self.assertEqual(percent_text(19.689), "19.69%")
        self.assertEqual(percent_text(None), "—")
        self.assertEqual(minutes_text(-8), "-8.00 min")
        self.assertEqual(minutes_text(4.98), "+4.98 min")

    def test_numeric_gaps_remain_null_not_zero(self):
        self.assertIsNone(safe_number(None))
        self.assertIsNone(safe_number("NaN"))
        self.assertIsNone(safe_number("inf"))
        self.assertEqual(chart_pairs([
            {"day": "2025-01-01", "pct": None},
            {"day": "2025-01-02", "pct": 0},
            {"day": "2025-01-03", "pct": 12.5},
        ], "day", "pct"), (["2025-01-01", "2025-01-02", "2025-01-03"], [None, 0.0, 12.5]))

    def test_csv_export_preserves_data_and_prevents_formula_injection(self):
        records = [{"code": "AA", "name": "=SUM(1+1)", "delay": -8, "maybe": None},
                   {"code": "BB", "name": "Another airline", "delay": 0, "maybe": 4}]
        result = export_csv(records)
        self.assertTrue(result.startswith(b"\xef\xbb\xbf"))
        parsed = list(csv.DictReader(io.StringIO(result.decode("utf-8-sig"))))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["name"], "'=SUM(1+1)")
        self.assertEqual(parsed[0]["delay"], "-8")
        self.assertEqual(parsed[0]["maybe"], "")
        self.assertEqual(parsed[1]["name"], "Another airline")
        self.assertEqual(export_csv([]), b"")

    def test_parameters_drop_empty_and_serialize_date(self):
        self.assertEqual(prepare_params({"date_from": date(2025, 1, 1),
                                         "airline": None, "origin": "", "min_sample_size": 0}),
                         {"date_from": "2025-01-01", "min_sample_size": "0"})

    def test_path_validation(self):
        for path in ("http://evil", "//evil", "/etc/passwd", "/api/v1/summary?evil=1"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fetch_json("http://api:8000", path)

    def test_api_get_encodes_filters_and_parses_json(self):
        class Response:
            def __enter__(self):
                return io.BytesIO(json.dumps({"total_flights": 1645503}).encode())

            def __exit__(self, *_args):
                return False

        with patch("app.dashboard.client.urlopen", return_value=Response()) as mocked:
            data = fetch_json("http://api:8000/", "/api/v1/summary",
                              {"date_from": date(2025, 1, 1), "airline": "AA", "origin": None})
        self.assertEqual(data["total_flights"], 1645503)
        requested = mocked.call_args.args[0]
        self.assertEqual(requested.full_url, "http://api:8000/api/v1/summary?date_from=2025-01-01&airline=AA")
        self.assertEqual(requested.get_header("Accept"), "application/json")

    def test_http_and_network_errors_are_user_friendly(self):
        with patch("app.dashboard.client.urlopen", side_effect=HTTPError("http://api", 503, "service", {}, None)):
            with self.assertRaisesRegex(FlightInsightAPIError, "HTTP 503"):
                fetch_json("http://api:8000", "/health")
        with patch("app.dashboard.client.urlopen", side_effect=URLError("connection refused")):
            with self.assertRaisesRegex(FlightInsightAPIError, "Cannot reach"):
                fetch_json("http://api:8000", "/health")


if __name__ == "__main__":
    unittest.main()
