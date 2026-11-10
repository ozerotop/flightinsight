# FlightInsight — local security model

This is a local analytics portfolio project, not a production SaaS application.
The published Compose ports listen only on `127.0.0.1`; there is no authentication
or TLS termination. **Do not publish ports 5432, 8000 or 8501 to the internet.**

## Database identity
`etl` uses `POSTGRES_USER` to import source data and manage staging tables.
`db-roles` is a one-shot, idempotent administrative job that creates or repairs
`flightinsight_reader`, which has `CONNECT`, schema `USAGE`, and `SELECT` on
`flights`, `airlines` and `airports`. The API and analytics use only this reader.
The reader cannot insert, create roles or read import history. Existing database
volumes are preserved. To verify: `docker compose exec -T api python scripts/check_db_permissions.py`.

## Secrets and isolation
`start.cmd` or `bash start.sh` creates `.env` with two random credentials.
Upgrading an existing `.env` appends a reader secret without rotating the admin
password. On POSIX, file permissions are set to owner-only (0600). Files under
`data/raw`, `.env`, local virtual environments and Docker database volumes are
not part of the Git repository. Application images run as UID 10001, with
capabilities removed and no-new-privileges enabled.

## Dependencies and limitations
The API and dashboard dependency pins were updated in November 2026. Review
Dependabot alerts and rebuild images as security patches are released. Successful
unit tests alone do not prove vulnerability-free software; **a rebuild and all
live Docker smoke checks must pass** after this security update. Docker image
tags and indirect Python dependencies remain subject to change, so builds are
not bit-for-bit reproducible. Secret scanning cannot prove that no old Git
commit ever contained sensitive information; review Git history separately.

To check locally:

```bash
python -m unittest discover -s tests -v
docker compose up -d --build --wait api dashboard
docker compose exec -T api python -m pytest -q tests/test_api.py
docker compose exec -T api python scripts/check_db_permissions.py
```

For a clean-clone test, use a **new checkout and a different Compose project
name** to prevent Docker volumes from an existing checkout being reused.
