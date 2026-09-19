#dummy.py - to backfill data in case needed 
from datetime import date
from scripts.fetch import discover
from scripts.ingest import ingest
from scripts.parse import parse

missing_dates = [date(2026, 8, 18)]

for d in missing_dates:
    df = discover(d)
    ingest(df)

parse()