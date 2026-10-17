# Etapa 6 – Orquestração com Dagster

## Para quê
Tirar o pipeline da execução manual: rodar na ordem certa, todo dia, tentando de novo
quando a API falhar, com histórico, logs e visão do grafo completo (API → fatos).

## Decisão: Dagster local (no .venv)
| Opção | Por que não / por que sim |
|---|---|
| Airflow | Mais pedido em vagas, mas não roda nativamente no Windows e pede ≥ 4 GB só para ele; o Docker tem 3,7 GB e já roda Postgres + SeaweedFS + Metabase |
| **Dagster no .venv** (escolhido) | Leve, integração nativa com dbt, grafo de assets |
| Dagster em contêiner | Fica para depois; limitação: o schedule só dispara com `dagster dev` aberto |

Conceitos são transferíveis (dependências, schedule, retry, idempotência, backfill).
`extract/` e `dbt_project/` não dependem do orquestrador: trocar para Airflow mexe só em `orchestration/`.

## Arquivos
| Arquivo | Função |
|---|---|
| `orchestration/extract_assets.py` | Assets `seed_api/contracts` e `seed_api/payments` (chamam `extract.main.run`), com retry e metadados |
| `orchestration/dbt_assets.py` | Projeto dbt como assets (`@dbt_assets` + `dbt build`); testes viram asset checks |
| `orchestration/definitions.py` | Job `atualiza_dw`, schedule `atualiza_dw_diario` (06:00 America/Sao_Paulo), resources |
| `pyproject.toml` | `[tool.dagster]` para `dagster dev` achar o código |

## Conceitos
| Conceito | O que é | No projeto |
|---|---|---|
| Asset | Dado persistente mantido atualizado | 2 de extração + 12 do dbt |
| Materialização | Execução que produz o asset (+ metadados) | Registros, inseridos, duração |
| Asset check | Verificação de qualidade ligada ao asset | Cada teste dbt (warn = amarelo) |
| Op / step | Função executada / execução dela num run | 3 steps: 2 extrações + 1 `dbt build` |
| Job | Seleção de assets com nome | `atualiza_dw` (tudo) |
| Run | Uma execução | Gantt, logs, re-execute from failure |
| Retry policy | Tentar de novo um step | 3x, 60s/120s/240s, só nas extrações |
| Schedule / sensor | Disparo por horário / por evento | Diário 06:00 / (não usado) |
| Resource | Conexão injetada nos assets | `DbtCliResource` |
| Definitions / code location | Índice do código carregado | `orchestration/definitions.py` |
| Daemon | Processo que avalia schedules/sensors | Sobe junto com `dagster dev` |
| DAGSTER_HOME | Onde ficam histórico e eventos | `dagster_home/` (fora do git) |
| Partições / backfill | Fatiar asset por data / reprocessar várias | Evolução futura |

Decisões não óbvias:
- Chaves `seed_api/<entidade>` = nomes que o dagster-dbt dá às sources → ligação automática Python ↔ dbt.
- Retry em dois níveis: tenacity (requisição, segundos) e RetryPolicy (asset inteiro, minutos).
- Sem retry no dbt: teste com erro falha igual na segunda tentativa.
- `dbt_executable` aponta para o dbt do mesmo Python do Dagster.

## Comandos
```powershell
.\.venv\Scripts\Activate.ps1
$env:DAGSTER_HOME = "$PWD\dagster_home"
dagster dev -p 3001                                         # interface em http://localhost:3001
dagster definitions validate -m orchestration.definitions
dagster asset list -m orchestration.definitions
dagster job execute -m orchestration.definitions -j atualiza_dw   # roda sem interface
```

## Resultado (API real)
| Step | Resultado | Tempo |
|---|---|---|
| `seed_api__payments` | 28.095 extraídos (6 novos) | 11s |
| `seed_api__contracts` | 26.550 extraídos (15 novos, 5 atualizados) | 14s |
| `dw_dbt_models` | PASS=96 WARN=5 ERROR=0 | 15s |
| Job | RUN_SUCCESS | ~40s |

Validação do SCD2 usando o lake: os 5 contratos atualizados mudaram só `amount_paid`,
`amount_to_pay` e a lista aninhada (novos pagamentos) — campos fora do `check_cols`, então
corretamente nenhuma versão nova foi aberta.

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| `The dbt executable 'dbt' was not found on PATH` | `.venv` não ativado no shell | `dbt_executable` = dbt ao lado de `sys.executable` |
| Aviso "No dagster.yaml found" | `DAGSTER_HOME` sem arquivo de config | Criar `dagster_home/dagster.yaml` vazio |
