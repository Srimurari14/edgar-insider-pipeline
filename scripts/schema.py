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
  transaction_classification (string) - Buy, Sell, Merger Disposition, or Other. Only code P maps to Buy and only code S maps to Sell, so every other code, including J, falls into Other.
  dollar_value (double, nullable) - transaction_shares * transaction_price_per_share. Null when either input is null.
  is_debt_security (boolean) - true if the SECURITY ITSELF is a bond/note (based on security_title). Does not check transaction_code.
  is_nonstandard_pricing (boolean) - true if the TRANSACTION TYPE makes price_per_share unreliable (currently: transaction_code = 'J', e.g. debt-to-equity conversions). Independent of is_debt_security; a row can trip this flag while being genuine equity.
  dollar_value_unreliable (boolean) - true if EITHER is_debt_security OR is_nonstandard_pricing is true. Use this as the general-purpose filter for "is dollar_value trustworthy for this row."
  is_empty_transaction (boolean) - true if the row has NO trade data at all (transaction_code, transaction_shares and transaction_price_per_share are all null). See "Empty rows" below. These rows are about 8% of the table. Exclude them whenever you count transactions.
  has_no_price (boolean) - true if the row HAS a share count but NO price per share. These are real transactions with no dollar value attached (gifts, awards, some option exercises). About 6% of the table. Count them as transactions, but their dollar_value is null so they contribute nothing to any sum.

Empty rows (is_empty_transaction = true):
A Form 4 has two sections, one for ordinary stock transactions and one for derivative
instruments such as options, RSUs and DSUs. This pipeline parses only the ordinary stock
section. When a filing contains nothing but derivative transactions, a row is still
written carrying the filing metadata (date, accession, issuer, owner) with every trade
field null. These rows mean "this person filed, and the filing held only derivative
activity." They do NOT mean the data is missing or corrupt. If a user asks about a row
or a filing like this, explain it that way rather than describing the data as blank or
unavailable. Because transaction_code is null, these rows classify as 'Other'.

An empty row is still a real filing by a real person. So if you filter with
is_empty_transaction = false, the rows that come back are the filings that contain
stock trades, not all the filings that exist. Never report that count as the number of
filings for a company. If a user asks how many filings there are, count without that
filter.

Table: dim_issuers
One row per company (issuer_cik), showing its most recent known name/ticker.
Columns: issuer_cik (string), issuer_name (string), issuer_trading_symbol (string)

Table: dim_owners
One row per insider (owner_cik), showing their most recent known name.
Columns: owner_cik (string), owner_name (string)

Table: agg_issuer_activity
One row per company, summarizing all its insider activity. Pre-computed, so prefer this
over aggregating fct_transactions yourself for broad questions about a company.
Columns:
  issuer_cik (string), issuer_name (string)
  total_owner_count (bigint) - number of distinct insiders who have actually TRADED this company's stock. Insiders who appear only in empty rows are not counted, so this can be lower than the number of people who filed.
  last_transaction_date (timestamp)
  total_buy_value, total_sell_value (double) - dollar totals, excluding rows where dollar_value_unreliable is true
  total_buy_count, total_sell_count (bigint) - number of transactions, excluding unreliable and empty rows

Table: agg_owner_activity
One row per insider, summarizing their trading activity across companies. Pre-computed,
so prefer this over aggregating fct_transactions yourself for broad questions about a person.
Columns:
  owner_cik (string), owner_name (string)
  last_transaction_date (timestamp)
  total_buy_value, total_sell_value (double) - dollar totals, excluding rows where dollar_value_unreliable is true
  total_buy_count, total_sell_count (bigint) - number of transactions, excluding unreliable and empty rows

General notes:
  - filing_date is a string column, not a native date type. Always compare it as a string.
  - period_of_report and transaction_date are real timestamp columns and can be compared with standard date functions.
  - When counting transactions in fct_transactions, add WHERE is_empty_transaction = false, or the count will include filings that hold no stock trades. A raw count(*) for one company can be several times larger than the number of real trades.
  - For questions about TYPICAL or AGGREGATE trade dollar amounts (totals, averages, "how much did insiders buy this month"), filter with WHERE dollar_value_unreliable = false. The two agg tables already do this.
  - For questions specifically about OUTLIERS, ANOMALIES, or the LARGEST/SMALLEST values ("what's the biggest trade ever", "any suspicious numbers"), do NOT filter out unreliable rows by default. Query across all rows first, since the anomaly itself may be exactly the kind of row dollar_value_unreliable is designed to flag. If you find a large or unusual dollar_value, check its is_debt_security and is_nonstandard_pricing values and explain what they mean as part of your answer, rather than excluding the row before ever seeing it.
  - When you use ORDER BY with a LIMIT, add a tiebreaker column such as accession. Many rows share the same filing_date, so ordering by date alone returns an arbitrary subset and the same query can give different rows each time. Never describe such a result as "the most recent N" unless the sort is unambiguous.
"""