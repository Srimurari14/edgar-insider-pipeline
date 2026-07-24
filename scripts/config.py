# config.py
import os

from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": "Sri dachepallisrimurari@gmail.com"}

DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/master.{date}.idx"
)
ARCHIVES_BASE = "https://www.sec.gov/Archives/"

SLEEP = 0.2

COLS = ["cik", "company", "form_type", "date_filed", "filename"]


LOCAL_ROOT = "data"

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"

S3_BUCKET = os.getenv("S3_BUCKET", "edgar-form4-sri")
BRONZE_PREFIX = "bronze/form4"
SILVER_PREFIX = "silver/form4"

SILVER_PATH = (
    f"s3://{S3_BUCKET}/{SILVER_PREFIX}" if USE_S3 else f"{LOCAL_ROOT}/{SILVER_PREFIX}"
)
