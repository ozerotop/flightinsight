-- FlightInsight Stage 5: global flight KPI summary; excluded cancelled and diverted from punctuality
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
), metrics AS (
    SELECT COUNT(*) AS total_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay IS NOT NULL) AS arrival_sample,
           COUNT(*) FILTER (WHERE cancelled) AS cancelled_flights,
           COUNT(*) FILTER (WHERE diverted) AS diverted_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS delayed_15_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay < 15) AS on_time_flights,
           AVG(arrival_delay) FILTER (WHERE NOT cancelled AND NOT diverted) AS avg_schedule_deviation,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY arrival_delay)
               FILTER (WHERE NOT cancelled AND NOT diverted) AS median_schedule_deviation,
           AVG(arrival_delay) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS avg_lateness_delayed,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY arrival_delay)
               FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS median_lateness_delayed
    FROM scoped
)
SELECT total_flights, arrival_sample, cancelled_flights, diverted_flights,
       delayed_15_flights, on_time_flights,
       ROUND(100.0 * delayed_15_flights / NULLIF(arrival_sample, 0), 2) AS delayed_15_pct,
       ROUND(100.0 * on_time_flights / NULLIF(arrival_sample, 0), 2) AS on_time_pct,
       ROUND(100.0 * cancelled_flights / NULLIF(total_flights, 0), 2) AS cancelled_pct,
       ROUND(100.0 * diverted_flights / NULLIF(total_flights, 0), 2) AS diverted_pct,
       ROUND(avg_schedule_deviation, 2) AS avg_schedule_deviation_min,
       ROUND(CAST(median_schedule_deviation AS numeric), 2) AS median_schedule_deviation_min,
       ROUND(avg_lateness_delayed, 2) AS avg_lateness_delayed_min,
       ROUND(CAST(median_lateness_delayed AS numeric), 2) AS median_lateness_delayed_min
FROM metrics
