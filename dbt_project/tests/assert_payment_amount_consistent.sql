-- Relatório de qualidade: pagamentos cujo amount_paid não condiz com o estado.
-- Severidade warn: não bloqueia o pipeline, mas aparece em todo dbt test/build.
-- Use a lista para pedir correção na origem (SEED).
{{ config(severity='warn') }}

select
    payment_id,
    payment_code,
    payment_state,
    payment_value,
    amount_paid,
    amount_paid - payment_value as diferenca
from {{ ref('stg_payments') }}
where has_amount_inconsistency
