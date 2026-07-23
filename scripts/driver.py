# driver.py
import urllib.error
from datetime import datetime, timedelta

from scripts.fetch import discover
from scripts.ingest import ingest
from scripts.parse import parse

start_date = datetime(2026, 7, 6)
end_date = datetime(2026, 7, 12)

for i in range((end_date - start_date).days + 1):
    current_date = start_date + timedelta(days=i)
    if current_date.weekday() >= 5:
        print(f'{current_date.strftime("%Y-%m-%d")}: weekend, no data')
        continue
    try:
        df = discover(current_date)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"no index for {current_date.strftime('%Y-%m-%d')}, skipping")
            continue
        raise
    ingest(df)
parse()
