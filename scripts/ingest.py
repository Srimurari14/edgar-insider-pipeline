# ingest.py
import os
import time
import urllib.error

from scripts.config import ARCHIVES_BASE, BRONZE_PREFIX, SLEEP
from scripts.storage import exists, write_bytes
from scripts.utils import get


def ingest(rows):
    print("Starting ingest...")
    for i, row in rows.iterrows():
        filing_date = str(row["date_filed"]).strip()
        filename = row["filename"]

        url = ARCHIVES_BASE + filename
        accession = os.path.basename(filename)
        file_path = f"{BRONZE_PREFIX}/filing_date={filing_date}/{accession}"

        if exists(file_path):
            continue
        try:
            raw = get(url)
        except urllib.error.HTTPError:
            continue

        time.sleep(SLEEP)
        write_bytes(file_path, raw)

    print(f"raw files written to {BRONZE_PREFIX}")
