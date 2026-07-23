# fetch.py
import math
import os
import time

import pandas as pd
from scripts.config import COLS, DAILY_INDEX_URL, SLEEP
from scripts.utils import get


def discover(dte):
    print(f"Starting fetch for {dte.strftime('%Y-%m-%d')}...")
    year = dte.year
    qtr = math.ceil(dte.month / 3)
    dt_str = dte.strftime("%Y%m%d")

    time.sleep(SLEEP)
    url = DAILY_INDEX_URL.format(year=year, qtr=qtr, date=dt_str)
    m = get(url).decode("utf-8", errors="replace").splitlines()

    form4_rows = []
    for line in m:
        if "|" not in line:
            continue
        row = [c.strip() for c in line.split("|")]
        if row[2] == "4":
            form4_rows.append(row)

    print(f"{dt_str}: {len(form4_rows)} Form 4 filings")
    df = pd.DataFrame(form4_rows, columns=COLS)

    os.makedirs("data/discovery", exist_ok=True)
    out = f"data/discovery/{dt_str}.csv"
    df.to_csv(out, header=True, index=False)
    print(f"data saved to {out}")
    return df
