"""Non-destructive API identity and database grant smoke check."""
from __future__ import annotations

import os

# Docker runs this file as ``python scripts/check_db_permissions.py``.
# In that mode Python puts /app/scripts (not /app) on sys.path, so the
# sibling module must be imported directly. Module execution from the
# repository root uses the package-relative form.
if __package__:
    from .run_analytics import open_connection
else:
    from run_analytics import open_connection


def main() -> int:
    expected = os.getenv("POSTGRES_USER", "flightinsight_reader")
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT current_user, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
                          has_table_privilege(current_user, 'public.flights', 'SELECT'),
                          has_table_privilege(current_user, 'public.flights', 'INSERT'),
                          has_table_privilege(current_user, 'public.import_batches', 'SELECT')
                   FROM pg_roles r WHERE r.rolname = current_user"""
            )
            user, superuser, createdb, createrole, read_flights, write_flights, read_batches = cur.fetchone()
    if user != expected or any(
        (superuser, createdb, createrole, not read_flights, write_flights, read_batches)
    ):
        raise AssertionError(f"[FAIL] API role {user!r} has unexpected privileges")
    print(f"[OK] API identity {user} has SELECT on flights and no write/admin privileges")
    print("[OK] Private import_batches table is not readable through API credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
