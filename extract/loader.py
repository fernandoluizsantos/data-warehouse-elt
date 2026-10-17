"""Carga lake -> Postgres (schema raw), idempotente via upsert por id."""
import json
from dataclasses import dataclass

import psycopg
from psycopg import sql

from extract.config import Entity


def ensure_tables(conn: psycopg.Connection, entity: Entity) -> None:
    conn.execute(sql.SQL("""
        CREATE TABLE IF NOT EXISTS raw.{table} (
            id             bigint PRIMARY KEY,
            payload        jsonb       NOT NULL,   -- registro exatamente como veio da API
            _extracted_at  timestamptz NOT NULL,
            _source        text        NOT NULL,
            _run_id        uuid        NOT NULL,
            _lake_key      text        NOT NULL,   -- arquivo de origem no lake (rastreabilidade)
            _loaded_at     timestamptz NOT NULL DEFAULT now()
        )
    """).format(table=sql.Identifier(entity.name)))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit.extraction_runs (
            run_id             uuid PRIMARY KEY,
            entity             text        NOT NULL,
            source             text        NOT NULL,
            last_id_param      bigint      NOT NULL,
            started_at         timestamptz NOT NULL,
            finished_at        timestamptz,
            status             text        NOT NULL,   -- running | success | failed
            records_extracted  integer     NOT NULL DEFAULT 0,
            files_written      integer     NOT NULL DEFAULT 0,
            rows_inserted      integer     NOT NULL DEFAULT 0,
            rows_updated       integer     NOT NULL DEFAULT 0,
            error              text
        )
    """)
    conn.commit()


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


def load_batch(conn: psycopg.Connection, entity: Entity, batch: dict, lake_key: str) -> LoadResult:
    """Carrega um arquivo do lake. Rodar duas vezes o mesmo arquivo não muda nada."""
    # Se o mesmo id aparecer duas vezes no lote, fica a última ocorrência
    # (ON CONFLICT não pode alterar a mesma linha duas vezes no mesmo comando).
    records = {int(r["id"]): r for r in batch["data"]}
    table = sql.Identifier(entity.name)

    with conn.transaction():
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS _incoming (id bigint, payload jsonb)")
        conn.execute("TRUNCATE _incoming")
        with conn.cursor().copy("COPY _incoming (id, payload) FROM STDIN") as copy:
            for rid, rec in records.items():
                copy.write_row((rid, json.dumps(rec, ensure_ascii=False)))

        rows = conn.execute(sql.SQL("""
            INSERT INTO raw.{table} AS t (id, payload, _extracted_at, _source, _run_id, _lake_key)
            SELECT id, payload, %(extracted_at)s, %(source)s, %(run_id)s, %(lake_key)s
            FROM _incoming
            ON CONFLICT (id) DO UPDATE SET
                payload       = EXCLUDED.payload,
                _extracted_at = EXCLUDED._extracted_at,
                _source       = EXCLUDED._source,
                _run_id       = EXCLUDED._run_id,
                _lake_key     = EXCLUDED._lake_key,
                _loaded_at    = now()
            -- só atualiza se o dado mudou E se o arquivo não é mais antigo que o já carregado
            WHERE t.payload IS DISTINCT FROM EXCLUDED.payload
              AND t._extracted_at <= EXCLUDED._extracted_at
            RETURNING (xmax = 0) AS inserted
        """).format(table=table), {
            "extracted_at": batch["_extracted_at"],
            "source": batch["_source"],
            "run_id": batch["_run_id"],
            "lake_key": lake_key,
        }).fetchall()
    conn.commit()  # cada arquivo do lake é uma unidade de carga

    inserted = sum(1 for (ins,) in rows if ins)
    updated = len(rows) - inserted
    return LoadResult(inserted, updated, len(records) - inserted - updated)
