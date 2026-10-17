{#
  Por padrão o dbt cria "<schema do profile>_<schema custom>" (ex.: analytics_staging).
  Aqui usamos o schema custom direto (staging, intermediate, marts), que são os
  schemas criados no init do Postgres.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
