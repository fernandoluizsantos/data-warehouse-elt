"""Assets de extração e carga: API -> lake -> Postgres raw.

As chaves ["seed_api", "<entidade>"] são as mesmas que o dagster-dbt dá às sources do
dbt (source 'seed_api', tabelas 'payments'/'contracts'). Assim o Dagster liga sozinho
a extração aos modelos dbt que leem essas tabelas.
"""
from dagster import AssetExecutionContext, Backoff, MaterializeResult, RetryPolicy, asset

from extract.main import run

# A API pode falhar ou recusar por instantes: tenta de novo com espera crescente (60s, 120s, 240s).
# O retry do httpx (extract/api_client.py) cobre falhas de uma requisição; este cobre o asset inteiro.
EXTRACT_RETRY = RetryPolicy(max_retries=3, delay=60, backoff=Backoff.EXPONENTIAL)


def _materialize(context: AssetExecutionContext, entity: str) -> MaterializeResult:
    summary = run(entity, full=True)
    context.log.info(f"Resumo da extração: {summary}")
    return MaterializeResult(
        metadata={
            "registros_extraidos": summary["extracted"],
            "inseridos": summary["inserted"],
            "atualizados": summary["updated"],
            "inalterados": summary["unchanged"],
            "arquivos_no_lake": summary["files"],
            "duracao_s": summary["duration_s"],
            "fonte": summary["source"],
            "run_id_extracao": summary["run_id"],
        }
    )


@asset(
    key=["seed_api", "contracts"],
    group_name="extracao",
    description="Contratos: API SEED -> lake (raw/contracts/...) -> Postgres raw.contracts (upsert).",
    retry_policy=EXTRACT_RETRY,
    kinds={"python", "s3", "postgres"},
)
def raw_contracts(context: AssetExecutionContext) -> MaterializeResult:
    return _materialize(context, "contracts")


@asset(
    key=["seed_api", "payments"],
    group_name="extracao",
    description="Pagamentos: API SEED -> lake (raw/payments/...) -> Postgres raw.payments (upsert).",
    retry_policy=EXTRACT_RETRY,
    kinds={"python", "s3", "postgres"},
)
def raw_payments(context: AssetExecutionContext) -> MaterializeResult:
    return _materialize(context, "payments")
