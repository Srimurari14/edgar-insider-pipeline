{{ config(materialized='table') }}

SELECT
    filing_date,
    accession,
    period_of_report,
    document_type,
    issuer_cik, 
    issuer_name, 
    issuer_trading_symbol,
    owner_cik,
    owner_name, 
    is_director,
    is_officer, 
    is_ten_percent_owner,
    is_other,
    officer_title,
    other_text,
    security_title, 
    transaction_date,
    transaction_code,
    transaction_shares,
    transaction_price_per_share,
    acquired_disposed_code,
    shares_owned_after,
    ownership_type,
    CASE 
        WHEN transaction_code = 'P' THEN 'Buy'
        WHEN transaction_code = 'S' THEN 'Sell'
        WHEN transaction_code = 'U' THEN 'Merger Disposition'
        ELSE 'Other'
    END AS transaction_classification,
    transaction_shares * transaction_price_per_share as dollar_value,
    CASE 
        WHEN security_title LIKE '%Notes%' OR security_title LIKE '%Bond%' 
            OR security_title LIKE '%Debenture%' OR REGEXP_LIKE(security_title, '[0-9]+\.[0-9]+%')
        THEN true ELSE false
    END AS is_debt_security,
    CASE 
        WHEN transaction_code = 'J' THEN true 
        ELSE false 
    END AS is_nonstandard_pricing,
    CASE 
        WHEN security_title LIKE '%Notes%' OR security_title LIKE '%Bond%' 
            OR security_title LIKE '%Debenture%' OR REGEXP_LIKE(security_title, '[0-9]+\.[0-9]+%')
            OR transaction_code = 'J'
        THEN true ELSE false
    END AS dollar_value_unreliable
FROM {{ref('stg_form4_transactions')}}
