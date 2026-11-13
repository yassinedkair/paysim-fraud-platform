select distinct simulation_day
from {{ ref('stg_transactions') }}
