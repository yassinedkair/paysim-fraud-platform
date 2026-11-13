with expected as (
    select count(*) as transactions, count_if(is_fraud) as frauds, sum(amount) as amount
    from {{ ref('stg_transactions') }}
), actual as (
    select count(*) as transactions, count_if(is_fraud) as frauds, sum(amount) as amount
    from {{ ref('fact_transactions') }}
)
select *
from expected cross join actual
where expected.transactions is distinct from actual.transactions
   or expected.frauds is distinct from actual.frauds
   or expected.amount is distinct from actual.amount
