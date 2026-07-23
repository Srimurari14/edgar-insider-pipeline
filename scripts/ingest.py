# ingest.py
import os
import time
import urllib.error

from scripts.config import ARCHIVES_BASE, BRONZE_PATH, SLEEP
from scripts.utils import get


def ingest(rows):
    print('Starting ingest...')
    for i, row in rows.iterrows():
        filing_date = str(row["date_filed"]).strip()
        filename = row["filename"]

        url = ARCHIVES_BASE + filename

        accession = os.path.basename(filename)

        dir_path = f"{BRONZE_PATH}/filing_date={filing_date}"

        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, accession)

        if not os.path.exists(file_path):
            try:
                raw = get(url)
            except urllib.error.HTTPError as e:
                print(e.code)
                continue
            time.sleep(SLEEP)
            with open(file_path, "wb") as file:
                file.write(raw)
    print(f'raw files written to {BRONZE_PATH}')
