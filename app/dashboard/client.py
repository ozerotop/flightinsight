"""Small standard-library HTTP client for FlightInsight's read-only REST API.

The dashboard must never connect to PostgreSQL directly. Parameter values are
encoded as HTTP query parameters, not concatenated into SQL or URLs manually.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class FlightInsightAPIError(RuntimeError):
    """A recoverable API or network failure suitable for displaying to a user."""


def prepare_params(values: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Drop empty optional filters and serialize dates to ISO format."""
    result: dict[str, str] = {}
    for key, value in (values or {}).items():
        if value is None or value == "":
            continue
        if isinstance(value, date):
            result[key] = value.isoformat()
        else:
            result[key] = str(value)
    return result


def fetch_json(
    base_url: str, path: str, params: Mapping[str, Any] | None = None, timeout: int = 90
) -> Any:
    """Fetch JSON from a known relative API path; surface safe, concise errors."""
    if not (path == "/health" or path.startswith("/api/v1/")) or "?" in path or "#" in path:
        raise ValueError("API path must be a known relative FlightInsight endpoint")
    endpoint = base_url.rstrip("/") + path
    query = prepare_params(params)
    if query:
        endpoint += "?" + urlencode(query)
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        raise FlightInsightAPIError(f"API returned HTTP {exc.code} for {path}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise FlightInsightAPIError(f"Cannot reach FlightInsight API ({path})") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise FlightInsightAPIError(f"Invalid JSON returned by the API ({path})") from exc
