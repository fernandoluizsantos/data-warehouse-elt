# Etapa 2 – Extração de uma entidade: API → lake → Postgres raw

## Para quê
Separar extração/carga (E+L) da transformação (T). O lake guarda o histórico imutável de
cada extração (permite reprocessar sem chamar a API); o `raw` do DW guarda o estado atual
consultável, que é o ponto de partida do dbt.

```
Fonte (API ou Faker) -> lake: raw/payments/ano=/mes=/dia=/*.json -> Postgres raw.payments
                                                                  -> audit.extraction_runs
```

## Arquivos
| Arquivo | Responsabilidade |
|---|---|
| `extract/config.py` | `.env` e definição das entidades (endpoint, campo de estado, estados finais) |
| `extract/api_client.py` | Autenticação, retry com backoff, paginação por `last_id` |
| `extract/synthetic.py` | Fonte Faker no mesmo formato da API |
| `extract/lake.py` | Grava/lê lotes no S3 (boto3), caminho particionado |
| `extract/state.py` | Calcula o próximo `last_id` a partir do `raw` |
| `extract/loader.py` | Upsert lake → `raw` |
| `extract/main.py` | Orquestra a execução e registra em `audit.extraction_runs` |

## Conceitos
- **Paginação por cursor (`last_id`)**: o maior id recebido vira o próximo `last_id` até vir vazio.
  Proteção contra laço infinito se a API não avançar.
- **Retry com backoff exponencial + jitter** (tenacity): tenta de novo em 429/5xx/erro de rede;
  respeita `Retry-After`; renova o token em 401.
- **Envelope no lake**: metadados (`_extracted_at`, `_source`, `_run_id`, `_last_id_param`) fora de
  `data`; `data` é a resposta da API intacta.
- **Particionamento** por `entidade/ano=/mes=/dia=` da extração: facilita reprocessar um dia e
  listar só o necessário.
- **`raw` com `payload jsonb`**: campo novo na API não quebra a carga; o dbt tipa depois.
- **Idempotência**: upsert por `id` (`ON CONFLICT`); só atualiza se o payload mudou e o arquivo
  não é mais antigo que o carregado.
- **Estado derivado do `raw`**: `last_id` = menor id em estado não final − 1, com teto de
  `REEXTRACT_MAX_IDS` ids para trás. Sem arquivo de estado para dessincronizar.
- **Dados sintéticos determinísticos**: âncora fixa; mesmo instante → mesmos dados; com o tempo
  surgem registros novos e mudanças de estado reais.
- **Lake × raw no DW**: lake = todas as versões (histórico); raw = versão atual (consulta).
  Em lakehouse (BigQuery external, Spectrum, Trino/DuckDB) o raw no DW pode não existir.

## Comandos
```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q                                   # testes unitários
python -m extract.main --entity payments                  # full (padrão)
python -m extract.main --entity payments --incremental    # last_id pelo estado
$env:USE_SYNTHETIC_DATA='false'; python -m extract.main --entity payments   # API real
```

## Resultado (modo sintético)
| Execução | last_id | Extraídos | Inseridos | Atualizados | Inalterados |
|---|---|---|---|---|---|
| 1ª carga | 1 | 5724 | 5724 | 0 | 0 |
| Incremental | 1724 | 5000 | 0 | 0 | 5000 |
| Incremental de novo | 1724 | 5000 | 0 | 0 | 5000 |
| `--full` | 1 | 5724 | 0 | 0 | 5724 |

`raw.payments`: 5724 linhas = 5724 ids distintos.

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| Reexecução marcava ~2941 "atualizados" sem mudança real | Sintético usava `datetime.now()` nas datas | Data-âncora fixa; estado depende da data de quitação |
| Incremental voltou só até `last_id=1724` | ~2% de pagamentos nunca quitados puxariam a janela para o início | Teto `REEXTRACT_MAX_IDS` (risco previsto na etapa 0) |
| `S3_ENDPOINT_URL` apontando para `:9000` | `.env` ainda com porta do MinIO | Ajustar para `http://localhost:8333` |
| `Falha ao autenticar (HTTP 401)` | `.env` ainda com os valores de exemplo de `API_EMAIL`/`API_PASSWORD` | Preencher as credenciais reais |
| Aspas quebrando `python -c` no PowerShell | PowerShell interpreta aspas e `$` | Colocar o código num arquivo `.py` |

## Validação na API real
| Execução | last_id | Extraídos | Inseridos | Atualizados | Tempo |
|---|---|---|---|---|---|
| Falhou | 1 | 0 | – | – | 1s |
| Full | 1 | 28.089 | 28.089 | 0 | 13s |
| Incremental | 23.265 | 4.966 | 0 | 0 | 2s |

Descobertas:
- **Sem limite de lote**: `last_id=1` devolve tudo em uma resposta (~7s). O laço faz uma chamada
  extra, recebe vazio e encerra.
- **Rate limit**: não apareceu em 4 chamadas (não comprova ausência).
- **Sentinela confirmada**: `payment_date = 2000-01-01` em exatamente os 5.429 pendentes.
- **Menor id = 2**: com `last_id >= 1` obrigatório, um eventual id 1 nunca é retornado (limitação da API).
- **Pendentes antigos**: 5.429 pendentes (19%), o mais antigo de 2025-09-01. Com teto de 5.000 ids,
  2.916 pendentes ficavam fora da janela e seus pagamentos nunca seriam capturados.

## Decisão: full diário
Como o full custa 13s e uma requisição, ele virou o padrão. O incremental continua no código
(`--incremental`) para quando o volume justificar. Lição: medir antes de otimizar.

| Opção | Prós | Contras |
|---|---|---|
| **Full diário** (escolhida) | Simples, captura toda mudança | ~28k registros/dia no lake |
| Incremental sem teto | – | Na prática é um full com mais lógica |
| Incremental com teto + full semanal | Menos carga | Até 7 dias de pagamentos defasados |
