"""Checagens de qualidade no Dagster.

1. Volume da extração (asset checks bloqueantes): compara o total extraído com a extração
   bem-sucedida anterior em audit.extraction_runs.
     - queda > 10%            -> WARN  (avisa, o pipeline segue)
     - queda > 50% ou zero    -> ERROR (bloqueia o dbt: dado quebrado não chega ao dashboard)
   Como a extração é full, o volume só deveria crescer; uma queda grande indica API devolvendo
   resposta parcial, filtro errado, credencial com menos permissão etc.

Freshness (fatos sem atualizar há mais de 26h) fica em orchestration/dbt_assets.py,
como FreshnessPolicy anexada aos assets das fatos.
"""
import psycopg
from dagster import AssetCheckResult, AssetCheckSeverity, asset_check

from extract.config import get_settings
from orchestration.extract_assets import raw_contracts, raw_payments

WARN_DROP = 0.10
ERROR_DROP = 0.50


def _volume_check(entity: str) -> AssetCheckResult:
    with psycopg.connect(get_settings().pg_conninfo) as conn:
        rows = conn.execute(
            """
            WITH latest AS (
                SELECT source FROM audit.extraction_runs
                WHERE entity = %(entity)s AND status = 'success'
                ORDER BY started_at DESC LIMIT 1
            )
            SELECT records_extracted
            FROM audit.extraction_runs
            WHERE entity = %(entity)s AND status = 'success'
              AND source = (SELECT source FROM latest)  -- não compara sintético com real
            ORDER BY started_at DESC
            LIMIT 2
            """,
            {"entity": entity},
        ).fetchall()

    if not rows:
        return AssetCheckResult(passed=False, severity=AssetCheckSeverity.ERROR,
                                description="Nenhuma extração bem-sucedida registrada.")
    current = rows[0][0]
    if len(rows) == 1:
        return AssetCheckResult(passed=current > 0, metadata={"registros": current},
                                description="Primeira extração: sem base de comparação.")

    previous = rows[1][0]
    variation = (current - previous) / previous if previous else 0.0
    metadata = {"registros": current, "registros_anteriores": previous,
                "variacao_pct": round(variation * 100, 2)}

    if current == 0 or variation <= -ERROR_DROP:
        return AssetCheckResult(passed=False, severity=AssetCheckSeverity.ERROR, metadata=metadata,
                                description=f"Queda de volume grave ({variation:.1%}). dbt bloqueado.")
    if variation <= -WARN_DROP:
        return AssetCheckResult(passed=False, severity=AssetCheckSeverity.WARN, metadata=metadata,
                                description=f"Queda de volume ({variation:.1%}).")
    return AssetCheckResult(passed=True, metadata=metadata)


@asset_check(asset=raw_contracts, blocking=True, description="Volume extraído x extração anterior.")
def contracts_volume_check() -> AssetCheckResult:
    return _volume_check("contracts")


@asset_check(asset=raw_payments, blocking=True, description="Volume extraído x extração anterior.")
def payments_volume_check() -> AssetCheckResult:
    return _volume_check("payments")


volume_checks = [contracts_volume_check, payments_volume_check]
