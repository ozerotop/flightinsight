-- FlightInsight Stage 5: BTS delay-cause minutes reported for eligible late arrivals only
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
), delayed AS (
    SELECT carrier_delay, weather_delay, nas_delay, security_delay, late_aircraft_delay
    FROM scoped
    WHERE NOT cancelled AND NOT diverted AND arrival_delay >= 15
), totals AS (
    SELECT COUNT(*) AS delayed_flights,
           COUNT(*) FILTER (WHERE carrier_delay IS NOT NULL) AS carrier_reported,
           COUNT(*) FILTER (WHERE weather_delay IS NOT NULL) AS weather_reported,
           COUNT(*) FILTER (WHERE nas_delay IS NOT NULL) AS nas_reported,
           COUNT(*) FILTER (WHERE security_delay IS NOT NULL) AS security_reported,
           COUNT(*) FILTER (WHERE late_aircraft_delay IS NOT NULL) AS late_aircraft_reported,
           COALESCE(SUM(carrier_delay), 0) AS carrier_minutes,
           COALESCE(SUM(weather_delay), 0) AS weather_minutes,
           COALESCE(SUM(nas_delay), 0) AS nas_minutes,
           COALESCE(SUM(security_delay), 0) AS security_minutes,
           COALESCE(SUM(late_aircraft_delay), 0) AS late_aircraft_minutes
    FROM delayed
), reasons AS (
    SELECT 'carrier' AS reason, carrier_minutes AS total_minutes, carrier_reported AS reported_flights, delayed_flights FROM totals
    UNION ALL SELECT 'weather', weather_minutes, weather_reported, delayed_flights FROM totals
    UNION ALL SELECT 'nas', nas_minutes, nas_reported, delayed_flights FROM totals
    UNION ALL SELECT 'security', security_minutes, security_reported, delayed_flights FROM totals
    UNION ALL SELECT 'late_aircraft', late_aircraft_minutes, late_aircraft_reported, delayed_flights FROM totals
)
SELECT reason, total_minutes, reported_flights, delayed_flights,
       ROUND(100.0 * total_minutes / NULLIF(SUM(total_minutes) OVER (), 0), 2)
           AS share_of_reported_cause_minutes_pct
FROM reasons ORDER BY total_minutes DESC, reason
