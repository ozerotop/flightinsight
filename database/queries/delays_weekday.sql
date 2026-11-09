-- FlightInsight Stage 5: Monday=1, Sunday=7; flight date is source local date
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
    SELECT EXTRACT(ISODOW FROM flight_date)::int AS weekday_iso,
           COUNT(*) AS total_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay IS NOT NULL) AS arrival_sample,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS delayed_15_flights,
           AVG(arrival_delay) FILTER (WHERE NOT cancelled AND NOT diverted) AS avg_schedule_deviation
    FROM scoped
    GROUP BY EXTRACT(ISODOW FROM flight_date)::int
)
SELECT weekday_iso, total_flights, arrival_sample, delayed_15_flights,
       ROUND(100.0 * delayed_15_flights / NULLIF(arrival_sample, 0), 2) AS delayed_15_pct,
       ROUND(avg_schedule_deviation, 2) AS avg_schedule_deviation_min
FROM grouped ORDER BY weekday_iso
