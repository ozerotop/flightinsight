"""Read-only integration smoke test for a running FlightInsight API.

Run inside api container: python scripts/check_api.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=90) as response:
        assert response.status == 200, (path, response.status)
        return json.load(response)


def main():
    h = get("/health")
    assert h == {"status": "ok", "database": "ok"}, h
    print("[OK] /health")
    summary = get("/api/v1/summary")
    assert summary["total_flights"] == 1_645_503, summary
    assert summary["delayed_15_flights"] == 317_266, summary
    assert abs(summary["delayed_15_pct"] - 19.69) < 0.02, summary
    print("[OK] /api/v1/summary: 1,645,503 flights, 317,266 late")
    airlines = get("/api/v1/analytics/airlines?limit=10")
    assert len(airlines) == 10 and airlines[0]["airline_code"], airlines
    print("[OK] /api/v1/analytics/airlines: 10 rows")
    trend = get("/api/v1/analytics/trends")
    assert len(trend) == 90, len(trend)
    print("[OK] /api/v1/analytics/trends: 90 days")
    airport = get("/api/v1/airports")
    assert len(airport) >= 1, airport
    print("[OK] /api/v1/airports")
    print("[DONE] FlightInsight API smoke checks passed")


if __name__ == "__main__":
    main()
