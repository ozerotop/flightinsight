# FlightInsight

**FlightInsight** is a reproducible flight-reliability analytics web service built with real [Bureau of Transportation Statistics (BTS)](https://www.transtats.bts.gov/) U.S. domestic flight data.

It helps explore **historical** airline/airport punctuality, cancellations, arrival delays, and time-of-day patterns. Historical trends are not predictions or guarantees for future flights.

**Dataset:** January–March 2025, **1,645,503** flight records. Large source ZIPs are downloaded from BTS on first run and are **not committed to Git**.

## Quick start — from a fresh GitHub clone

**Prerequisites:** Git, Docker Desktop (Windows/macOS) or Docker Engine with Compose v2 (Linux), internet access and sufficient disk space. Ensure Docker is started and using Linux containers. **Host Python is not required.**

### Windows CMD or PowerShell

```bat
git clone https://github.com/ozerotop/flightinsight.git
cd flightinsight
start.cmd
```

In PowerShell, run `./start.cmd` instead of `start.cmd` if needed.

### Linux / macOS

```bash
git clone https://github.com/ozerotop/flightinsight.git
cd flightinsight
bash start.sh
```

The launcher uses a temporary official Python Docker image to create a **random local database password** in ignored `.env` and download the three official BTS ZIPs. It then initializes PostgreSQL, runs the transactional ETL and launches the API/dashboard, waiting for health checks. The end-to-end API smoke check validates expected Q1 2025 counts.

**Open the app:** http://localhost:8501  
**Explore API/Swagger:** http://localhost:8000/docs

Initial setup requires network downloads and the import of 1.6 million records. Once the archives and database volume exist, rerunning the same launcher should safely reuse them.

## Features

- Validated, streaming ETL from compressed BTS CSVs into PostgreSQL, with import batch logs and duplicate prevention.
- Relational entities: `airlines`, `airports`, `flights`, `import_batches`.
- SQL analytics with CTEs, aggregation, medians and window functions, plus `EXPLAIN ANALYZE` checks.
- Read-only FastAPI with OpenAPI/Swagger and parameterized filters.
- Streamlit/Plotly dashboard covering overview, airlines, airports, time patterns and disruptions.
- CSV report exports, date/route/airline filters, minimum sample-size controls.
- Docker Compose and Python tests.

The **delayed** criterion is arrival **15+ minutes after schedule**. Cancelled/diverted flights are reported separately and excluded from arrival punctuality denominators; the average schedule deviation differs from lateness among delayed flights only.

## Architecture

```text
BTS official ZIP/CSV  ->  Python ETL  ->  PostgreSQL  ->  FastAPI  ->  Streamlit / Plotly
                              |                |           |
                         data checks       SQL queries   REST / Swagger
```

PostgreSQL credentials and original CSV/ZIPs stay local. The dashboard calls FastAPI over Docker's internal network, not the database directly. Services are bound to `127.0.0.1` by default.

## Common commands

From the repository root after first startup:

```bash
# See service health and container status
docker compose ps

# Run the same idempotent import again (should skip existing months)
docker compose run --rm etl

# Verify database aggregates and SQL queries
docker compose run --rm analytics python scripts/check_analytics.py

# Test the API in its own container
docker compose run --rm --no-deps api python -m pytest -q tests/test_api.py

# Stop the application without deleting data
docker compose stop

# Restart without re-importing data
docker compose up -d --wait api dashboard
```

Optional end-to-end HTTP checks with **host Python 3.11+**, if installed:

```bash
python scripts/check_release.py
```

Or run the container-based API verification with no host Python:

```bash
docker compose exec -T api python scripts/check_api.py
```

To run dependency-free Python unit tests on a machine with Python installed:

```bash
python -m unittest discover -s tests -p "test_release.py" -v
```

**Do not use `docker compose down -v` or `docker volume prune`** unless you intentionally want to delete the local PostgreSQL database. `docker compose stop` keeps the data volume intact.

## Troubleshooting

- **Docker engine unavailable:** Start Docker Desktop, then run `docker info`; on Windows select Linux containers.
- **Download failure:** Check access to BTS (official source details in `docs/data_source.md`), then rerun the launcher. For restricted Docker networking, you can run `python scripts/download_bts.py` on the host if Python is available; rerunning the launcher will skip the already downloaded ZIPs.
- **Port 8000 / 8501 / 5432 in use:** Stop the conflicting service; the default Compose file binds these to localhost only.
- **DB is empty:** Run `docker compose run --build --rm etl`, then `docker compose exec -T api python scripts/check_api.py`.
- **Dashboard error:** Use `docker compose ps` and `docker compose logs --tail=80 dashboard api postgres`.
- **Fresh start:** Delete data only if intended. Existing `.env` is never overwritten by the launcher; keep it with the database volume it belongs to.

## Data, design and tests

- [Requirements](docs/requirements.md) and [BTS data source](docs/data_source.md)
- [Data dictionary](docs/data_dictionary.md) and [quality report](docs/data_quality_report.md)
- [ER diagram](docs/er_diagram.md) and [database setup](docs/database_setup.md)
- [SQL metrics](docs/sql_analytics.md) and [API endpoints](docs/api.md)
- [Portfolio description and interview preparation](docs/portfolio.md)

## Development status

The ETL, SQL reports, API and dashboard have been exercised on one Windows/Docker Desktop installation with the Q1 2025 dataset. The launchers are provided for repeatability but **must still be validated from a clean clone on another computer** before claiming full cross-platform reproducibility. No files from `data/raw`, `.env`, or Docker volumes belong in GitHub.
