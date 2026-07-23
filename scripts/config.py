# config.py

HEADERS = {"User-Agent": "Sri dachepallisrimurari@gmail.com"}

DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/master.{date}.idx"
)
ARCHIVES_BASE = "https://www.sec.gov/Archives/"

SLEEP = 0.2

COLS = ["cik", "company", "form_type", "date_filed", "filename"]

BRONZE_PATH = "data/bronze/form4"
SILVER_PATH = "data/silver/form4"
