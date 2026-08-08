# parse.py
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
from botocore.exceptions import ClientError

from scripts.config import BRONZE_PREFIX, SILVER_PATH, SILVER_PREFIX
from scripts.storage import list_files, read_bytes
from scripts.utils import find_text, to_bool


def parse():
    print("Parsing Data ...")

    existing_silver_files = [
        k for k in list_files(SILVER_PREFIX) if k.endswith(".parquet")
    ]
    if existing_silver_files:
        existing_accessions = set(
            pd.read_parquet(SILVER_PATH, columns=["accession"])["accession"].unique()
        )
        print(f"{len(existing_accessions)} accessions already in silver")
    else:
        existing_accessions = set()
        print("no existing silver data found, parsing all bronze files")

    all_transactions = []
    skipped = []
    already_processed = 0

    for i in list_files(BRONZE_PREFIX):
        if not i.endswith(".txt"):
            continue
        s = i.split("/")
        filing_date = datetime.strptime(s[-2].split("=")[1], "%Y%m%d").strftime(
            "%Y-%m-%d"
        )
        accession = s[-1].removesuffix(".txt")

        if accession in existing_accessions:
            already_processed += 1
            continue

        try:
            raw = read_bytes(i).decode("utf-8", errors="replace")
            xml_start = raw.find("<XML>")
            xml_end = raw.find("</XML>")
            if xml_start == -1 or xml_end == -1:
                skipped.append((accession, "no <XML> block"))
                continue
            root = ET.fromstring(raw[xml_start + 5 : xml_end].strip())
        except (ET.ParseError, OSError, ClientError) as e:
            skipped.append((accession, str(e)))
            continue

        row = {
            "accession": accession,
            "filing_date": filing_date,
            "period_of_report": find_text(root, "periodOfReport"),
            "document_type": find_text(root, "documentType"),
            "issuer_cik": find_text(root, "issuer/issuerCik"),
            "issuer_name": find_text(root, "issuer/issuerName"),
            "issuer_trading_symbol": find_text(root, "issuer/issuerTradingSymbol"),
            "owner_cik": find_text(root, "reportingOwner/reportingOwnerId/rptOwnerCik"),
            "owner_name": find_text(
                root, "reportingOwner/reportingOwnerId/rptOwnerName"
            ),
            "is_director": to_bool(
                find_text(root, "reportingOwner/reportingOwnerRelationship/isDirector")
            ),
            "is_officer": to_bool(
                find_text(root, "reportingOwner/reportingOwnerRelationship/isOfficer")
            ),
            "is_ten_percent_owner": to_bool(
                find_text(
                    root, "reportingOwner/reportingOwnerRelationship/isTenPercentOwner"
                )
            ),
            "is_other": to_bool(
                find_text(root, "reportingOwner/reportingOwnerRelationship/isOther")
            ),
            "officer_title": find_text(
                root, "reportingOwner/reportingOwnerRelationship/officerTitle"
            ),
            "other_text": find_text(
                root, "reportingOwner/reportingOwnerRelationship/otherText"
            ),
        }

        txns = root.findall("nonDerivativeTable/nonDerivativeTransaction")

        if not txns:
            all_transactions.append(
                {
                    **row,
                    "security_title": None,
                    "transaction_date": None,
                    "transaction_code": None,
                    "transaction_shares": None,
                    "transaction_price_per_share": None,
                    "acquired_disposed_code": None,
                    "shares_owned_after": None,
                    "ownership_type": None,
                }
            )
        else:
            for t in txns:
                all_transactions.append(
                    {
                        **row,
                        "security_title": find_text(t, "securityTitle/value"),
                        "transaction_date": find_text(t, "transactionDate/value"),
                        "transaction_code": find_text(
                            t, "transactionCoding/transactionCode"
                        ),
                        "transaction_shares": find_text(
                            t, "transactionAmounts/transactionShares/value"
                        ),
                        "transaction_price_per_share": find_text(
                            t, "transactionAmounts/transactionPricePerShare/value"
                        ),
                        "acquired_disposed_code": find_text(
                            t,
                            "transactionAmounts/transactionAcquiredDisposedCode/value",
                        ),
                        "shares_owned_after": find_text(
                            t,
                            "postTransactionAmounts/sharesOwnedFollowingTransaction/value",
                        ),
                        "ownership_type": find_text(
                            t, "ownershipNature/directOrIndirectOwnership/value"
                        ),
                    }
                )

    if not all_transactions:
        print(
            f"no new filings to parse ({already_processed} already in silver, "
            f"{len(skipped)} skipped)"
        )
        return {
            "new_rows": 0,
            "new_filings": 0,
            "already_processed": already_processed,
            "skipped": len(skipped),
        }

    df = pd.DataFrame(all_transactions)

    numeric_cols = [
        "transaction_shares",
        "transaction_price_per_share",
        "shares_owned_after",
    ]
    date_cols = ["period_of_report", "transaction_date"]

    df[numeric_cols] = (
        df[numeric_cols].apply(pd.to_numeric, errors="coerce").astype(float)
    )
    df[date_cols] = df[date_cols].apply(pd.to_datetime, errors="coerce")

    print(f"parsed {len(df)} new rows from {df['accession'].nunique()} filings, writing...")

    df.to_parquet(SILVER_PATH, partition_cols=["filing_date"], index=False)

    print(f"write done to {SILVER_PREFIX}")
    print(f"{already_processed} filings already in silver, skipped")
    if skipped:
        print(f"{len(skipped)} files skipped:")
        for acc, reason in skipped:
            print(f"  {acc}: {reason}")

    return {
        "new_rows": len(df),
        "new_filings": df["accession"].nunique(),
        "already_processed": already_processed,
        "skipped": len(skipped),
    }