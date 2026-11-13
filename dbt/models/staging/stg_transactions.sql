{% set silver_path = env_var('FRAUD_SILVER_PATH', 'data/silver/16910f90577b0d981bf8ff289714510bb89bc71bff7d3f220f024e287e4eea6b.parquet') %}

select
    transaction_id,
    step as simulation_hour,
    (step - 1) // 24 + 1 as simulation_day,
    type as transaction_type,
    amount,
    isFraud as is_fraud
from read_parquet('{{ silver_path | replace("'", "''") }}')
