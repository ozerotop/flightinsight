"""Download the three official BTS monthly on-time datasets for FlightInsight.

Run from repository root:
    python scripts/download_bts.py

Files are kept in data/raw/, which is excluded from Git.
"""

from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
BASE_URL = "https://www.transtats.bts.gov/PREZIP"
YEAR = 2025
MONTHS = (1, 2, 3)


def download(month: int) -> bool:
    name = (
        "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_"
        f"{YEAR}_{month}.zip"
    )
    destination = RAW_DIR / f"bts_{YEAR}_{month:02d}.zip"
    partial = destination.with_suffix(".zip.part")
    if destination.is_file() and zipfile.is_zipfile(destination):
        print(f"[SKIP] {destination.name} (valid ZIP already exists)", flush=True)
        return True

    url = f"{BASE_URL}/{name}"
    print(f"[GET]  {YEAR}-{month:02d} from {url}", flush=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 FlightInsight/0.1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
        if not zipfile.is_zipfile(partial):
            raise ValueError("Downloaded file is not a ZIP archive")
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP failed CRC check")
            if not any(n.lower().endswith(".csv") for n in archive.namelist()):
                raise ValueError("ZIP has no CSV file")
        partial.replace(destination)
        print(f"[OK]   {destination.name} ({destination.stat().st_size:,} bytes)", flush=True)
        return True
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f"[FAIL] {YEAR}-{month:02d}: {error}", file=sys.stderr)
        print("       Download the month manually from the official BTS site,", file=sys.stderr)
        print(f"       save as: {destination}", file=sys.stderr)
        return False
    finally:
        partial.unlink(missing_ok=True)


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    failed = [month for month in MONTHS if not download(month)]
    if failed:
        print(f"Failed months: {failed}", file=sys.stderr)
        return 1
    print("All three ZIP archives are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
