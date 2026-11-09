"""Integration checks using the *real* BTS 2025 Q1 PostgreSQL dataset.

Run: docker compose run --build --rm analytics python scripts/check_analytics.py
Does not alter rows or schema. Prints verification results and returns nonzero on failure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from run_analytics import execute_query, get_parameters, open_connection

EXPECTED_TOTAL = 1_645_503
EXPECTED_CANCELLED = 30_640
EXPECTED_DIVERTED = 3_817
EXPECTED_COMPLETED = 1_611_046
EXPECTED_DELAYED = 317_266


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}", flush=True)


def main() -> int:
    params = get_parameters(min_sample_size=0)
    with open_connection() as conn:
        s = execute_query(conn, "summary", params)[0]
        print("[INFO] Summary:", {k: s[k] for k in (
            "total_flights", "arrival_sample", "cancelled_flights",
            "diverted_flights", "delayed_15_flights", "delayed_15_pct",
        )}, flush=True)
        check(s["total_flights"] == EXPECTED_TOTAL, "Total flights match source 2025 Q1")
        check(s["cancelled_flights"] == EXPECTED_CANCELLED, "Cancellations match source")
        check(s["diverted_flights"] == EXPECTED_DIVERTED, "Diversions match source")
        check(s["arrival_sample"] == EXPECTED_COMPLETED, "Punctuality denominator excludes cancelled/diverted")
        check(s["delayed_15_flights"] == EXPECTED_DELAYED, "Flights delayed >=15m match source")
        check(s["on_time_flights"] + s["delayed_15_flights"] == s["arrival_sample"], "On-time and delayed partition eligible arrivals")
        check(abs(s["delayed_15_pct"] - Decimal("19.69")) <= Decimal("0.01"), "Delay rate is about 19.69%")

        airlines = execute_query(conn, "airlines", params)
        check(sum(row["total_flights"] for row in airlines) == EXPECTED_TOTAL, "Airline totals reconcile")
        check(sum(row["arrival_sample"] for row in airlines) == EXPECTED_COMPLETED, "Airline denominators reconcile")
        check(sum(row["delayed_15_flights"] for row in airlines) == EXPECTED_DELAYED, "Airline delays reconcile")

        origins = execute_query(conn, "airports_departure", params)
        dests = execute_query(conn, "airports_arrival", params)
        check(sum(row["scheduled_departures"] for row in origins) == EXPECTED_TOTAL, "Origin airport totals reconcile")
        check(sum(row["scheduled_arrivals"] for row in dests) == EXPECTED_TOTAL, "Destination airport totals reconcile")
        check(sum(row["delayed_15_arrivals"] for row in dests) == EXPECTED_DELAYED, "Destination arrival delays reconcile")

        weekday = execute_query(conn, "delays_weekday", params)
        hour = execute_query(conn, "delays_hour", params)
        check(sum(row["total_flights"] for row in weekday) == EXPECTED_TOTAL, "Weekday totals reconcile")
        check(sum(row["total_flights"] for row in hour) == EXPECTED_TOTAL, "Departure-hour totals reconcile")
        check(all(0 <= row["origin_local_departure_hour"] <= 23 for row in hour), "Scheduled HHMM hours normalized to 0..23")

        cancellations = execute_query(conn, "cancellations", params)
        check(sum(row["cancelled_flights"] for row in cancellations) == EXPECTED_CANCELLED, "Cancellation reasons reconcile")

        causes = execute_query(conn, "delay_causes", params)
        check(len(causes) == 5 and all(row["total_minutes"] >= 0 for row in causes), "Five nonnegative delay-cause aggregates")
        check(all(row["delayed_flights"] == EXPECTED_DELAYED for row in causes), "Delay causes cover the same late-arrival cohort")

        trends = execute_query(conn, "trends_daily", params)
        check(len(trends) == 90, "Daily trend has every calendar day Jan-Mar 2025")
        check(trends[0]["flight_date"] == date(2025, 1, 1) and trends[-1]["flight_date"] == date(2025, 3, 31), "Daily trend date bounds match")
        check(sum(row["total_flights"] for row in trends) == EXPECTED_TOTAL, "Daily totals reconcile")
        check(sum(row["delayed_15_flights"] for row in trends) == EXPECTED_DELAYED, "Daily late arrivals reconcile")

        # Test a genuinely filtered cohort and conservation across two query types.
        filtered = get_parameters(airline_code="AA", date_from=date(2025, 2, 1), date_to=date(2025, 2, 28), min_sample_size=0)
        subset = execute_query(conn, "summary", filtered)[0]
        by_day = execute_query(conn, "trends_daily", filtered)
        check(sum(row["total_flights"] for row in by_day) == subset["total_flights"], "Filtered AA February totals reconcile")
        check(sum(row["delayed_15_flights"] for row in by_day) == subset["delayed_15_flights"], "Filtered AA February delays reconcile")

    print("\n[DONE] SQL analytics integration checks passed. No rows or schema were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
