import math
import urllib.error
from datetime import date, timedelta

from scripts.fetch import discover
from scripts.ingest import ingest
from scripts.utils import get


def handler(event, context):
    current_date = date.today() - timedelta(days=1)

    if current_date.weekday() >= 5:
        print(f"{current_date.strftime('%Y-%m-%d')}: weekend, no data")
        return {"statusCode": 200, "status": "weekend, skipped"}

    try:
        df = discover(current_date)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            year = current_date.year
            qtr = math.ceil(current_date.month / 3)
            probe_url = (
                f"https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/"
            )
            try:
                get(probe_url)
            except urllib.error.HTTPError:
                print(f"probe failed - likely blocked, stopping at {current_date}")
                raise e
            print(f"no index for {current_date.strftime('%Y-%m-%d')}, skipping")
            return {"statusCode": 200, "status": "no index (holiday), skipped"}
        raise

    ingest(df)
    return {"statusCode": 200, "status": "ingested", "filings_found": len(df)}
