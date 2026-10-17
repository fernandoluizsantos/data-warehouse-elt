{#
  Log de execução do dbt em audit.dbt_results: uma linha por nó (modelo, snapshot, teste)
  a cada invocação. Funciona igual rodando pelo Dagster ou pelo terminal.

  - create_dbt_results_table: on-run-start (a tabela existe antes dos modelos que a leem)
  - log_dbt_results:          on-run-end (recebe `results`, o resultado de cada nó)
#}

{% macro create_dbt_results_table() %}
    create schema if not exists audit;
    create table if not exists audit.dbt_results (
        invocation_id     text        not null,   -- id da execução do dbt
        run_started_at    timestamptz not null,
        command           text,                   -- build, run, test...
        unique_id         text        not null,   -- ex.: model.dw_contratos.fct_pagamentos
        resource_type     text        not null,   -- model, snapshot, test, seed
        node_name         text        not null,
        status            text        not null,   -- success, error, skipped, pass, warn, fail
        execution_time_s  numeric,
        rows_affected     bigint,                 -- linhas criadas/alteradas (modelos)
        failures          bigint,                 -- linhas que violaram o teste (testes)
        message           text,
        logged_at         timestamptz not null default now()
    );
{% endmacro %}


{% macro log_dbt_results(results) %}
    {% if execute and results | length > 0 %}
        {% set rows = [] %}
        {% for r in results %}
            {% set rows_affected = r.adapter_response.get('rows_affected') if r.adapter_response else none %}
            {% set message = (r.message | string)[:2000] | replace("'", "''") if r.message else none %}
            {% do rows.append(
                "('" ~ invocation_id ~ "', '" ~ run_started_at ~ "', '" ~ flags.WHICH ~ "', '"
                ~ r.node.unique_id ~ "', '" ~ r.node.resource_type ~ "', '" ~ r.node.name ~ "', '"
                ~ r.status ~ "', " ~ (r.execution_time or 0) ~ ", "
                ~ (rows_affected if rows_affected is not none else 'null') ~ ", "
                ~ (r.failures if r.failures is not none else 'null') ~ ", "
                ~ ("'" ~ message ~ "'" if message is not none else 'null') ~ ")"
            ) %}
        {% endfor %}
        {% set insert_sql %}
            insert into audit.dbt_results
                (invocation_id, run_started_at, command, unique_id, resource_type, node_name,
                 status, execution_time_s, rows_affected, failures, message)
            values {{ rows | join(',\n') }}
        {% endset %}
        {% do run_query(insert_sql) %}
        {% do run_query('commit') %}
    {% endif %}
{% endmacro %}
