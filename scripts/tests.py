import pandas as pd
s = pd.read_parquet("data/silver/form4")
print(s["accession"].nunique())                          # should be 2652
print(s["filing_date"].value_counts().sort_index())
print(s.dtypes)
print(s["transaction_price_per_share"].isna().sum(), "null prices")
print(s.groupby("owner_cik")["issuer_cik"].nunique().sort_values(ascending=False).head(10))