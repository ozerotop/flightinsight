# FlightInsight

A reproducible flight-reliability analytics project based on real **Bureau of Transportation Statistics (BTS)** U.S. domestic flight data.

**Use case:** help teams compare historical flight punctuality and cancellation patterns across airlines, airports and time intervals. Historical patterns are not guarantees for future flights.

## Project status

- **Implemented:** BTS download and data inspection, PostgreSQL schema, Docker Compose for the database, and a streaming Python ETL importer with row validation and repeat-import protection.
- **Coming next:** analytical SQL queries, REST API (FastAPI), interactive dashboard (Streamlit + Plotly), end-to-end Docker Compose startup and additional tests.

## Data

The dataset is BTS *Reporting Carrier On-Time Performance*, **January–March 2025** (1,645,503 flight records). The large ZIP files are **not** included in Git. Scripts download the originals from the official BTS site, and the ETL reads them directly without extraction.

Source and field definitions: [`docs/data_source.md`](docs/data_source.md) and [`docs/data_dictionary.md`](docs/data_dictionary.md). Data quality results: [`docs/data_quality_report.md`](docs/data_quality_report.md).

## Run the current version (Windows CMD / PowerShell)

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

## Architecture (planned complete system)

```text
BTS ZIP/CSV -> Python ETL -> PostgreSQL -> FastAPI -> Streamlit/Plotly
```

Current schema: `airlines`, `airports`, `flights`, `import_batches`. Status, delay causes and missing values are preserved according to the documented business rules; arrivals delayed **15 or more minutes** are classified as delayed, and cancelled/diverted flights are tracked separately.

## Security and reproducibility

- Local secrets are stored in `.env`, generated with a random password and excluded from Git. `.env.example` documents the required settings.
- Large datasets, Docker volumes, virtual environments and caches are excluded from Git.
- The import is transactional per source month and can be run again without duplicating flights.
- A future release will reduce new-user startup to a single Docker Compose command after the API and dashboard are implemented.
