"""Ponto de entrada: extrai da API (ou fonte sintética) para o lake e carrega no raw.

Uso:
    python -m extract.main --entity payments                  # full (padrão): last_id=1
    python -m extract.main --entity payments --incremental    # last_id calculado pelo estado

Padrão é full: a API devolve tudo em ~13s e o incremental com janela perdia mudanças de
pagamentos pendentes antigos (ver docs/02-extracao.md). O incremental fica disponível para
quando o volume crescer.
"""
import argparse
import logging
import time
import uuid
from datetime import datetime, timezone

import psycopg

from extract import lake, loader, state
from extract.api_client import SeedClient
from extract.config import ENTITIES, Entity, Settings, get_settings
from extract.synthetic import SyntheticSource

log = logging.getLogger("extract")


def make_source(settings: Settings, entity: Entity):
    if settings.use_synthetic:
        if entity.name != "payments":
            # TODO: fonte sintética de contratos (pendente, necessária antes de publicar)
            raise NotImplementedError(f"Modo sintético ainda não suporta '{entity.name}'")
        return SyntheticSource(), "synthetic"
    if not settings.api_email or not settings.api_password:
        raise RuntimeError("Defina API_EMAIL e API_PASSWORD no .env (ou USE_SYNTHETIC_DATA=true)")
    client = SeedClient(settings.api_base_url, settings.api_email, settings.api_password)
    return client, settings.api_base_url


def extract_to_lake(settings: Settings, entity: Entity, last_id: int, run_id: str, s3) -> tuple[list[str], int]:
    """Extrai a partir de last_id e grava cada lote no lake. Retorna (chaves, nº de registros)."""
    source, source_name = make_source(settings, entity)
    keys: list[str] = []
    total = 0
    try:
        for batch_number, (used_last_id, records) in enumerate(source.fetch_since(entity.endpoint, last_id), 1):
            key = lake.write_batch(
                s3, settings.s3_bucket, entity.name, records,
                extracted_at=datetime.now(timezone.utc), source=source_name, run_id=run_id,
                batch_number=batch_number, last_id_param=used_last_id,
            )
            keys.append(key)
            total += len(records)
            log.info("Lote %s: %s registros (last_id=%s) -> s3://%s/%s",
                     batch_number, len(records), used_last_id, settings.s3_bucket, key)
    finally:
        source.close()
    return keys, total


def load_from_lake(conn, settings: Settings, entity: Entity, keys: list[str], s3) -> loader.LoadResult:
    result = loader.LoadResult()
    for key in keys:
        r = loader.load_batch(conn, entity, lake.read_batch(s3, settings.s3_bucket, key), key)
        result.inserted += r.inserted
        result.updated += r.updated
        result.unchanged += r.unchanged
    return result


def run(entity_name: str, full: bool = True) -> dict:
    settings = get_settings()
    entity = ENTITIES[entity_name]
    s3 = lake.s3_client(settings)
    run_id = str(uuid.uuid4())
    started = time.monotonic()

    with psycopg.connect(settings.pg_conninfo) as conn:
        loader.ensure_tables(conn, entity)
        last_id = 1 if full else state.next_last_id(conn, entity, settings.reextract_max_ids)
        source_name = "synthetic" if settings.use_synthetic else settings.api_base_url
        log.info("Run %s | entidade=%s | fonte=%s | last_id=%s", run_id, entity.name, source_name, last_id)

        conn.execute("""
            INSERT INTO audit.extraction_runs (run_id, entity, source, last_id_param, started_at, status)
            VALUES (%s, %s, %s, %s, now(), 'running')
        """, (run_id, entity.name, source_name, last_id))
        conn.commit()

        try:
            keys, extracted = extract_to_lake(settings, entity, last_id, run_id, s3)
            result = load_from_lake(conn, settings, entity, keys, s3)
        except Exception as exc:
            conn.rollback()
            conn.execute("""
                UPDATE audit.extraction_runs SET status='failed', finished_at=now(), error=%s WHERE run_id=%s
            """, (str(exc)[:2000], run_id))
            conn.commit()
            raise

        conn.execute("""
            UPDATE audit.extraction_runs
            SET status='success', finished_at=now(), records_extracted=%s, files_written=%s,
                rows_inserted=%s, rows_updated=%s
            WHERE run_id=%s
        """, (extracted, len(keys), result.inserted, result.updated, run_id))
        conn.commit()

    summary = {
        "run_id": run_id,
        "entity": entity.name,
        "source": source_name,
        "last_id": last_id,
        "duration_s": round(time.monotonic() - started, 1),
        "extracted": extracted,
        "files": len(keys),
        "inserted": result.inserted,
        "updated": result.updated,
        "unchanged": result.unchanged,
    }
    log.info("Concluído em %.1fs | extraídos=%s arquivos=%s inseridos=%s atualizados=%s inalterados=%s",
             summary["duration_s"], extracted, len(keys), result.inserted, result.updated, result.unchanged)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extração API -> lake -> Postgres raw")
    parser.add_argument("--entity", choices=sorted(ENTITIES), required=True)
    parser.add_argument("--incremental", action="store_true",
                        help="usa o last_id calculado pelo estado em vez de extrair tudo")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(args.entity, full=not args.incremental)


if __name__ == "__main__":
    main()
