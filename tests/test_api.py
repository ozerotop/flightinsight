"""FastAPI HTTP contract tests. Mock DB calls; no PostgreSQL required."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

SUMMARY_ROW = {
    "total_flights": 1_645_503,
    "arrival_sample": 1_611_046,
    "cancelled_flights": 30_640,
    "diverted_flights": 3817,
    "delayed_15_flights": 317266,
    "on_time_flights": 1293780,
    "delayed_15_pct": 19.69,
    "on_time_pct": 80.31,
    "cancelled_pct": 1.86,
    "diverted_pct": 0.23,
    "avg_schedule_deviation_min": 4.98,
    "median_schedule_deviation_min": -8.0,
    "avg_lateness_delayed_min": 71.65,
    "median_lateness_delayed_min": 41.0,
}


def test_swagger_documents_expected_paths():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    endpoints = response.json()["paths"]
    for path in (
        "/health", "/api/v1/summary", "/api/v1/airlines", "/api/v1/airports",
        "/api/v1/analytics/airlines", "/api/v1/analytics/airports",
        "/api/v1/analytics/delays", "/api/v1/analytics/cancellations",
        "/api/v1/analytics/trends", "/api/v1/analytics/delay-causes",
    ):
        assert path in endpoints
    assert client.get("/docs").status_code == 200


def test_summary_validates_and_normalizes_parameters():
    with patch("app.api.main._report", return_value=[SUMMARY_ROW]) as report:
        response = client.get(
            "/api/v1/summary",
            params={"airline": "aa", "origin": "jfk", "date_from": "2025-02-01", "date_to": "2025-02-28"},
        )
    assert response.status_code == 200
    assert response.json()["total_flights"] == 1_645_503
    assert isinstance(response.json()["delayed_15_pct"], float)
    name, params = report.call_args.args
    assert name == "summary"
    assert params["airline_code"] == "AA"
    assert params["origin_code"] == "JFK"
    assert params["date_from"].isoformat() == "2025-02-01"


@pytest.mark.parametrize("query", [
    "?date_from=2025-03-31&date_to=2025-01-01",
    "?date_from=wrong-date",
    "?airline=AA%27%3BDROP%20TABLE%20flights",
    "?min_sample_size=-1",
    "?origin=JFK%2F",
    "?date_from=2020-01-01&date_to=2025-03-31",
])
def test_invalid_filters_return_422_without_database_calls(query):
    with patch("app.api.main._report") as report:
        response = client.get("/api/v1/summary" + query)
    assert response.status_code == 422
    report.assert_not_called()


def test_airport_and_delay_dispatch():
    with patch("app.api.main._report", return_value=[]) as report:
        response = client.get("/api/v1/analytics/airports?direction=departure&limit=5")
        assert response.status_code == 200
        assert response.json() == []
        assert report.call_args.args[0] == "airports_departure"
        response = client.get("/api/v1/analytics/delays?group_by=hour")
        assert response.status_code == 200
        assert report.call_args.args[0] == "delays_hour"


def test_reject_invalid_direction_and_limit():
    with patch("app.api.main._report") as report:
        assert client.get("/api/v1/analytics/airports?direction=other").status_code == 422
        assert client.get("/api/v1/analytics/airlines?limit=0").status_code == 422
    report.assert_not_called()


def test_airline_reference_list():
    with patch("app.api.main._lookup", return_value=[{"airline_code": "AA", "airline_name": "AA"}]):
        response = client.get("/api/v1/airlines")
    assert response.status_code == 200
    assert response.json() == [{"airline_code": "AA", "airline_name": "AA"}]


def test_health_success_and_failure():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
    with patch("app.api.main.open_connection", return_value=connection):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    with patch("app.api.main.open_connection", side_effect=OSError("offline")):
        response = client.get("/health")
    assert response.status_code == 503
    assert "offline" not in response.text


def test_summary_unavailable_database_sanitized():
    with patch("app.api.main.open_connection", side_effect=OSError("private password")):
        response = client.get("/api/v1/summary")
    assert response.status_code == 503
    assert "private password" not in response.text
