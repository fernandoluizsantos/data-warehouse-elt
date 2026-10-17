# Plano do Projeto ELT – Data Warehouse

> Arquivo de acompanhamento. Marque `[x]` ao concluir. Uma etapa só termina quando:
> (1) funciona e foi testada, (2) você entendeu o "para quê", (3) o resumo de anotações foi gerado.

## Arquitetura-alvo

```
API do sistema -> Extração (Python) -> MinIO (raw, S3) -> Postgres (schema raw)
   -> dbt (staging -> intermediate -> marts) -> Metabase
Orquestração: Dagster | Tudo local via Docker Compose
```

## Estrutura do repositório

```
data-warehouse-elt/
├── docker-compose.yml
├── .env.example          # .env real fica no .gitignore
├── extract/              # extração e carga
├── orchestration/        # Dagster
├── dbt_project/{models/{staging,intermediate,marts},snapshots,tests}
├── docs/                 # diagramas e notas por etapa
└── README.md
```

## Etapas

### [x] Etapa 0 – Entender a fonte e o negócio
- **Para quê:** um DW responde perguntas de negócio. Sem elas, não há granularidade nem modelo.
- Levantar: endpoints, autenticação, paginação, rate limit, campos de data/atualização.
- Definir 1–2 processos de negócio e 2–3 perguntas que o DW deve responder.
- **Entregável:** `docs/00-fonte-e-negocio.md`
- **Pronto quando:** perguntas de negócio e candidata a granularidade da fato definidas.

### [x] Etapa 1 – Infraestrutura (Docker Compose)
- **Para quê:** ambiente reproduzível; qualquer pessoa sobe tudo com um comando.
- MinIO, Postgres, Metabase; `.env.example`, `.gitignore`.
- **Pronto quando:** console do MinIO abre, `psql` conecta, Metabase responde.
- Plano B se o MinIO falhar: Garage, SeaweedFS ou LocalStack.

### [x] Etapa 2 – Extração de UMA entidade → SeaweedFS → Postgres raw
- ✅ Validado contra a API real (28.089 pagamentos, sem limite de lote, full em 13s).
- **Para quê:** separar extrair de transformar (ELT); o raw imutável permite reprocessar.
- Paginação, retries com backoff, rate limit.
- Gravar JSON/Parquet sem alteração em `entidade/ano/mes/dia`, com `_extracted_at` e `_source`.
- Carga incremental por watermark, com estado guardado; carga idempotente.
- Modo sintético (Faker) no mesmo formato da API.
- **Pronto quando:** rodar 2x o mesmo período não duplica linhas.

### [x] Etapa 3 – Primeiro modelo staging no dbt + testes básicos
- **Para quê:** staging padroniza nomes e tipos; testes pegam problemas cedo.
- `sources` + `stg_<entidade>`, testes `unique` e `not_null`.

### [x] Etapa 4 – Demais entidades
- ✅ Contratos extraídos da API real (26.535) + `stg_contracts` + testes de reconciliação.
- ⏳ **Pendente:** fonte sintética de contratos (antes de publicar).
- Repetir o padrão da etapa 2/3, extraindo o que for comum para funções reutilizáveis.

### [x] Etapa 5 – Modelo dimensional
- **Definir a granularidade da fato ANTES de modelar.**
- `dim_data` + demais dimensões + ao menos uma fato.
- Snapshot SCD2 em uma dimensão; modelo incremental; `relationships` e `accepted_values`.
- Source freshness e `dbt docs generate`.
- **Entregável:** diagrama do modelo em `docs/`.

### [x] Etapa 6 – Orquestração com Dagster
- Local (`dagster dev`); schedule só dispara com o terminal aberto. Contêiner fica para depois.
- Pipeline: extrair → carregar → dbt run → dbt test.
- Retries e agendamento diário; dbt como assets.

### [x] Etapa 7 – Logs de execução e qualidade de dados
- Tabela de log: linhas carregadas, duração, status.
- Checagens de qualidade (volume, nulos, freshness).

### [ ] Etapa 8 – Dashboard no Metabase
- Responder as perguntas de negócio da etapa 0.

### [ ] Etapa 9 – README e portfólio
- ✅ README.md escrito; domínio real removido de `.env.example`, `config.py` e `docs/00`.
- ⏳ Antes de publicar: fonte sintética de contratos; anonimizar números reais em `docs/` e `PLANO.md`;
  decidir sobre o `CLAUDE.md`; prints em `docs/img/`; dashboards no Metabase.
- Diagrama de arquitetura, decisões técnicas, `docker compose up`, prints.

## Checklist transversal
- [ ] Nenhuma credencial/token/dado real no repositório
- [ ] Endpoint S3 configurável por variável (MinIO local ↔ AWS)
- [ ] Modo sintético funcionando
- [ ] Resumo de anotações gerado em `docs/` ao fim de cada etapa

## Diário de decisões
| Data | Decisão | Alternativas | Motivo |
|------|---------|--------------|--------|
| 2026-10-17 | Duas fatos: `fct_contratos` (1 por contrato) e `fct_pagamentos` (1 por pagamento) | Fato única no nível do pagamento | Evita somar valor contratado repetido |
| 2026-10-17 | SeaweedFS 4.48 como data lake S3 | MinIO, Garage, LocalStack | MinIO sem imagem pública (quay 401, Docker Hub removido); SeaweedFS sobe em 1 contêiner; código boto3 não muda |
| 2026-10-17 | Metabase lê só `marts` e `monitoring` com usuário `metabase_reader` (grants via dbt) | Usar `dw_user` | `raw` tem dados pessoais e bancários; grant manual se perderia quando o dbt recria a tabela |
| 2026-10-17 | Check de volume bloqueante (WARN >10%, ERROR >50%) + FreshnessPolicy nas fatos + log do dbt via hooks | Só testes do dbt | Impede dado quebrado no dashboard; saúde do pipeline vira dado consultável |
| 2026-10-17 | Dagster local no `.venv` | Airflow; Dagster em contêiner | Airflow não roda nativo no Windows e não cabe nos 3,7 GB do Docker; integração dbt nativa |
| 2026-10-17 | Duas fatos: `fct_pagamentos` (incremental, 1/pagamento) e `fct_contratos` (accumulating snapshot, 1/contrato) | Fato única | Granularidades diferentes de contratado × pago |
| 2026-10-17 | Pagamentos com inconsistência **removidos** da fato (post_hook no incremental) | Manter linha e zerar medida | Decisão do usuário; mesma regra no intermediate para as fatos baterem |
| 2026-10-17 | SK só na `dim_contrato` (SCD2 via snapshot `check`); demais dimensões SCD1 com id da origem | SK em todas | SK só onde o id se repete (versões) |
| 2026-10-17 | Chaves de data no fuso de Brasília | UTC | O dia que importa para o negócio |
| 2026-10-17 | `amount_paid`/`amount_to_pay` do contrato renomeados para `amount_committed`/`amount_remaining` | Manter nomes da API | Validado em 99,8%: é valor lançado em pagamentos (inclui pendentes), não dinheiro pago |
| 2026-10-17 | Lista aninhada `payments` dos contratos fica só no raw | Explodir no staging | Endpoint `/payments/` é a fonte; aninhado só tem 1 item a mais |
| 2026-10-17 | 80 pagamentos sem contrato: mantidos no staging (teste `warn`); nos marts, membro desconhecido -1 | Descartar; falhar o pipeline | Não perder R$ 1,3 mi do total sem quebrar joins |
| 2026-10-17 | Pagamentos com `amount_paid` incoerente (348): flag `has_amount_inconsistency` no staging, excluídos das métricas nos marts; teste `warn` lista os casos | Usar `amount_paid` como está; apagar | Erros de digitação (até 1000x) inflavam o "valor pago" em ~R$ 9 mi |
| 2026-10-17 | **Full diário** como padrão de extração (substitui a decisão abaixo) | Incremental com teto; sem teto; teto + full semanal | API real devolve 28k registros em 13s; com teto de 5000 ids, 2916 pendentes antigos ficariam desatualizados |
| 2026-10-17 | Incremental com `last_id` + reextração a partir do menor id não finalizado | Só `last_id`; full refresh | Captura mudanças de estado sem recarregar tudo |
