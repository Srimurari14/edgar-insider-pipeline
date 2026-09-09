# schema.py

SCHEMA_DESCRIPTION = """
SCHEMA: edgar_form4 (queryable via Athena)

Table: fct_transactions
One row per insider transaction (a single trade within a Form 4 filing).
Columns:
  filing_date (string, format YYYY-MM-DD) - the day the filing was submitted. Compare as a string, e.g. WHERE filing_date = '2026-08-18', NOT with DATE '2026-08-18'.
  accession (string) - unique ID for the filing this transaction came from
  period_of_report (timestamp)
  document_type (string)
  issuer_cik (string) - the company's SEC identifier
  issuer_name (string)
  issuer_trading_symbol (string) - stock ticker
  owner_cik (string) - the insider's SEC identifier
  owner_name (string)
  is_director, is_officer, is_ten_percent_owner, is_other (boolean) - insider's role
  officer_title (string, nullable)
  other_text (string, nullable) - free text, used when relationship doesn't fit the other role flags
  security_title (string) - name of the security traded (e.g. "Common Stock", or a bond/note name)
  transaction_date (timestamp) - when the trade itself happened; can be much older than filing_date (insiders sometimes file late or file amendments)
  transaction_code (string) - raw SEC code. Common values: P=purchase, S=sale, J=other/filer-specified (e.g. debt-to-equity conversions, where the "price" is an accounting artifact, not a real market price)
  transaction_shares (double)
  transaction_price_per_share (double)
  acquired_disposed_code (string) - A=acquired, D=disposed
  shares_owned_after (double)
  ownership_type (string) - D=direct, I=indirect
  transaction_classification (string) - Buy, Sell, Merger Disposition, or Other
  dollar_value (double) - transaction_shares * transaction_price_per_share
  is_debt_security (boolean) - true if the SECURITY ITSELF is a bond/note (based on security_title). Does not check transaction_code.
  is_nonstandard_pricing (boolean) - true if the TRANSACTION TYPE makes price_per_share unreliable (currently: transaction_code = 'J', e.g. debt-to-equity conversions). Independent of is_debt_security; a row can trip this flag while being genuine equity.
  dollar_value_unreliable (boolean) - true if EITHER is_debt_security OR is_nonstandard_pricing is true. Use this as the general-purpose filter for "is dollar_value trustworthy for this row."

Table: dim_issuers
One row per company (issuer_cik), showing its most recent known name/ticker.
Columns: issuer_cik (string), issuer_name (string), issuer_trading_symbol (string)

Table: dim_owners
One row per insider (owner_cik), showing their most recent known name.
Columns: owner_cik (string), owner_name (string)

Table: agg_issuer_activity
One row per company, summarizing all its insider activity.
Columns:
  issuer_cik (string), issuer_name (string)
  total_owner_count (bigint) - number of distinct insiders who have traded this company's stock
  last_transaction_date (timestamp)
  total_buy_value, total_sell_value (double) - dollar totals (debt securities excluded)
  total_buy_count, total_sell_count (bigint) - number of transactions

Table: agg_owner_activity
One row per insider, summarizing all their trading activity across companies.
Columns:
  owner_cik (string), owner_name (string)
  last_transaction_date (timestamp)
  total_buy_value, total_sell_value (double) - dollar totals (debt securities excluded)
  total_buy_count, total_sell_count (bigint) - number of transactions

General notes:
  - filing_date is a string column, not a native date type. Always compare it as a string.
  - period_of_report and transaction_date are real timestamp columns and can be compared with standard date functions.
  - For questions about TYPICAL or AGGREGATE trade dollar amounts (totals, averages, "how much did insiders buy this month"), filter out unreliable rows: WHERE dollar_value_unreliable = false in fct_transactions. The two agg tables already exclude debt securities from their totals.
  - For questions specifically about OUTLIERS, ANOMALIES, or the LARGEST/SMALLEST values in the data ("what's the biggest trade ever", "any suspicious numbers"), do NOT filter out unreliable rows by default. Query across all rows first, since the anomaly itself may be exactly the kind of row dollar_value_unreliable is designed to flag. If you find a large or unusual dollar_value, check its is_debt_security and is_nonstandard_pricing values and explain what they mean as part of your answer, rather than excluding the row before ever seeing it.
"""