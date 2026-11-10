"""Regression tests for release scripts, no Docker daemon needed."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_release import verify_summary  # noqa: E402


class ReleaseTests(unittest.TestCase):
    def test_expected_summary(self):
        verify_summary({
            "total_flights": 1_645_503,
            "delayed_15_flights": 317_266,
            "cancelled_flights": 30_640,
            "diverted_flights": 3_817,
            "arrival_sample": 1_611_046,
        })

    def test_wrong_data_is_rejected(self):
        data = {
            "total_flights": 1_645_502,
            "delayed_15_flights": 317_266,
            "cancelled_flights": 30_640,
            "diverted_flights": 3_817,
            "arrival_sample": 1_611_046,
        }
        with self.assertRaisesRegex(AssertionError, "total_flights"):
            verify_summary(data)

    def test_launcher_does_not_delete_volumes(self):
        for name in ("start.cmd", "start.sh"):
            script = (ROOT / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("down -v", script)
            self.assertNotIn("volume prune", script)

    def test_launchers_bootstrap_and_verify(self):
        for name in ("start.cmd", "start.sh"):
            script = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("scripts/init_env.py", script)
            self.assertIn("scripts/download_bts.py", script)
            self.assertIn("docker compose run --build --rm etl", script)
            self.assertIn("docker compose up -d --build --wait api dashboard", script)
            self.assertIn("scripts/check_api.py", script)


if __name__ == "__main__":
    unittest.main()
