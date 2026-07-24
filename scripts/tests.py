# validate.py
import pandas as pd

from scripts.config import BRONZE_PREFIX, SILVER_PATH, SILVER_PREFIX
from scripts.storage import list_files


def validate():
    print("\nValidating silver ...")

    df = pd.read_parquet(SILVER_PATH)
    bronze_count = sum(1 for _ in list_files(BRONZE_PREFIX))

    # ---- hard invariants ----
    assert len(df) > 0, "silver is empty"

    assert df["accession"].nunique() == bronze_count, (
        f"filing count mismatch: {df['accession'].nunique()} in silver "
        f"vs {bronze_count} in bronze"
    )

    # one parquet file per partition; more means an append instead of a wipe
    files_per_partition = {}
    for key in list_files(SILVER_PREFIX):
        if not key.endswith(".parquet"):
            continue 
        partition = key.rsplit("/", 1)[0]
        files_per_partition[partition] = files_per_partition.get(partition, 0) + 1

    bad = {p: n for p, n in files_per_partition.items() if n > 1}
    assert not bad, f"multiple parquet files per partition (append not wipe?): {bad}"

    for col in ["accession", "filing_date", "issuer_cik", "owner_cik"]:
        nulls = df[col].isna().sum()
        assert nulls == 0, f"{nulls} null values in {col}"

    for col in [
        "transaction_shares",
        "transaction_price_per_share",
        "shares_owned_after",
    ]:
        assert df[col].dtype == "float64", f"{col} is {df[col].dtype}, expected float64"

    for col in ["is_director", "is_officer", "is_ten_percent_owner", "is_other"]:
        assert df[col].dtype == "bool", f"{col} is {df[col].dtype}, expected bool"

    # empty price must stay null, never coerced to 0
    priced = df["transaction_shares"].notna()
    assert df.loc[priced, "transaction_price_per_share"].isna().sum() > 0, (
        "no null prices found - footnoted prices may have been filled with 0"
    )

    print(f"  rows:            {len(df)}")
    print(f"  filings:         {df['accession'].nunique()} (bronze: {bronze_count})")
    print(f"  days:            {df['filing_date'].nunique()}")
    print(f"  partitions:      {len(files_per_partition)}")
    print(f"  issuers:         {df['issuer_cik'].nunique()}")
    print(f"  owners:          {df['owner_cik'].nunique()}")
    print(f"  no transaction:  {df['transaction_code'].isna().sum()}")
    print(f"  null prices:     {df['transaction_price_per_share'].isna().sum()}")
    print(f"  zero prices:     {(df['transaction_price_per_share'] == 0).sum()}")
    print(f"  identical rows:  {len(df) - len(df.drop_duplicates())}")

    print("\n  rows per day:")
    for day, n in df["filing_date"].value_counts().sort_index().items():
        print(f"    {day}: {n}")

    print("\n  transaction codes:")
    for code, n in df["transaction_code"].value_counts().head(10).items():
        print(f"    {code}: {n}")

    print("\nValidation passed.")