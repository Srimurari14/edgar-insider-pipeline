{{ config(materialized='table') }}

SELECT owner_cik, owner_name FROM (
    SELECT
        owner_cik,
        owner_name,
        ROW_NUMBER() OVER (PARTITION BY owner_cik ORDER BY filing_date DESC) as rn
    FROM {{ ref('stg_form4_transactions') }}
) t
WHERE rn = 1