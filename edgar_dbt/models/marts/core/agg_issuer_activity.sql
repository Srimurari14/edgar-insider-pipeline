{{ config(materialized='table') }}

SELECT 
    f.issuer_cik,
    d.issuer_name,
    COUNT(DISTINCT owner_cik) as total_owner_count,
    max(transaction_date) as last_transaction_date,
    SUM(CASE WHEN transaction_classification = 'Buy' AND is_debt_security = false 
        THEN dollar_value ELSE 0 END) AS total_buy_value,
    Count(CASE WHEN transaction_classification = 'Buy' AND is_debt_security = false 
        THEN 1 END) AS total_buy_count,
    SUM(CASE WHEN transaction_classification = 'Sell' AND is_debt_security = false 
        THEN dollar_value ELSE 0 END) AS total_sell_value,
    Count(CASE WHEN transaction_classification = 'Sell' AND is_debt_security = false 
        THEN 1 END) AS total_sell_count
FROM 
    {{ref('fct_transactions')}} f
JOIN 
    {{ref('dim_issuers')}} d
ON f.issuer_cik = d.issuer_cik
GROUP BY 1,2 