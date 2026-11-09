"""Host-side smoke test for the local Streamlit UI and existing FastAPI service."""

from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def get(url: str, timeout: int = 25) -> tuple[int, bytes]:
    with urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def main() -> int:
    try:
        _, health_data = get("http://127.0.0.1:8000/health")
        health = json.loads(health_data)
        assert health.get("status") == "ok" and health.get("database") == "ok"
        print("[OK] FastAPI + PostgreSQL ready")

        _, summary_data = get("http://127.0.0.1:8000/api/v1/summary", timeout=120)
        summary = json.loads(summary_data)
        flights = int(summary.get("total_flights", -1))
        assert flights == 1_645_503, f"Unexpected flight count: {flights}"
        print(f"[OK] API summary: {flights:,} flights")

        _, ui_health = get("http://127.0.0.1:8501/_stcore/health")
        assert b"ok" in ui_health.lower(), f"Unexpected dashboard status: {ui_health[:80]!r}"
        print("[OK] Streamlit server healthy on port 8501")

        _, page = get("http://127.0.0.1:8501/")
        assert b"<html" in page.lower(), "Streamlit did not serve an HTML page"
        print("[OK] Dashboard HTML responds at http://localhost:8501/")
        print("[DONE] Dashboard HTTP smoke checks passed. Open it in your browser to validate charts.")
        return 0
    except (OSError, URLError, HTTPError, ValueError, AssertionError) as exc:
        print(f"[ERROR] Dashboard smoke check failed: {exc}", file=sys.stderr)
        print("[HELP] Check `docker compose ps` and `docker compose logs --tail=80 dashboard`.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
