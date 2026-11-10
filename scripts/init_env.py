"""Create or upgrade local .env, keeping the existing database password."""
from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
ADMIN_PLACEHOLDER = "replace_with_local_password"
READER_PLACEHOLDER = "replace_with_local_reader_password"


def _private_permissions(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, 0o600)


def _create_exclusive(path: Path, content: str) -> None:
    # A new POSIX file has 0600 from its first instant on disk.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
        out.write(content)
    _private_permissions(path)


def _set_value(text: str, key: str, placeholder: str, *, allow_add: bool = True) -> tuple[str, bool]:
    prefix = key + "="
    lines = text.splitlines(keepends=True)
    matching = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matching) > 1:
        raise ValueError(f"Duplicate entry for {key}")
    if not matching:
        if not allow_add:
            raise ValueError(f"Missing {key}")
        return text.rstrip("\r\n") + "\n" + prefix + secrets.token_urlsafe(32) + "\n", True
    i = matching[0]
    current = lines[i].strip().split("=", 1)[1]
    if current == placeholder:
        lines[i] = prefix + secrets.token_urlsafe(32) + "\n"
        return "".join(lines), True
    if not current:
        raise ValueError(f"Empty {key}")
    return text, False


def main() -> int:
    if not EXAMPLE.is_file():
        print("[ERROR] .env.example not found", file=sys.stderr)
        return 1
    if not TARGET.exists():
        template = EXAMPLE.read_text(encoding="utf-8-sig")
        try:
            template, _ = _set_value(template, "POSTGRES_PASSWORD", ADMIN_PLACEHOLDER, allow_add=False)
            template, _ = _set_value(template, "POSTGRES_READ_PASSWORD", READER_PLACEHOLDER)
            _create_exclusive(TARGET, template)
        except FileExistsError:
            print("[INFO] .env appeared during setup; checking it")
        except (OSError, ValueError) as exc:
            print(f"[ERROR] Could not create .env: {type(exc).__name__}", file=sys.stderr)
            return 1
        else:
            print("[OK] Private .env created with two independent random passwords")
            return 0

    # The existing database may contain millions of records; NEVER rotate its admin password.
    try:
        text = TARGET.read_text(encoding="utf-8-sig")
        if not any(line.startswith("POSTGRES_PASSWORD=") for line in text.splitlines()):
            raise ValueError("Existing .env lacks POSTGRES_PASSWORD")
        if any(line.strip() == "POSTGRES_PASSWORD=" + ADMIN_PLACEHOLDER for line in text.splitlines()):
            raise ValueError("Existing .env has placeholder admin password")
        updated, changed = _set_value(text, "POSTGRES_READ_PASSWORD", READER_PLACEHOLDER)
        _private_permissions(TARGET)
        if changed:
            # Atomic replacement avoids truncating a working .env on disk errors.
            fd, temp_name = tempfile.mkstemp(prefix=".env-", dir=TARGET.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
                    out.write(updated)
                _private_permissions(Path(temp_name))
                os.replace(temp_name, TARGET)
                _private_permissions(TARGET)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            print("[OK] Existing .env updated with a new API reader password; admin password kept")
        else:
            print("[SKIP] Existing .env already configured; secrets unchanged")
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Could not update .env: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
