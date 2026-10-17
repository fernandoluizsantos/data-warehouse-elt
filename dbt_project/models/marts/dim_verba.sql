-- Verbas (budget allocation) vistas em contratos e pagamentos. Tipo 1: nome mais recente.

with all_budgets as (
    select budget_allocation_id, budget_allocation_name, _extracted_at from {{ ref('stg_contracts') }}
    union all
    select budget_allocation_id, budget_allocation_name, _extracted_at from {{ ref('stg_payments') }}
    where budget_allocation_id is not null
),

latest as (
    select distinct on (budget_allocation_id)
        budget_allocation_id    as verba_id,
        budget_allocation_name  as nome_verba
    from all_budgets
    order by budget_allocation_id, _extracted_at desc
)

select * from latest
union all
select -1, 'Não informado'
