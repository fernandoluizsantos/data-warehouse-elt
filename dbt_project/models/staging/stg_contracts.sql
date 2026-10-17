with source as (
    select * from {{ source('seed_api', 'contracts') }}
),

renamed as (
    select
        -- chave
        id                                                              as contract_id,

        -- contrato
        payload ->> 'contract_code'                                     as contract_code,
        payload ->> 'contract_type'                                     as contract_type,
        payload ->> 'contract_state'                                    as contract_state,
        -- a API mistura "2026" e "30/12/2025": guardamos o texto e o ano extraído
        payload ->> 'contract_validity'                                 as contract_validity_raw,
        right(payload ->> 'contract_validity', 4)::int                  as validity_year,
        nullif(payload ->> 'project_code', '')                          as project_code,

        -- fornecedor (sem telefone, e-mail e dados bancários: LGPD)
        (payload ->> 'supplier__id')::bigint                            as supplier_id,
        payload ->> 'supplier__cpf_cnpj'                                as supplier_cnpj,
        payload ->> 'supplier__corporate_name'                          as supplier_name,

        -- onde o gasto acontece
        (payload ->> 'campus__id')::bigint                              as campus_id,
        payload ->> 'campus__name'                                      as campus_name,
        (payload ->> 'brand__id')::bigint                               as brand_id,
        payload ->> 'brand__name'                                       as brand_name,
        (payload ->> 'budget_allocation__id')::bigint                   as budget_allocation_id,
        payload ->> 'budget_allocation__name'                           as budget_allocation_name,

        -- classificações opcionais
        (payload ->> 'obra_type_fk__id')::bigint                        as obra_type_id,
        payload ->> 'obra_type_fk__name'                                as obra_type_name,
        (payload ->> 'strategic_directorate_fk__id')::bigint            as strategic_directorate_id,
        payload ->> 'strategic_directorate_fk__name'                    as strategic_directorate_name,
        (payload ->> 'amplification_type_fk__id')::bigint               as amplification_type_id,
        payload ->> 'amplification_type_fk__name'                       as amplification_type_name,

        -- pessoas: só ids (e-mails ficam de fora)
        (payload ->> 'created_by__id')::bigint                          as created_by_id,
        (payload ->> 'approver__id')::bigint                            as approver_id,

        -- valores informados pela origem. Renomeados pelo significado real (validado em 99,8%):
        -- "amount_paid" da API = soma do payment_value dos pagamentos NÃO cancelados
        -- (inclui pendentes), ou seja, valor já lançado em pagamentos, não dinheiro pago.
        -- "amount_to_pay" = valor - lançado; zerado quando o contrato é Encerrado/Cancelado.
        (payload ->> 'contract_value')::numeric(14, 2)                  as contract_value,
        (payload ->> 'amount_paid')::numeric(14, 2)                     as amount_committed,
        (payload ->> 'amount_to_pay')::numeric(14, 2)                   as amount_remaining,

        -- datas; aprovação usa a mesma sentinela 2000-01-01 dos pagamentos
        (payload ->> 'creation_date')::timestamptz                      as created_at,
        nullif(
            (payload ->> 'approval_date')::timestamptz,
            '2000-01-01T00:00:00Z'::timestamptz
        )                                                               as approved_at,

        -- checklist de documentos anexados
        (payload ->> 'has_competitor_map')::boolean                     as has_competitor_map,
        (payload ->> 'has_proposals_pdf')::boolean                      as has_proposals_pdf,
        (payload ->> 'has_gestor_email_print')::boolean                 as has_gestor_email_print,
        (payload ->> 'has_classification_print')::boolean               as has_classification_print,
        (payload ->> 'has_compliance_print')::boolean                   as has_compliance_print,
        (payload ->> 'has_fiscal_print')::boolean                       as has_fiscal_print,
        (payload ->> 'has_exception_form')::boolean                     as has_exception_form,

        -- a lista aninhada "payments" fica só no raw: a fonte dos pagamentos é /payments/

        -- metadados da carga
        _extracted_at
    from source
)

select * from renamed
