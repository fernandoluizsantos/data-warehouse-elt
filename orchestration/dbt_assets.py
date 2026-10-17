"""Projeto dbt como assets do Dagster: cada modelo/snapshot vira um asset e cada teste
vira um asset check. Testes com severity=warn aparecem como aviso, não como falha."""
import shutil
import sys
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, AssetSpec, FreshnessPolicy, apply_freshness_policy
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "dbt_project"

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)
# Em `dagster dev`, gera o manifest.json (mapa do projeto dbt) ao carregar o código.
dbt_project.prepare_if_dev()

# Usa o dbt do mesmo ambiente Python do Dagster (funciona sem ativar o .venv e no contêiner)
DBT_EXECUTABLE = shutil.which("dbt", path=str(Path(sys.executable).parent)) or "dbt"

dbt_resource = DbtCliResource(project_dir=dbt_project, dbt_executable=DBT_EXECUTABLE)


# Fatos devem ser atualizadas todo dia: aviso com 26h sem atualizar, falha com 50h
# (mesmos limites do source freshness do dbt). Avaliado pelo daemon do Dagster.
FACT_FRESHNESS = FreshnessPolicy.time_window(fail_window=timedelta(hours=50),
                                             warn_window=timedelta(hours=26))


class DwDbtTranslator(DagsterDbtTranslator):
    def get_asset_spec(self, manifest: Mapping[str, Any], unique_id: str,
                       project: DbtProject | None) -> AssetSpec:
        spec = super().get_asset_spec(manifest, unique_id, project)
        if spec.key.path[-1].startswith("fct_"):
            spec = apply_freshness_policy(spec, FACT_FRESHNESS)
        return spec


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=DwDbtTranslator())
def dw_dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    # `build` = snapshot + run + test na ordem do grafo, só para os assets selecionados
    yield from dbt.cli(["build"], context=context).stream()
