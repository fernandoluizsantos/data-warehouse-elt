-- Marcas vistas em contratos e pagamentos. Tipo 1: nome mais recente.

with all_brands as (
    select brand_id, brand_name, _extracted_at from {{ ref('stg_contracts') }}
    union all
    select brand_id, brand_name, _extracted_at from {{ ref('stg_payments') }}
    where brand_id is not null
),

latest as (
    select distinct on (brand_id)
        brand_id        as marca_id,
        brand_name      as nome_marca
    from all_brands
    order by brand_id, _extracted_at desc
)

select * from latest
union all
select -1, 'Não informado'
