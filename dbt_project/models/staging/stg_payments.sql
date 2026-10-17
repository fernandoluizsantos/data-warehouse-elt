with source as (
    select * from {{ source('seed_api', 'payments') }}
),

renamed as (
    select
        -- chave
        id                                                              as payment_id,

        -- pagamento
        payload ->> 'payment_code'                                      as payment_code,
        payload ->> 'payment_state'                                     as payment_state,

        -- contrato
        (payload ->> 'contract_code__id')::bigint                       as contract_id,
        payload ->> 'contract_code__contract_code'                      as contract_code,

        -- fornecedor (sem telefone, e-mail e dados bancários: LGPD)
        (payload ->> 'contract_code__supplier__id')::bigint             as supplier_id,
        payload ->> 'contract_code__supplier__cpf_cnpj'                 as supplier_cnpj,
        payload ->> 'contract_code__supplier__corporate_name'           as supplier_name,

        -- onde o gasto aconteceu
        (payload ->> 'contract_code__campus__id')::bigint               as campus_id,
        payload ->> 'contract_code__campus__name'                       as campus_name,
        (payload ->> 'contract_code__brand__id')::bigint                as brand_id,
        payload ->> 'contract_code__brand__name'                        as brand_name,
        (payload ->> 'contract_code__budget_allocation__id')::bigint    as budget_allocation_id,
        payload ->> 'contract_code__budget_allocation__name'            as budget_allocation_name,

        -- valores: numeric, nunca float (float erra centavos)
        (payload ->> 'payment_value')::numeric(14, 2)                   as payment_value,
        (payload ->> 'amount_paid')::numeric(14, 2)                     as amount_paid,

        -- datas: timestamptz entende 'Z' e '-03:00'
        (payload ->> 'creation_date')::timestamptz                      as created_at,
        -- a API manda 2000-01-01 quando ainda não foi pago -> NULL
        nullif(
            (payload ->> 'payment_date')::timestamptz,
            '2000-01-01T00:00:00Z'::timestamptz
        )                                                               as paid_at,
        -- prazo é uma data "pura" (meia-noite UTC): pega só a parte da data do texto,
        -- para o fuso da sessão não empurrar o dia para trás. Também usa a sentinela.
        nullif(left(payload ->> 'payment_deadline', 10)::date, '2000-01-01'::date) as due_date,
        (payload ->> 'last_update_date')::timestamptz                   as updated_at,

        -- metadados da carga
        _extracted_at
    from source
),

flagged as (
    select
        *,
        -- amount_paid incoerente com o estado (ex.: digitado 100x maior, cancelado com valor pago).
        -- O registro fica no staging; os marts o excluem das métricas.
        case
            when payment_state = 'Pago' then amount_paid <> payment_value
            else amount_paid > 0
        end                                                             as has_amount_inconsistency
    from renamed
)

select * from flagged
