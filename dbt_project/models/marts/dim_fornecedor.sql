-- Fornecedores vistos em contratos e pagamentos. Tipo 1: guarda só o cadastro mais recente.

with all_suppliers as (
    select supplier_id, supplier_cnpj, supplier_name, _extracted_at
    from {{ ref('stg_contracts') }}
    union all
    select supplier_id, supplier_cnpj, supplier_name, _extracted_at
    from {{ ref('stg_payments') }}
    where supplier_id is not null
),

latest as (
    select distinct on (supplier_id)
        supplier_id     as fornecedor_id,
        supplier_cnpj   as cnpj,
        supplier_name   as razao_social
    from all_suppliers
    order by supplier_id, _extracted_at desc
)

select * from latest
union all
select -1, null, 'Não informado'
