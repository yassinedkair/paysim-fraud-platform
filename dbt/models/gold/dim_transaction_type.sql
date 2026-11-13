select distinct transaction_type
from {{ ref('stg_transactions') }}
