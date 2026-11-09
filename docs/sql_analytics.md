# FlightInsight — SQL analytics (Stage 5)

## Data and definitions

Queries read the normalized PostgreSQL tables populated from official BTS domestic on-time performance ZIP files for January–March 2025. Every query accepts the same **parameterized**, inclusive date range and optional reporting airline, origin and destination airport codes. SQL files are in `database/queries/` and do not modify the database.

**Arrival punctuality** uses only rows with `cancelled = false`, `diverted = false` and non-NULL `arrival_delay`. This denominator is called `arrival_sample`; it differs from the count of all scheduled flights. A delayed arrival is `arrival_delay >= 15` minutes; an on-time arrival is `arrival_delay < 15`, **including early arrivals**. Cancellations and diversions are counted separately among **all** scheduled records.

Formulas:

| Metric | Calculation |
|---|---|
| Arrival delay rate | `100 * delayed_15_flights / arrival_sample` |
| On-time arrival rate | `100 * on_time_flights / arrival_sample` |
| Cancellation rate | `100 * cancelled_flights / total_flights` |
| Diversion rate | `100 * diverted_flights / total_flights` |
| Mean schedule deviation | arithmetic average of `arrival_delay` across `arrival_sample`; negative values reflect early arrivals |
| Median schedule deviation | PostgreSQL `percentile_cont(0.5)` of `arrival_delay` across `arrival_sample` |
| Mean/median late-arrival duration | average/median `arrival_delay` across the delayed 15+ minute cohort only |

Percentages use `NULLIF(denominator,0)` and return SQL `NULL` for empty or inapplicable samples. They are rounded to 2 decimals **only after** aggregation; raw counts are not rounded.

## Available reports

| Query file | Purpose |
|---|---|
| `summary.sql` | Total flights, sample sizes, cancellations, diversions, punctuality, average and median delays |
| `airlines.sql` | Airline arrival punctuality ranking; shows both total and eligible arrivals |
| `airports_departure.sql` | Departure-airport punctuality; includes diverted flights if they have a reported departure delay |
| `airports_arrival.sql` | Destination-airport arrival punctuality; excludes cancelled/diverted flights |
| `delays_weekday.sql` | Arrival delays grouped by ISO weekday (Monday 1 – Sunday 7) |
| `delays_hour.sql` | Arrival delays by **scheduled departure hour in origin-local time**, not UTC; `2400` mapped to hour 0 |
| `cancellations.sql` | Cancelled flights grouped by BTS cancellation code; percentages use separate denominators |
| `delay_causes.sql` | Five BTS delay-cause minute sums among delayed arrivals with reported causes |
| `trends_daily.sql` | Daily totals, daily arrival delay share, and a **weighted** 7-calendar-day rolling rate |

A rolling seven-day rate divides the **sum of late arrivals over the window** by the **sum of eligible arrivals**, not the mean of seven daily percentages. `generate_series` includes dates with zero flights in a filtered subset; a day with no eligible arrivals has a NULL daily delay percentage.

### Delay causes

BTS delay causes are five separate duration columns: carrier, weather, NAS, security and late aircraft. The query sums **reported cause minutes**, treats NULL as *missing from the sum* rather than silently asserting a zero delay, and exposes `reported_flights` for each category and `delayed_flights` for the analyzed cohort. Shares are based on reported **cause minutes**, not percentages of flights. A single flight may have several positive causes. Reporting presence is not the same thing as the cause being positive.

### Minimum sample size

Airline and airport rankings default to a minimum of **100 eligible flights**, configurable using `--min-sample-size`. This avoids interpreting rankings based on a handful of observations as equally reliable. Use `--min-sample-size 0` to see all groups and reconcile sums to total flights.

### Source limitations

Airline names are not filled in by the ETL at this stage: the UI may display BTS reporting carrier codes until a verified name lookup is added. No forecasts or causal claims are made; these are descriptive historical statistics. Scheduled HHMM is **local clock time**, not a timezone-aware timestamp.

## Running on Windows CMD

Run after the completed ETL stage. Docker Desktop must be running.

```bat
docker compose run --build --rm analytics python scripts/check_analytics.py
docker compose run --rm analytics python scripts/run_analytics.py summary
docker compose run --rm analytics python scripts/run_analytics.py airlines --min-sample-size 500 --limit 10
docker compose run --rm analytics python scripts/run_analytics.py trends_daily --date-from 2025-02-01 --date-to 2025-02-28 --airline AA --limit 10
docker compose run --rm analytics python scripts/run_analytics.py all --limit 3
```

All report values are retrieved directly from PostgreSQL. JSON numbers that originate from exact PostgreSQL `numeric` values are printed as strings to preserve decimal precision.

### Investigating performance

```bat
docker compose run --rm analytics python scripts/run_analytics.py summary --explain
docker compose run --rm analytics python scripts/run_analytics.py airlines --explain
```

`EXPLAIN (ANALYZE, BUFFERS)` **actually executes** the SELECT to measure runtime. Inspect the `Execution Time`, scan operators and buffer activity. These queries are intentionally read-only. Existing database indexes come from `database/schema.sql`; add any further indexes **only when a measured query justifies them**. Do not assume the planner must use an index for a report scanning nearly the entire dataset.

## Checks and scope

- Host-only query-contract tests: `python -m unittest discover -s tests -p "test_analytics.py" -v`.
- Real-database integration checks: `docker compose run --build --rm analytics python scripts/check_analytics.py`.
- Expected Q1 cohort: **1,645,503** total; **1,611,046** regularly completed eligible arrivals; **30,640** cancelled; **3,817** diverted; **317,266** arrivals late by 15+ minutes.
- Integration tests cross-check grouped airline/airport/day totals and a filtered AA/February cohort. They **do not replace** a full independent review of every aggregation or a performance benchmark.

These reports are the SQL foundation for the REST API that will be added in Stage 6.
