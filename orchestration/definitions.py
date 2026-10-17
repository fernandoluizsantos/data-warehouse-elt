"""Ponto de entrada do Dagster: junta assets, checks, recursos, job e agendamento.

Rodar (na raiz do projeto, com o .venv ativo):
    dagster dev -p 3001
"""
from dagster import AssetSelection, Definitions, ScheduleDefinition, define_asset_job

from orchestration.dbt_assets import dbt_resource, dw_dbt_models
from orchestration.extract_assets import raw_contracts, raw_payments
from orchestration.quality_checks import volume_checks

# Pipeline completo: extrações (em paralelo) -> checks de volume -> dbt build (+ testes)
atualiza_dw_job = define_asset_job(
    name="atualiza_dw",
    selection=AssetSelection.all(),
    description="Extrai contratos e pagamentos e reconstrói o DW com dbt (build + testes).",
)

atualiza_dw_diario = ScheduleDefinition(
    name="atualiza_dw_diario",
    job=atualiza_dw_job,
    cron_schedule="0 6 * * *",           # todo dia às 06:00
    execution_timezone="America/Sao_Paulo",
)

defs = Definitions(
    assets=[raw_contracts, raw_payments, dw_dbt_models],
    asset_checks=volume_checks,
    jobs=[atualiza_dw_job],
    schedules=[atualiza_dw_diario],
    resources={"dbt": dbt_resource},
)
