"""Explicit response schemas for the public FlightInsight v1 API.

Numerical rates/delays are JSON numbers or null; counts remain integers.
"""

from datetime import date
from pydantic import BaseModel, ConfigDict


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponse):
    status: str
    database: str


class Airline(StrictResponse):
    airline_code: str
    airline_name: str | None = None


class Airport(StrictResponse):
    airport_code: str
    airport_name: str | None = None
    city: str | None = None
    state: str | None = None


class Summary(StrictResponse):
    total_flights: int
    arrival_sample: int
    cancelled_flights: int
    diverted_flights: int
    delayed_15_flights: int
    on_time_flights: int
    delayed_15_pct: float | None = None
    on_time_pct: float | None = None
    cancelled_pct: float | None = None
    diverted_pct: float | None = None
    avg_schedule_deviation_min: float | None = None
    median_schedule_deviation_min: float | None = None
    avg_lateness_delayed_min: float | None = None
    median_lateness_delayed_min: float | None = None


class AirlineAnalytics(StrictResponse):
    airline_code: str
    airline_name: str
    total_flights: int
    cancelled_flights: int
    diverted_flights: int
    arrival_sample: int
    delayed_15_flights: int
    delayed_15_pct: float | None = None
    cancelled_pct: float | None = None
    avg_schedule_deviation_min: float | None = None


class AirportAnalytics(StrictResponse):
    airport_code: str
    city: str | None = None
    state: str | None = None
    scheduled_arrivals: int | None = None
    scheduled_departures: int | None = None
    cancelled_flights: int | None = None
    cancelled_departures: int | None = None
    diverted_flights: int | None = None
    arrival_sample: int | None = None
    departure_sample: int | None = None
    delayed_15_arrivals: int | None = None
    delayed_15_departures: int | None = None
    delayed_15_pct: float | None = None
    cancelled_pct: float | None = None
    avg_arrival_deviation_min: float | None = None
    avg_departure_deviation_min: float | None = None


class DelayAnalytics(StrictResponse):
    weekday_iso: int | None = None
    origin_local_departure_hour: int | None = None
    total_flights: int
    arrival_sample: int
    delayed_15_flights: int
    delayed_15_pct: float | None = None
    avg_schedule_deviation_min: float | None = None


class CancellationAnalytics(StrictResponse):
    cancellation_code: str
    cancelled_flights: int
    share_of_cancellations_pct: float | None = None
    share_of_all_flights_pct: float | None = None
    all_flights: int
    cancelled_total: int


class DelayCauseAnalytics(StrictResponse):
    reason: str
    total_minutes: float
    reported_flights: int
    delayed_flights: int
    share_of_reported_cause_minutes_pct: float | None = None


class Trend(StrictResponse):
    flight_date: date
    total_flights: int
    cancelled_flights: int
    diverted_flights: int
    arrival_sample: int
    delayed_15_flights: int
    delayed_15_pct: float | None = None
    delayed_7d_pct: float | None = None
