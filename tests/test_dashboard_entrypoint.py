"""Regression check for Streamlit script import resolution.

Streamlit runs app/dashboard/app.py as a script: importing `app.dashboard.*`
from that script conflicts with the same directory's app.py file.
"""

import ast
import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "app" / "dashboard"


class StreamlitEntrypointImportsTests(unittest.TestCase):
    def test_script_uses_local_helper_imports(self):
        tree = ast.parse((SCRIPT_DIR / "app.py").read_text(encoding="utf-8"))
        imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertIn("client", imported)
        self.assertIn("helpers", imported)
        self.assertNotIn("app.dashboard.client", imported)
        self.assertNotIn("app.dashboard.helpers", imported)

    def test_helper_modules_are_importable_as_script_siblings(self):
        sys.path.insert(0, str(SCRIPT_DIR))
        try:
            client = importlib.import_module("client")
            helpers = importlib.import_module("helpers")
            self.assertTrue(callable(client.fetch_json))
            self.assertTrue(callable(helpers.export_csv))
        finally:
            sys.path.remove(str(SCRIPT_DIR))


if __name__ == "__main__":
    unittest.main()
