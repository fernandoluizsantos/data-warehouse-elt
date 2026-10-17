-- Fato de pagamentos. Granularidade: 1 linha por pagamento.
-- Incremental: processa só pagamentos que mudaram desde a última execução (_extracted_at só
-- avança no raw quando o payload muda — ver extract/loader.py).
--
-- Pagamentos com amount_paid incoerente ficam FORA da fato. Num modelo incremental não basta
-- filtrá-los na entrada: um pagamento já carregado que passe a ser incoerente precisa sair.
-- Por isso eles entram no lote e o post_hook os apaga ao final.
{{
    config(
        materialized='incremental',
        unique_key='pagamento_id',
        incremental_strategy='delete+insert',
        on_schema_change='append_new_columns',
        post_hook="delete from {{ this }} where possui_inconsistencia_valor"
    )
}}

with payments as (
    select *
    from {{ ref('stg_payments') }}
    {% if is_incremental() %}
    where _extracted_at > (select coalesce(max(_extracted_at), '1900-01-01') from {{ this }})
    {% endif %}
),

contracts as (
    select contrato_sk, contrato_id, valido_de, valido_ate
    from {{ ref('dim_contrato') }}
),

final as (
    select
        -- chave e atributos degenerados (não viram dimensão própria)
        p.payment_id                                                    as pagamento_id,
        p.payment_code                                                  as codigo_pagamento,
        p.payment_state                                                 as estado_pagamento,

        -- chaves das dimensões (-1 = membro desconhecido)
        -- versão do contrato vigente quando o pagamento foi criado (SCD2)
        coalesce(c.contrato_sk, '-1')                                   as contrato_sk,
        coalesce(p.contract_id, -1)                                     as contrato_id,
        coalesce(p.supplier_id, -1)                                     as fornecedor_id,
        coalesce(p.campus_id, -1)                                       as campus_id,
        coalesce(p.brand_id, -1)                                        as marca_id,
        coalesce(p.budget_allocation_id, -1)                            as verba_id,

        -- datas (role-playing da dim_data); o dia é o de Brasília
        to_char(p.created_at at time zone 'America/Sao_Paulo', 'YYYYMMDD')::int     as data_criacao_key,
        coalesce(to_char(p.paid_at at time zone 'America/Sao_Paulo', 'YYYYMMDD')::int, -1)
                                                                        as data_pagamento_key,
        coalesce(to_char(p.due_date, 'YYYYMMDD')::int, -1)              as data_vencimento_key,

        -- medidas
        p.payment_value                                                 as valor_pagamento,
        case when p.payment_state = 'Pago' then p.payment_value else 0 end              as valor_pago,
        case when p.payment_state = 'Pendente Pagamento' then p.payment_value else 0 end as valor_pendente,
        case when p.payment_state = 'Cancelado' then p.payment_value else 0 end         as valor_cancelado,

        -- controle
        p.has_amount_inconsistency                                      as possui_inconsistencia_valor,
        p._extracted_at
    from payments as p
    left join contracts as c
        on  c.contrato_id = p.contract_id
        and (p.created_at at time zone 'UTC') >= c.valido_de
        and (p.created_at at time zone 'UTC') <  c.valido_ate
)

select * from final
