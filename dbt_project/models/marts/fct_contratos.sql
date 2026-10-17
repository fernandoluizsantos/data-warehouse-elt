-- Fato de contratos (accumulating snapshot). Granularidade: 1 linha por contrato, estado atual.
-- Valores pagos vêm de int_pagamentos_por_contrato (mesma regra da fct_pagamentos).

with contracts as (
    select * from {{ ref('stg_contracts') }}
),

payments as (
    select * from {{ ref('int_pagamentos_por_contrato') }}
),

current_version as (
    select contrato_sk, contrato_id
    from {{ ref('dim_contrato') }}
    where versao_atual
),

final as (
    select
        c.contract_id                                                   as contrato_id,
        v.contrato_sk,

        -- chaves das dimensões
        c.supplier_id                                                   as fornecedor_id,
        c.campus_id,
        c.brand_id                                                      as marca_id,
        c.budget_allocation_id                                          as verba_id,
        to_char(c.created_at at time zone 'America/Sao_Paulo', 'YYYYMMDD')::int     as data_criacao_key,
        coalesce(to_char(c.approved_at at time zone 'America/Sao_Paulo', 'YYYYMMDD')::int, -1)
                                                                        as data_aprovacao_key,

        -- atributo usado nas regras abaixo (detalhes do contrato ficam na dim_contrato)
        c.contract_state                                                as estado_contrato,

        -- medidas
        c.contract_value                                                as valor_contratado,
        coalesce(p.valor_pago, 0)                                       as valor_pago,
        coalesce(p.valor_pendente, 0)                                   as valor_pendente,
        coalesce(p.valor_cancelado, 0)                                  as valor_cancelado,
        coalesce(p.qtd_pagamentos, 0)                                   as qtd_pagamentos,
        -- valor lançado segundo a própria origem ("amount_paid" da API)
        c.amount_committed                                              as valor_comprometido_origem,
        -- saldo só existe para contrato aprovado e em andamento; encerrados/cancelados
        -- têm a sobra liberada pela origem, e não aprovados ainda não geram obrigação
        case when c.contract_state = 'Aprovado'
             then c.contract_value - coalesce(p.valor_pago, 0)
             else 0
        end                                                             as saldo
    from contracts as c
    left join payments as p using (contract_id)
    left join current_version as v on v.contrato_id = c.contract_id
)

select * from final
