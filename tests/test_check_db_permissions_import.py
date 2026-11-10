"""Regression tests for check_db_permissions.py in Docker and module modes."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_db_permissions.py"

STUB_RUN_ANALYTICS = """\
class _Cursor:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query):
        self.query = query
    def fetchone(self):
        return ("flightinsight_reader", False, False, False, True, False, False)

class _Connection:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return _Cursor()

def open_connection():
    return _Connection()
"""


class DbPermissionScriptImportTests(unittest.TestCase):
    def _run(self, module_mode: bool) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "scripts"
            package.mkdir()
            (package / "check_db_permissions.py").write_text(
                SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (package / "run_analytics.py").write_text(
                STUB_RUN_ANALYTICS, encoding="utf-8"
            )
            if module_mode:
                (package / "__init__.py").write_text("", encoding="utf-8")
                command = [sys.executable, "-m", "scripts.check_db_permissions"]
            else:
                command = [sys.executable, str(package / "check_db_permissions.py")]

            env = os.environ.copy()
            env["POSTGRES_USER"] = "flightinsight_reader"
            return subprocess.run(
                command, cwd=tmp, env=env, capture_output=True,
                text=True, check=False,
            )

    def test_direct_script_execution_used_by_docker(self):
        result = self._run(module_mode=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("[DONE]", result.stdout) if "[DONE]" in result.stdout else self.assertIn(
            "[OK] API identity flightinsight_reader", result.stdout
        )

    def test_module_execution_from_repository_root(self):
        result = self._run(module_mode=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("[OK] API identity flightinsight_reader", result.stdout)


if __name__ == "__main__":
    unittest.main()
