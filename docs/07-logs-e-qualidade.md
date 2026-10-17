# Etapa 7 – Logs de execução e qualidade de dados

## Para quê
Saber, sem abrir terminal, se o pipeline rodou, quanto trouxe, quanto demorou, o que falhou e
como está a qualidade do dado — e impedir que um dado quebrado chegue ao dashboard.

## Camadas de observabilidade
| O que | Onde | Como |
|---|---|---|
| Log da extração (linhas, duração, status, erro) | `audit.extraction_runs` | `extract/main.py` (desde a etapa 2) |
| Log do dbt (cada modelo/teste: status, duração, linhas, falhas) | `audit.dbt_results` | Hooks `on-run-start`/`on-run-end` (`macros/audit_dbt_results.sql`) |
| Nulos, unicidade, relações, valores aceitos | Testes do dbt → asset checks no Dagster | Etapas 3–5 |
| **Volume** da extração | Asset checks bloqueantes no Dagster | `orchestration/quality_checks.py` |
| **Freshness** das fatos | `FreshnessPolicy` nos assets `fct_*` | `orchestration/dbt_assets.py` |
| Freshness da source | `dbt source freshness` | `_sources.yml` (etapa 3) |
| Visões para o painel de saúde | Schema `monitoring` (dbt) | `mon_extracoes`, `mon_execucoes_dbt`, `mon_qualidade_dados` |

## Regras de volume
| Situação | Severidade | Efeito |
|---|---|---|
| Queda > 10% vs extração anterior bem-sucedida (mesma fonte) | WARN | Avisa; pipeline segue |
| Queda > 50% ou zero registros | ERROR | **Bloqueia o dbt** (`blocking=True`) |

Como a extração é full, o volume só deveria crescer. Simulação: queda de 15% → WARN; queda de 96% → ERROR.

## Freshness das fatos
`FreshnessPolicy.time_window(warn_window=26h, fail_window=50h)` em `fct_pagamentos` e `fct_contratos`.
Mesmos limites do `dbt source freshness`. Avaliado pelo daemon; não precisa de sensor.

## Conceitos
- **Observabilidade** = logs (o que aconteceu) + métricas (volume, duração) + checagens (está certo?).
- **Hooks do dbt** (`on-run-start`/`on-run-end`): SQL que roda antes/depois de toda execução;
  `results` traz status, tempo, `adapter_response.rows_affected` e `failures` de cada nó.
- **Check bloqueante**: falha com severidade ERROR impede a materialização dos assets abaixo no mesmo run.
- **WARN × ERROR**: problema conhecido que não deve parar o negócio × quebra que invalida o dado.
- **Comparar só com a mesma fonte**: o log tem extrações sintéticas e reais; misturar gera falso alarme.
- **Visões de monitoramento como modelos dbt**: a saúde do pipeline vira dado consultável no Metabase.
- **Manifest do dbt no Dagster**: o grafo vem do `target/manifest.json`. `dagster dev` regera
  ao carregar (`prepare_if_dev`); pela CLI é preciso `dbt parse` depois de criar/renomear modelos.

## Comandos
```powershell
cd dbt_project; $env:DBT_PROFILES_DIR='.'
dotenv -f ..\.env run -- dbt parse               # regera o manifest depois de mudar modelos
cd ..
$env:DAGSTER_HOME = "$PWD\dagster_home"
dagster job execute -m orchestration.definitions -j atualiza_dw
```
```sql
SELECT * FROM monitoring.mon_extracoes ORDER BY iniciado_em DESC;
SELECT * FROM monitoring.mon_execucoes_dbt ORDER BY iniciado_em DESC;
SELECT * FROM monitoring.mon_qualidade_dados WHERE execucao_mais_recente AND gravidade <> 'ok';
```

## Resultado
Job `atualiza_dw`: RUN_SUCCESS; checks de volume passed; dbt PASS=106 WARN=5 ERROR=0 (111 nós).
`metabase_reader` lê `monitoring` (grants via dbt + USAGE no schema).

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| `lag()` com `FILTER` | FILTER só vale para agregações | CTE só com extrações bem-sucedidas |
| `KeyError: 'model.dw_contratos.mon_execucoes_dbt'` no Dagster | Manifest antigo: modelos novos não existiam no mapa | `dbt parse` (ou recarregar o código no `dagster dev`) |
| `SupersessionWarning` em `build_last_update_freshness_checks` | API substituída no Dagster 1.13 | `FreshnessPolicy` via `DagsterDbtTranslator` |
| Linha de WARN sumiu da saída | Filtro do PowerShell removia linhas com "warn" | Rodar sem filtro |
