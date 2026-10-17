-- Executado só na primeira criação do volume do Postgres.
-- Roda dentro do banco POSTGRES_DB (o DW).

-- Camadas do DW
CREATE SCHEMA IF NOT EXISTS raw;        -- dado bruto carregado do lake
CREATE SCHEMA IF NOT EXISTS staging;    -- dbt: limpeza e padronização
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;      -- dbt: modelo dimensional
CREATE SCHEMA IF NOT EXISTS audit;      -- logs de execução
CREATE SCHEMA IF NOT EXISTS monitoring; -- dbt: visões de saúde do pipeline

-- Banco separado para os metadados do Metabase (isolado do DW)
CREATE DATABASE metabase;
