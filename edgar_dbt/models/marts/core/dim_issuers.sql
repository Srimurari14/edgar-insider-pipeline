{{ config(materialized='table') }}

SELECT issuer_cik, 
    issuer_name, 
    issuer_trading_symbol FROM (
SELECT
    issuer_cik, 
    issuer_name, 
    issuer_trading_symbol,
    ROW_NUMBER() OVER (PARTITION BY issuer_cik ORDER BY filing_date DESC) as rn
FROM {{ref('stg_form4_transactions')}}) t
WHERE rn=1
