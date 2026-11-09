-- FlightInsight Stage 5: cancellation codes, with denominators (all vs cancelled) explicitly separate
-- All filters are bound parameters, never SQL string interpolation.
WITH scoped AS (
    SELECT f.*, a.airline_code, a.airline_name,
           o.airport_code AS origin_code, o.city AS origin_city, o.state AS origin_state,
           d.airport_code AS destination_code, d.city AS destination_city, d.state AS destination_state
    FROM flights AS f
    JOIN airlines AS a ON a.airline_id = f.airline_id
    JOIN airports AS o ON o.airport_id = f.origin_airport_id
    JOIN airports AS d ON d.airport_id = f.destination_airport_id
    WHERE f.flight_date BETWEEN CAST(%(date_from)s AS date) AND CAST(%(date_to)s AS date)
      AND (CAST(%(airline_code)s AS text) IS NULL OR a.airline_code = CAST(%(airline_code)s AS text))
      AND (CAST(%(origin_code)s AS text) IS NULL OR o.airport_code = CAST(%(origin_code)s AS text))
      AND (CAST(%(destination_code)s AS text) IS NULL OR d.airport_code = CAST(%(destination_code)s AS text))
), totals AS (
    SELECT COUNT(*) AS all_flights,
           COUNT(*) FILTER (WHERE cancelled) AS cancelled_total
    FROM scoped
), grouped AS (
    SELECT COALESCE(NULLIF(cancellation_code, ''), 'UNKNOWN') AS cancellation_code,
           COUNT(*) AS cancelled_flights
    FROM scoped
    WHERE cancelled
    GROUP BY COALESCE(NULLIF(cancellation_code, ''), 'UNKNOWN')
)
SELECT g.cancellation_code, g.cancelled_flights,
       ROUND(100.0 * g.cancelled_flights / NULLIF(t.cancelled_total, 0), 2) AS share_of_cancellations_pct,
       ROUND(100.0 * g.cancelled_flights / NULLIF(t.all_flights, 0), 2) AS share_of_all_flights_pct,
       t.all_flights, t.cancelled_total
FROM grouped AS g CROSS JOIN totals AS t
ORDER BY g.cancelled_flights DESC, g.cancellation_code
