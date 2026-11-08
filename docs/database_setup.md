# FlightInsight — PostgreSQL and BTS import

## Requirements

- Docker Desktop / Docker Compose v2, running.
- Python 3.11+ for the standard-library setup and BTS download scripts.
- Internet access on initial download and Docker image build.

No local PostgreSQL installation and no local Python database driver are required.

## 1. Start the database

From the repository root:

```bat
python scripts\init_env.py
docker compose config -q
docker compose up -d postgres
python scripts\check_database.py
```

The setup helper creates `.env` with a random password and **never overwrites** it. `.env` is excluded from Git. PostgreSQL listens on `127.0.0.1:5432` by default.

The database schema is initialized by PostgreSQL **only on the first start of an empty Docker data volume**; subsequent starts preserve data.

## 2. Download and inspect official BTS data

```bat
python scripts\download_bts.py
python scripts\inspect_bts.py
```

These scripts save the official January–March 2025 BTS ZIP files under `data/raw/` (ignored by Git). They are run on the host because the ETL container mounts this directory read-only.

## 3. Import into PostgreSQL

```bat
docker compose run --build --rm etl
```

This runs Python 3.12 in Docker and installs only `psycopg[binary]` into the ETL image. It does **not** require modifying your existing Python virtual environment. Docker Compose automatically waits for PostgreSQL's healthcheck.

The importer:

- Streams source CSV records from each ZIP; never loads a complete month into RAM.
- Validates required fields, formats, dates, local clock HHMM (`2400` is allowed), and delay/status values.
- Rejects the **entire month's transaction** if even one malformed record is found, instead of quietly losing flights.
- Loads dimension tables `airlines` and `airports`, then flights with their foreign keys.
- Imports each month atomically, recording file SHA-256 and row counts in `import_batches`.
- Skips an archive whose SHA-256 is already marked `completed`.
- Prevents duplicate scheduled flights through a unique constraint and `ON CONFLICT DO NOTHING`.
- Preserves `NULL` where delay causes were not reported; it does not substitute zero.

**Important:** The import may use substantial disk space during database loading, and it needs working Docker Desktop resources.

## 4. Verify

```bat
python scripts\check_import.py
python -m unittest discover -s tests -p "test_import_flights.py" -v
git status --short
```

Successful import should contain exactly **1,645,503** flight rows for these three source files and three completed batches. Re-run `docker compose run --rm etl` to confirm that every ZIP is skipped and no rows are duplicated.

## Troubleshooting

- Missing ZIP: run `python scripts\download_bts.py` again.
- Docker errors: ensure Docker Desktop is running; inspect `docker compose ps` and `docker compose logs postgres`.
- ETL failed: inspect its printed error and the latest `import_batches.error_message`. Fix source/configuration and re-run; the failed month does not partially commit.
- **Never run `docker compose down -v` unless you deliberately want to delete all database data.** `docker compose down` without `-v` keeps the volume.

The automated one-command end-user initialization will be added by finalization, together with the API and dashboard.
