"""Idempotently provision FlightInsight's read-only PostgreSQL API user.

Runs as one-shot Docker Compose service db-roles, using the ETL/admin identity.
It works for both an existing populated volume and a fresh PostgreSQL instance.
"""
from __future__ import annotations

import os
import re
import sys


def main() -> int:
    import psycopg
    from psycopg import sql

    admin = os.environ["POSTGRES_USER"]
    reader = os.environ.get("POSTGRES_READ_USER", "flightinsight_reader")
    password = os.environ["POSTGRES_READ_PASSWORD"]
    dbname = os.environ.get("POSTGRES_DB", "flightinsight")
    if (not re.fullmatch(r"[a-z][a-z0-9_]{2,30}", reader)
            or reader in {admin, "postgres"}):
        raise ValueError("Invalid or privileged API role name")
    if len(password) < 24 or password == "replace_with_local_reader_password":
        raise ValueError("Use scripts/init_env.py to generate POSTGRES_READ_PASSWORD")

    with psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=dbname, user=admin, password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=15, autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = %s", (reader,))
            existing = cur.fetchone()
            if existing is None:
                cur.execute(sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(sql.Identifier(reader)))
            elif any(existing):
                raise RuntimeError("Existing API role has elevated privileges; refusing to reuse it")

            # Password is safely SQL-quoted and never printed to the terminal.
            cur.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(reader), sql.Literal(password)))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(dbname), sql.Identifier(reader)))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(reader)))
            cur.execute(sql.SQL("GRANT SELECT ON TABLE public.airlines, public.airports, public.flights TO {}").format(
                sql.Identifier(reader)))
            cur.execute("SELECT has_table_privilege(%s, 'public.flights', 'SELECT'), "
                        "has_table_privilege(%s, 'public.flights', 'INSERT')", (reader, reader))
            can_read, can_write = cur.fetchone()
            if not can_read or can_write:
                raise RuntimeError("Unexpected API table privileges")
    print("[OK] Read-only database role ready; existing flight data unchanged")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] API database role setup failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from exc
