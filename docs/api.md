# FlightInsight REST API (stage 6)

FastAPI exposes read-only BTS analytics. The API is available at
`http://localhost:8000`; interactive OpenAPI documentation at
`http://localhost:8000/docs`.

## Startup

Start PostgreSQL after loading the BTS dataset (see the main README):

```bat
docker compose up -d --build api
```

The API uses a Docker-internal database hostname (`postgres`) and does not
require local psycopg or FastAPI installations. It does not modify database rows.

## Endpoints

| Path | Purpose |
|---|---|
| `GET /health` | API + PostgreSQL readiness; 503 if database is unavailable |
| `GET /api/v1/summary` | Main KPI metrics (returns one object) |
| `GET /api/v1/airlines` | Airline code and display name lookup |
| `GET /api/v1/airports` | Airport code/city/state lookup |
| `GET /api/v1/analytics/airlines` | Ranked airline punctuality |
| `GET /api/v1/analytics/airports` | Airport ranking (`direction=arrival` or `departure`) |
| `GET /api/v1/analytics/delays` | Delays grouped by `group_by=weekday` or `hour` |
| `GET /api/v1/analytics/cancellations` | Cancellation reason codes and rates |
| `GET /api/v1/analytics/trends` | Daily counts and weighted 7-day delay rate |
| `GET /api/v1/analytics/delay-causes` | BTS delay-cause minutes |

Query parameters for analytics: `date_from`, `date_to` (inclusive, ISO date),
`airline`, `origin`, `destination` and `min_sample_size` (minimum sample for
ranked reports). Default dates cover `2025-01-01` through `2025-03-31`.
The accepted date interval is at most 366 days. Airlines/airports accept
2–10 ASCII letters or digits; codes are normalized to uppercase.
The `limit` parameter for airline/airport rankings accepts 1–500, default 100.

Invalid parameters produce HTTP **422**. Database failures produce HTTP **503**
with a generic error message; connection credentials are never returned.
Empty list reports return `[]`, and empty summary date ranges return zero
counts with null percentage/average values. Metrics use documented denominators
(see [`sql_analytics.md`](sql_analytics.md)).

The API returns numbers as JSON numbers and missing statistics as JSON `null`.
No data write endpoints or authentication are included in the local MVP.
Do not expose the localhost development API publicly without appropriate security.

## Quick checks

```bat
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/summary
curl "http://localhost:8000/api/v1/analytics/airports?direction=arrival&limit=5"
```

Unit tests (inside the API image):

```bat
docker compose run --build --rm --no-deps api python -m pytest -q tests/test_api.py
```

After starting the API, run the real database integration smoke check:

```bat
python scripts/check_api.py
```
