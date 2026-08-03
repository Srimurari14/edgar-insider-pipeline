CREATE EXTERNAL TABLE edgar_form4.silver_form4_transactions ( accession string,
                                                             period_of_repor timestamp,
                                                             document_type string,
                                                             issuer_cik string, 
                                                             issuer_name string, 
                                                             issuer_trading_symbol string,
                                                             owner_cik string,
                                                             owner_name string, 
                                                             is_director boolean,
                                                             is_officer boolean, 
                                                             is_ten_percent_owner boolean,
                                                             is_other boolean,
                                                             officer_title string,
                                                             other_text string,
                                                             security_title string, 
                                                             transaction_date timestamp,
                                                             transaction_code string,
                                                             transaction_shares double,
                                                             transaction_price_per_share double,
                                                             acquired_disposed_code string,
                                                             shares_owned_after double,
                                                             ownership_type string)
                                                             PARTITIONED BY (filing_date string)
                                                             STORED AS PARQUET
                                                             LOCATION 's3://edgar-form4-sri/silver/form4/'
                                                             TBLPROPERTIES ('parquet.compression'='SNAPPY');