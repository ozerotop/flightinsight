-- FlightInsight Stage 5: daily trend incl zero-volume days; 7-calendar-day weighted rate
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
    SELECT flight_date,
           COUNT(*) AS total_flights,
           COUNT(*) FILTER (WHERE cancelled) AS cancelled_flights,
           COUNT(*) FILTER (WHERE diverted) AS diverted_flights,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay IS NOT NULL) AS arrival_sample,
           COUNT(*) FILTER (WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15) AS delayed_15_flights
    FROM scoped GROUP BY flight_date
), calendar AS (
    SELECT generate_series(CAST(%(date_from)s AS timestamp), CAST(%(date_to)s AS timestamp), INTERVAL '1 day')::date AS flight_date
), daily AS (
    SELECT c.flight_date,
           COALESCE(g.total_flights, 0) AS total_flights,
           COALESCE(g.cancelled_flights, 0) AS cancelled_flights,
           COALESCE(g.diverted_flights, 0) AS diverted_flights,
           COALESCE(g.arrival_sample, 0) AS arrival_sample,
           COALESCE(g.delayed_15_flights, 0) AS delayed_15_flights
    FROM calendar AS c LEFT JOIN grouped AS g USING (flight_date)
), rolling AS (
    SELECT *,
           SUM(delayed_15_flights) OVER (ORDER BY flight_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS delayed_7d,
           SUM(arrival_sample) OVER (ORDER BY flight_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS sample_7d
    FROM daily
)
SELECT flight_date, total_flights, cancelled_flights, diverted_flights,
       arrival_sample, delayed_15_flights,
       ROUND(100.0 * delayed_15_flights / NULLIF(arrival_sample, 0), 2) AS delayed_15_pct,
       ROUND(100.0 * delayed_7d / NULLIF(sample_7d, 0), 2) AS delayed_7d_pct
FROM rolling ORDER BY flight_date
