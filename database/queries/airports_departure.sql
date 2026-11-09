-- FlightInsight Stage 5: origin airport punctuality; diverted departures retained when delay available
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
), grouped AS (
    SELECT origin_code AS airport_code, MAX(origin_city) AS city, MAX(origin_state) AS state,
           COUNT(*) AS scheduled_departures,
           COUNT(*) FILTER (WHERE cancelled) AS cancelled_departures,
           COUNT(*) FILTER (WHERE NOT cancelled AND departure_delay IS NOT NULL) AS departure_sample,
           COUNT(*) FILTER (WHERE NOT cancelled AND departure_delay >= 15) AS delayed_15_departures,
           AVG(departure_delay) FILTER (WHERE NOT cancelled) AS avg_departure_deviation
    FROM scoped
    GROUP BY origin_code
)
SELECT airport_code, city, state, scheduled_departures, cancelled_departures,
       departure_sample, delayed_15_departures,
       ROUND(100.0 * delayed_15_departures / NULLIF(departure_sample, 0), 2) AS delayed_15_pct,
       ROUND(100.0 * cancelled_departures / NULLIF(scheduled_departures, 0), 2) AS cancelled_pct,
       ROUND(avg_departure_deviation, 2) AS avg_departure_deviation_min
FROM grouped
WHERE departure_sample >= %(min_sample_size)s
ORDER BY delayed_15_pct ASC NULLS LAST, departure_sample DESC, airport_code
