# FlightInsight

A reproducible flight-reliability analytics project based on real **Bureau of Transportation Statistics (BTS)** U.S. domestic flight data.

**Use case:** help teams compare historical flight punctuality and cancellation patterns across airlines, airports and time intervals. Historical patterns are not guarantees for future flights.

## Project status

- **Implemented:** BTS download and data inspection, PostgreSQL schema, Docker Compose, streaming Python ETL with validation and repeat-import protection, parameterized SQL analytics, and read-only FastAPI REST API with Swagger/OpenAPI and automated tests.
- **Next:** Streamlit/Plotly dashboard and simplified one-command Docker startup.

## Data

The dataset is BTS *Reporting Carrier On-Time Performance*, **January–March 2025** (1,645,503 flight records). The large ZIP files are **not** included in Git. Scripts download the originals from the official BTS site, and the ETL reads them directly without extraction.

Source and field definitions: [`docs/data_source.md`](docs/data_source.md) and [`docs/data_dictionary.md`](docs/data_dictionary.md). Data quality results: [`docs/data_quality_report.md`](docs/data_quality_report.md).

## Set up from a fresh clone (Windows CMD / PowerShell)

**Prerequisites:** Docker Desktop running with Docker Compose v2, Python 3.11+ (for local setup/download helpers), and internet access for the initial download and container build.

```bat
git clone https://github.com/ozerotop/flightinsight.git
cd flightinsight
python scripts\init_env.py
python scripts\download_bts.py
docker compose up -d postgres
docker compose run --build --rm etl
python scripts\check_import.py
```

The importer uses Python 3.12 **inside Docker**, so you do not have to install Python database libraries on your computer. The first run downloads the BTS archives and populates PostgreSQL; subsequent ETL runs skip already imported sources.

Run the standard-library ETL unit tests on the host:

```bat
python -m unittest discover -s tests -p "test_import_flights.py" -v
```

To stop PostgreSQL without deleting data:

```bat
docker compose stop postgres
```

> Do **not** run `docker compose down -v` unless you deliberately want to delete all stored PostgreSQL data.

More detailed setup: [`docs/database_setup.md`](docs/database_setup.md). Logical database diagram: [`docs/er_diagram.md`](docs/er_diagram.md). Requirements: [`docs/requirements.md`](docs/requirements.md).

## SQL analytics (Stage 5)

Analytics queries are stored in [`database/queries/`](database/queries/) and reused by the FastAPI service. After importing the BTS data, run:

```bat
python -m unittest discover -s tests -p "test_analytics.py" -v
docker compose run --build --rm analytics python scripts/check_analytics.py
docker compose run --rm analytics python scripts/run_analytics.py summary
docker compose run --rm analytics python scripts/run_analytics.py airlines --limit 10
docker compose run --rm analytics python scripts/run_analytics.py summary --explain
```

Reports accept date, airline, origin, destination and sample-size filters. See [`docs/sql_analytics.md`](docs/sql_analytics.md) for full commands, denominator definitions and performance testing.


## REST API (Stage 6)

After preparing `.env`, downloading BTS data and loading the PostgreSQL database:

```bat
docker compose up -d --build api
```

Open [Swagger UI](http://localhost:8000/docs) to explore endpoints.
The health endpoint is `http://localhost:8000/health`, with main metrics at
`http://localhost:8000/api/v1/summary`. These run only on localhost.

Test API contracts in the container (no extra host Python packages needed):

```bat
docker compose run --build --rm --no-deps api python -m pytest -q tests/test_api.py
```

Then check the real running API using the Python standard library:

```bat
python scripts\check_api.py
```

See [`docs/api.md`](docs/api.md) for request parameters, routes and error rules.
The API is read-only; the previous SQL and ETL commands remain supported.

## Architecture

```text
BTS ZIP/CSV -> Python ETL -> PostgreSQL -> FastAPI -> Streamlit/Plotly
```

Current schema: `airlines`, `airports`, `flights`, `import_batches`. Status, delay causes and missing values are preserved according to the documented business rules; arrivals delayed **15 or more minutes** are classified as delayed, and cancelled/diverted flights are tracked separately.

## Security and reproducibility

- Local secrets are stored in `.env`, generated with a random password and excluded from Git. `.env.example` documents the required settings.
- Large datasets, Docker volumes, virtual environments and caches are excluded from Git.
- The import is transactional per source month and can be run again without duplicating flights.
- After Stage 7 adds the dashboard, Stage 8 will simplify clean-machine startup and verify fresh-clone reproducibility.
