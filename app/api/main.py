"""FastAPI service over the already-tested Stage 5 PostgreSQL queries.

No schema changes and no write endpoints. Run with Docker Compose API service.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query

from scripts.run_analytics import execute_query, get_parameters, open_connection
from app.api.schemas import (
    Airline, AirlineAnalytics, Airport, AirportAnalytics, CancellationAnalytics,
    DelayAnalytics, DelayCauseAnalytics, HealthResponse, Summary, Trend,
)

logger = logging.getLogger("flightinsight.api")

app = FastAPI(
    title="FlightInsight API",
    version="1.0.0",
    description=(
        "Read-only analytics for 2025 Q1 BTS U.S. domestic flights. "
        "Arrival delays of 15+ minutes count as delayed; cancelled and diverted "
        "flights are excluded from arrival punctuality denominators."
    ),
    docs_url="/docs",
    redoc_url=None,
)


# All query strings are fixed SQL stored in database/queries, never built from user input.
def _report(name: str, params: dict) -> list[dict]:
    try:
        with open_connection() as connection:
            return execute_query(connection, name, params)
    except Exception as exc:
        logger.exception("Database analytics request failed: %s", name)
        raise HTTPException(status_code=503, detail="Analytics database unavailable") from exc


def _lookup(name: Literal["airlines", "airports"]) -> list[dict]:
    statements = {
        "airlines": """SELECT airline_code, COALESCE(airline_name, airline_code) AS airline_name
                       FROM airlines ORDER BY airline_code""",
        "airports": """SELECT airport_code, airport_name, city, state
                       FROM airports ORDER BY airport_code""",
    }
    try:
        from psycopg.rows import dict_row
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statements[name])
                return list(cursor.fetchall())
    except Exception as exc:
        logger.exception("Database reference lookup failed: %s", name)
        raise HTTPException(status_code=503, detail="Analytics database unavailable") from exc


def filters(
    date_from: date = Query(date(2025, 1, 1), description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date = Query(date(2025, 3, 31), description="Inclusive end date (YYYY-MM-DD)"),
    airline: str | None = Query(None, description="BTS airline code, e.g. AA"),
    origin: str | None = Query(None, description="Departure airport code, e.g. JFK"),
    destination: str | None = Query(None, description="Arrival airport code, e.g. LAX"),
    min_sample_size: int = Query(100, ge=0, le=1_000_000, description="Minimum valid sample in ranking reports"),
) -> dict:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    if (date_to - date_from).days > 365:
        raise HTTPException(status_code=422, detail="Date range must be at most 366 days")
    try:
        return get_parameters(
            date_from=date_from, date_to=date_to,
            airline_code=airline, origin_code=origin,
            destination_code=destination, min_sample_size=min_sample_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


FilterParams = Annotated[dict, Depends(filters)]


@app.get("/health", response_model=HealthResponse, tags=["System"], summary="Check API and database readiness")
def health() -> HealthResponse:
    try:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Analytics database unavailable") from exc
    return HealthResponse(status="ok", database="ok")


@app.get("/api/v1/summary", response_model=Summary, tags=["Analytics"], summary="Global punctuality and delay metrics")
def summary(params: FilterParams) -> dict:
    return _report("summary", params)[0]


@app.get("/api/v1/airlines", response_model=list[Airline], tags=["Reference"], summary="All available airlines")
def airlines() -> list[dict]:
    return _lookup("airlines")


@app.get("/api/v1/airports", response_model=list[Airport], tags=["Reference"], summary="All available airports")
def airports() -> list[dict]:
    return _lookup("airports")


@app.get("/api/v1/analytics/airlines", response_model=list[AirlineAnalytics], tags=["Analytics"], summary="Rank airlines by arrival delay rate")
def analytics_airlines(params: FilterParams, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return _report("airlines", params)[:limit]


@app.get("/api/v1/analytics/airports", response_model=list[AirportAnalytics], tags=["Analytics"], summary="Rank departure or arrival airports")
def analytics_airports(
    params: FilterParams,
    direction: Literal["arrival", "departure"] = "arrival",
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    report = "airports_arrival" if direction == "arrival" else "airports_departure"
    return _report(report, params)[:limit]


@app.get("/api/v1/analytics/delays", response_model=list[DelayAnalytics], tags=["Analytics"], summary="Delay rates by weekday or local departure hour")
def analytics_delays(params: FilterParams, group_by: Literal["weekday", "hour"] = "weekday") -> list[dict]:
    return _report("delays_weekday" if group_by == "weekday" else "delays_hour", params)


@app.get("/api/v1/analytics/cancellations", response_model=list[CancellationAnalytics], tags=["Analytics"], summary="Flight cancellations by BTS reason code")
def analytics_cancellations(params: FilterParams) -> list[dict]:
    return _report("cancellations", params)


@app.get("/api/v1/analytics/trends", response_model=list[Trend], tags=["Analytics"], summary="Daily trend and weighted seven-day late-arrival rate")
def analytics_trends(params: FilterParams) -> list[dict]:
    return _report("trends_daily", params)


@app.get("/api/v1/analytics/delay-causes", response_model=list[DelayCauseAnalytics], tags=["Analytics"], summary="Delay-cause minutes for flights arriving 15+ minutes late")
def analytics_delay_causes(params: FilterParams) -> list[dict]:
    return _report("delay_causes", params)
