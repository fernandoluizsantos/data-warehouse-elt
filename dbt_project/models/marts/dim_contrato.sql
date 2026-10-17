-- Dimensão de contrato com histórico (SCD2), a partir do snapshot.
-- Uma linha por VERSÃO do contrato; contrato_sk identifica a versão.

with versions as (
    select
        *,
        row_number() over (partition by contract_id order by dbt_valid_from) as version_number
    from {{ ref('snap_contracts') }}
),

contracts as (
    select
        dbt_scd_id                                          as contrato_sk,
        contract_id                                         as contrato_id,
        contract_code                                       as codigo_contrato,
        contract_type                                       as tipo_contrato,
        contract_state                                      as estado_contrato,
        validity_year                                       as ano_vigencia,
        project_code                                        as codigo_projeto,
        coalesce(obra_type_name, 'Não se aplica')           as tipo_obra,
        coalesce(strategic_directorate_name, 'Não se aplica') as diretoria_estrategica,
        coalesce(amplification_type_name, 'Não se aplica')  as tipo_ampliacao,
        version_number                                      as versao,
        -- o histórico só começa no 1º snapshot; a 1ª versão "vale desde sempre"
        -- para que fatos antigas encontrem uma versão no join por data
        case when version_number = 1
             then '1900-01-01'::timestamp
             else dbt_valid_from
        end                                                 as valido_de,
        dbt_valid_to                                        as valido_ate,
        dbt_valid_to = '9999-12-31'::timestamp              as versao_atual
    from versions
),

unknown as (
    select
        '-1'                        as contrato_sk,
        -1::bigint                  as contrato_id,
        'Sem contrato'              as codigo_contrato,
        'Não informado'             as tipo_contrato,
        'Não informado'             as estado_contrato,
        null::int                   as ano_vigencia,
        null::text                  as codigo_projeto,
        'Não se aplica'             as tipo_obra,
        'Não se aplica'             as diretoria_estrategica,
        'Não se aplica'             as tipo_ampliacao,
        1::bigint                   as versao,
        '1900-01-01'::timestamp     as valido_de,
        '9999-12-31'::timestamp     as valido_ate,
        true                        as versao_atual
)

select * from contracts
union all
select * from unknown
