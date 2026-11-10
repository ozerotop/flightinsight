"""Host-side read-only end-to-end check for the FlightInsight release.

Run after quick start: python scripts/check_release.py
Requires only the Python standard library.
"""

from __future__ import annotations

import json
import sys
from urllib.request import urlopen

API_BASE = "http://127.0.0.1:8000"
UI_BASE = "http://127.0.0.1:8501"


def get_json(path: str, timeout: int = 120):
    with urlopen(API_BASE + path, timeout=timeout) as response:
        if response.status != 200:
            raise AssertionError(f"{path}: HTTP {response.status}")
        return json.load(response)


def verify_summary(data: dict) -> None:
    expected = {"total_flights": 1_645_503, "delayed_15_flights": 317_266,
                "cancelled_flights": 30_640, "diverted_flights": 3_817,
                "arrival_sample": 1_611_046}
    for name, count in expected.items():
        if int(data.get(name, -1)) != count:
            raise AssertionError(f"{name}: expected {count}, got {data.get(name)!r}")


def main() -> int:
    try:
        health = get_json("/health", timeout=15)
        if health != {"status": "ok", "database": "ok"}:
            raise AssertionError(f"API/database not healthy: {health!r}")
        print("[OK] API and PostgreSQL")

        summary = get_json("/api/v1/summary")
        verify_summary(summary)
        print("[OK] 1,645,503 BTS flights and delay metrics")

        if len(get_json("/api/v1/analytics/trends")) != 90:
            raise AssertionError("Daily trends must contain 90 dates")
        if len(get_json("/api/v1/analytics/airlines?limit=10")) != 10:
            raise AssertionError("Airline ranking must have 10 records")
        print("[OK] SQL reports through REST API")

        spec = get_json("/openapi.json", timeout=15)
        if "/api/v1/summary" not in spec.get("paths", {}):
            raise AssertionError("OpenAPI specification is missing summary")
        print("[OK] Swagger/OpenAPI")

        with urlopen(UI_BASE + "/_stcore/health", timeout=15) as response:
            content = response.read().lower()
            if response.status != 200 or b"ok" not in content:
                raise AssertionError("Streamlit health endpoint failed")
        with urlopen(UI_BASE + "/", timeout=15) as response:
            if b"<html" not in response.read(4096).lower():
                raise AssertionError("Streamlit did not serve an HTML page")
        print("[OK] Streamlit health and HTML")
        print("[DONE] All release smoke checks passed")
        return 0
    except (OSError, ValueError, AssertionError, KeyError) as exc:
        print(f"[ERROR] Release smoke check failed: {exc}", file=sys.stderr)
        print("[HELP] docker compose ps; docker compose logs --tail=80 api dashboard", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
