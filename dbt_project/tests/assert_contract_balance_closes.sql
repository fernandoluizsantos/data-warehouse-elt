-- Relatório de qualidade: contratos abertos em que valor - lançado <> saldo (tolerância 1 centavo).
-- Encerrados/Cancelados ficam de fora: a origem zera o saldo deles por regra de negócio.
{{ config(severity='warn') }}

select
    contract_id,
    contract_code,
    contract_state,
    contract_value,
    amount_committed,
    amount_remaining,
    contract_value - amount_committed - amount_remaining as diferenca
from {{ ref('stg_contracts') }}
where contract_state not in ('Encerrado', 'Cancelado')
  and abs(contract_value - amount_committed - amount_remaining) > 0.01
