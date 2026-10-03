{{ config(materialized='table') }}

SELECT 
    f.owner_cik,
    d.owner_name,
    max(transaction_date) as last_transaction_date,
    SUM(CASE WHEN transaction_classification = 'Buy' AND dollar_value_unreliable = false 
        THEN dollar_value ELSE 0 END) AS total_buy_value,
    Count(CASE WHEN transaction_classification = 'Buy' AND dollar_value_unreliable = false 
        AND is_empty_transaction = false
        THEN 1 END) AS total_buy_count,
    SUM(CASE WHEN transaction_classification = 'Sell' AND dollar_value_unreliable = false 
        THEN dollar_value ELSE 0 END) AS total_sell_value,
    Count(CASE WHEN transaction_classification = 'Sell' AND dollar_value_unreliable = false 
        AND is_empty_transaction = false
        THEN 1 END) AS total_sell_count
FROM 
    {{ref('fct_transactions')}} f
JOIN 
    {{ref('dim_owners')}} d
ON f.owner_cik = d.owner_cik
GROUP BY 1,2