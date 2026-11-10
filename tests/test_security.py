"""Security checks that do not require a Docker daemon or PostgreSQL."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import init_env

ROOT = Path(__file__).resolve().parents[1]


class LocalSecretTests(unittest.TestCase):
    def test_fresh_env_has_two_secrets_and_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".env"
            example = Path(tmp) / ".env.example"
            example.write_text("POSTGRES_PASSWORD=replace_with_local_password\n"
                               "POSTGRES_READ_PASSWORD=replace_with_local_reader_password\n", encoding="utf-8")
            with patch.object(init_env, "EXAMPLE", example), patch.object(init_env, "TARGET", target):
                self.assertEqual(init_env.main(), 0)
            text = target.read_text(encoding="utf-8")
            self.assertIn("POSTGRES_PASSWORD=", text)
            self.assertIn("POSTGRES_READ_PASSWORD=", text)
            self.assertNotIn("replace_with_local", text)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_existing_admin_password_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".env"
            example = Path(tmp) / ".env.example"
            example.write_text("POSTGRES_PASSWORD=replace_with_local_password\n", encoding="utf-8")
            target.write_text("POSTGRES_DB=flightinsight\nPOSTGRES_PASSWORD=old-secret-stays\n", encoding="utf-8")
            with patch.object(init_env, "EXAMPLE", example), patch.object(init_env, "TARGET", target):
                self.assertEqual(init_env.main(), 0)
                before = target.read_text(encoding="utf-8")
                self.assertIn("POSTGRES_PASSWORD=old-secret-stays", before)
                self.assertIn("POSTGRES_READ_PASSWORD=", before)
                self.assertEqual(init_env.main(), 0)
                self.assertEqual(target.read_text(encoding="utf-8"), before)


class ComposeSecurityTests(unittest.TestCase):
    def test_stack_separates_database_users(self):
        text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("db-roles:", text)
        self.assertIn("POSTGRES_USER: flightinsight_reader", text)
        self.assertIn("POSTGRES_READ_PASSWORD:", text)
        self.assertIn('"127.0.0.1:8000:8000"', text)
        self.assertIn('"127.0.0.1:8501:8501"', text)
        self.assertIn('"no-new-privileges:true"', text)

    def test_application_images_are_nonroot(self):
        for path in ["Dockerfile.api", "Dockerfile.dashboard", "Dockerfile.etl"]:
            self.assertIn("USER 10001:10001", (ROOT / path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
