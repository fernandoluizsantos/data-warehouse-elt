-- Relatório de qualidade: o valor lançado do contrato (amount_committed, "amount_paid" na API)
-- deve ser a soma do payment_value dos seus pagamentos não cancelados.
-- Regra validada em 99,8% dos contratos; o restante é divergência entre os dois endpoints.
{{ config(severity='warn') }}

with committed_by_contract as (
    select
        contract_id,
        sum(payment_value) as payments_committed
    from {{ ref('stg_payments') }}
    where contract_id is not null
      and payment_state <> 'Cancelado'
    group by 1
)

select
    c.contract_id,
    c.contract_code,
    c.contract_state,
    c.amount_committed,
    coalesce(p.payments_committed, 0)                       as payments_committed,
    c.amount_committed - coalesce(p.payments_committed, 0)  as diferenca
from {{ ref('stg_contracts') }} as c
left join committed_by_contract as p using (contract_id)
where abs(c.amount_committed - coalesce(p.payments_committed, 0)) > 0.01
