-- Campus vistos em contratos e pagamentos. Tipo 1: nome mais recente.

with all_campus as (
    select campus_id, campus_name, _extracted_at from {{ ref('stg_contracts') }}
    union all
    select campus_id, campus_name, _extracted_at from {{ ref('stg_payments') }}
    where campus_id is not null
),

latest as (
    select distinct on (campus_id)
        campus_id       as campus_id,
        campus_name     as nome_campus
    from all_campus
    order by campus_id, _extracted_at desc
)

select * from latest
union all
select -1, 'Não informado'
