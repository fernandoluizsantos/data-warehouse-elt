#!/bin/sh
# Usuário somente leitura para o Metabase. Roda só na criação do volume.
# As permissões de SELECT nas tabelas do schema marts são dadas pelo dbt (config `grants`),
# porque o dbt recria as tabelas a cada execução.
set -e

if [ -z "$METABASE_READER_PASSWORD" ]; then
  echo "METABASE_READER_PASSWORD não definido; usuário metabase_reader não criado"
  exit 0
fi

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v pw="$METABASE_READER_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE metabase_reader LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE :"db" TO metabase_reader;
GRANT USAGE ON SCHEMA marts TO metabase_reader;
GRANT USAGE ON SCHEMA monitoring TO metabase_reader;
SQL
