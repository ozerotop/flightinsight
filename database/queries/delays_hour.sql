-- FlightInsight Stage 5: hour of scheduled departure at origin local time, 2400 => hour 0
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
), hourly AS (
    SELECT CASE WHEN scheduled_departure_hhmm = 2400 THEN 0
                ELSE scheduled_departure_hhmm / 100 END AS origin_local_departure_hour,
           cancelled, diverted, arrival_delay
    FROM scoped
), grouped AS (
    SELECT origin_local_departure_hour,
           COUNT(*) AS total_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay IS NOT NULL) AS arrival_sample,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS delayed_15_flights,
           AVG(arrival_delay) FILTER (WHERE NOT cancelled AND NOT diverted) AS avg_schedule_deviation
    FROM hourly GROUP BY origin_local_departure_hour
)
SELECT origin_local_departure_hour, total_flights, arrival_sample, delayed_15_flights,
       ROUND(100.0 * delayed_15_flights / NULLIF(arrival_sample, 0), 2) AS delayed_15_pct,
       ROUND(avg_schedule_deviation, 2) AS avg_schedule_deviation_min
FROM grouped ORDER BY origin_local_departure_hour
