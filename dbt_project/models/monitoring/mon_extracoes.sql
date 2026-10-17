-- Uma linha por extração, com a variação de volume em relação à extração anterior bem-sucedida.

with runs as (
    select * from {{ source('audit', 'extraction_runs') }}
),

-- volume da extração bem-sucedida anterior (falhas não entram na comparação)
successes as (
    select
        run_id,
        -- por entidade E fonte: não compara extração sintética com a real
        lag(records_extracted) over (partition by entity, source order by started_at) as registros_anteriores
    from runs
    where status = 'success'
)

select
    r.run_id,
    r.entity                                                            as entidade,
    r.source                                                            as fonte,
    r.status,
    r.started_at                                                        as iniciado_em,
    (r.started_at at time zone 'America/Sao_Paulo')::date               as data_execucao,
    round(extract(epoch from r.finished_at - r.started_at)::numeric, 1) as duracao_s,
    r.last_id_param                                                     as last_id,
    r.records_extracted                                                 as registros_extraidos,
    r.rows_inserted                                                     as linhas_inseridas,
    r.rows_updated                                                      as linhas_atualizadas,
    s.registros_anteriores,
    case when s.registros_anteriores > 0
         then round(100.0 * (r.records_extracted - s.registros_anteriores) / s.registros_anteriores, 2)
    end                                                                 as variacao_volume_pct,
    r.error                                                             as erro
from runs as r
left join successes as s using (run_id)
