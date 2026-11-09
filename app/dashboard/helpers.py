"""Pure dashboard formatting/export helpers, independent of Streamlit and Plotly."""

from __future__ import annotations

import csv
import io
import math
from typing import Any, Mapping, Sequence


def count_text(value: Any) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def percent_text(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f}%"


def minutes_text(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.2f} min"


def safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def export_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Export API records as UTF-8 CSV safe to open in spreadsheet software."""
    if not rows:
        return b""
    columns = list(dict.fromkeys(column for row in rows for column in row.keys()))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        sanitized: dict[str, Any] = {}
        for key in columns:
            value = row.get(key)
            if value is None:
                value = ""
            # The API has numbers as numbers. Treat *text* beginning with
            # spreadsheet formula characters as literal text on export.
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            sanitized[key] = value
        writer.writerow(sanitized)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def chart_pairs(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> tuple[list[Any], list[float | None]]:
    """Keep null percentages as gaps, rather than incorrectly converting to zero."""
    return ([row.get(x_field) for row in rows], [safe_number(row.get(y_field)) for row in rows])
