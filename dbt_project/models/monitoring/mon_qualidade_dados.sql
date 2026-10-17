-- Histórico de cada teste do dbt: status e quantidade de registros com problema por execução.
-- Permite acompanhar a tendência (ex.: os 348 pagamentos inconsistentes estão diminuindo?).

select
    r.invocation_id,
    r.run_started_at                                                as executado_em,
    (r.run_started_at at time zone 'America/Sao_Paulo')::date       as data_execucao,
    r.node_name                                                     as teste,
    r.status,
    coalesce(r.failures, 0)                                         as registros_com_problema,
    -- testes de qualidade conhecidos (severity warn) x quebras de pipeline (error)
    case
        when r.status = 'pass' then 'ok'
        when r.status = 'warn' then 'aviso'
        else 'falha'
    end                                                             as gravidade,
    -- a execução mais recente de cada teste, para o painel "situação atual"
    r.run_started_at = max(r.run_started_at) over (partition by r.node_name) as execucao_mais_recente
from {{ source('audit', 'dbt_results') }} as r
where r.resource_type = 'test'
