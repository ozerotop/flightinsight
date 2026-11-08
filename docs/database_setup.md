# Database setup — Stage 3

The purpose of this stage is to create an **empty, validated PostgreSQL database**.
Flight data are not imported until Stage 4.

## Requirements

- Docker Desktop with Docker Compose v2; Docker daemon running.
- Python 3.11+ to run the **development setup helpers** (stdlib only). Future releases will simplify the end-user startup flow.
- Windows CMD / PowerShell or an equivalent shell.

## First run

From the `flightinsight` repository root:

```bat
python scripts\init_env.py
docker compose config -q
docker compose up -d postgres
python scripts\check_database.py
```

The setup helper generates `.env` with a random password using `.env.example`; it **does not overwrite** an existing `.env` and never prints the password. `.env` is Git-ignored; do not publish it.

The database is exposed only on local `127.0.0.1:5432` by default; the port can be changed with `POSTGRES_PORT` in `.env` if needed.

The official PostgreSQL container executes `database/schema.sql` **only when its data volume is initialized for the first time**. Re-running `docker compose up -d postgres` preserves existing data. Changes to schema.sql on subsequent starts are not automatically applied as migrations.

## Verify

- `docker compose ps`: `postgres` should become `healthy`.
- `python scripts\check_database.py`: should report 4 tables, 5 indexes, 4 foreign keys.
- `git status --short`: `.env` and Docker volumes must **not** appear as tracked/untracked files.

## Stop / restart

```bat
docker compose stop postgres
docker compose up -d postgres
```

**Do not use** `docker compose down -v` unless intentionally deleting the database contents; `-v` deletes the persistent PostgreSQL volume.

## Database boundaries

- `database/schema.sql` defines `airlines`, `airports`, `import_batches`, and `flights`.
- This stage creates an empty database. The actual BTS ZIP files remain only in `data/raw/` and never go to Git.
- The backend and dashboard will be added later. The final README will document a clean-clone startup, including automated data acquisition/import and application startup.
