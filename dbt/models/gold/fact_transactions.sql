select
    transaction_id,
    simulation_hour,
    simulation_day,
    transaction_type,
    amount,
    is_fraud
from {{ ref('stg_transactions') }}
