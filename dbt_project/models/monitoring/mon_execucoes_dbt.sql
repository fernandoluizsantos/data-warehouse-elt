-- Uma linha por execução do dbt: quantos modelos/testes passaram, avisaram ou falharam.

select
    invocation_id,
    min(command)                                                            as comando,
    min(run_started_at)                                                     as iniciado_em,
    (min(run_started_at) at time zone 'America/Sao_Paulo')::date            as data_execucao,
    round(sum(execution_time_s), 1)                                         as duracao_total_s,
    count(*) filter (where resource_type in ('model', 'snapshot'))          as modelos,
    count(*) filter (where resource_type in ('model', 'snapshot') and status = 'success') as modelos_ok,
    count(*) filter (where resource_type in ('model', 'snapshot') and status = 'error')   as modelos_erro,
    count(*) filter (where resource_type = 'test')                          as testes,
    count(*) filter (where resource_type = 'test' and status = 'pass')      as testes_ok,
    count(*) filter (where resource_type = 'test' and status = 'warn')      as testes_aviso,
    count(*) filter (where resource_type = 'test' and status in ('fail', 'error')) as testes_falha,
    count(*) filter (where status = 'skipped')                              as pulados,
    case
        when count(*) filter (where status in ('error', 'fail')) > 0 then 'falha'
        when count(*) filter (where status = 'warn') > 0 then 'sucesso com avisos'
        else 'sucesso'
    end                                                                     as status_geral
from {{ source('audit', 'dbt_results') }}
group by invocation_id
