"""Create a local .env using .env.example and a random password (stdlib only).

Never overwrites an existing .env. Git ignores the generated file.
Run from anywhere: python scripts/init_env.py
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
PLACEHOLDER = "POSTGRES_PASSWORD=replace_with_local_password"


def main() -> int:
    if TARGET.exists():
        print("[SKIP] .env already exists; no credentials changed")
        return 0
    if not EXAMPLE.is_file():
        print("[ERROR] .env.example not found", file=sys.stderr)
        return 1

    template = EXAMPLE.read_text(encoding="utf-8-sig")
    if template.count(PLACEHOLDER) != 1:
        print("[ERROR] Expected password placeholder not found exactly once", file=sys.stderr)
        return 1

    password = secrets.token_urlsafe(32)
    content = template.replace(PLACEHOLDER, f"POSTGRES_PASSWORD={password}")
    try:
        # Exclusive create: refuse to replace a file created meanwhile.
        with TARGET.open("x", encoding="utf-8", newline="\n") as out:
            out.write(content)
    except FileExistsError:
        print("[SKIP] .env appeared; no credentials changed")
        return 0
    print("[OK] Local .env created with a random password (not printed)")
    print("[INFO] .env is ignored by Git; do not publish this file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
