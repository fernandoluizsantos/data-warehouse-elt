# Contexto

Sou estudante/profissional em transição para Engenharia de Dados e quero aprender
construindo. Meu objetivo é montar, localmente, um projeto ELT de Data Warehouse
para colocar no portfólio e no currículo. Já tenho um DW local feito com dbt, então
o foco novo é a extração, a carga em um data lake, a orquestração e a organização
profissional do projeto. Tenho dificuldade em enxergar a aplicação prática de um DW
no mundo real, então quero que cada etapa deixe claro o "para quê".

# Como quero que você trabalhe (importante)

- Modo professor: construa em etapas pequenas. Ao fim de cada etapa, pare, resuma
  o que foi feito e espere minha confirmação antes de seguir.
- Antes de escrever código, explique em poucas linhas o que vamos fazer e por quê.
- Depois de escrever, explique as decisões não óbvias (idempotência, incremental,
  granularidade, particionamento, etc.).
- Se houver mais de um caminho razoável, apresente as opções com prós e contras e
  recomende uma. Não escolha em silêncio.
- Ao final de cada etapa, gere um resumo em markdown (conceitos, comandos, erros
  que apareceram e como resolvemos) que eu possa colar nas minhas anotações.
- Rode e teste o que escrever. Mostre a saída. Se algo falhar, explique a causa.

# Arquitetura-alvo

API do sistema -> Extração (Python) -> Raw no data lake (MinIO, formato S3)
-> Carga no DW (PostgreSQL, schema raw) -> dbt (staging -> intermediate -> marts)
-> Metabase. Orquestração com Dagster (ou Airflow, se você justificar a troca).
Tudo rodando local via Docker Compose.

Stack:
- MinIO (object storage compatível com S3) como camada raw do lake
- PostgreSQL como data warehouse
- Python (httpx/requests, boto3, pandas/pyarrow) para extração e carga
- dbt (dbt-postgres) para transformação, testes, snapshots e docs
- Dagster para orquestração (assets dbt)
- Metabase para visualização

# Requisitos técnicos

1. Extração com paginação, retries com backoff e tratamento de rate limit.
2. Carga incremental baseada em campo de atualização (watermark), guardando o
   estado da última extração.
3. Dado bruto gravado sem alteração no MinIO, particionado por
   entidade/ano/mes/dia, com metadados `_extracted_at` e `_source`.
4. Carga idempotente: rodar duas vezes o mesmo período não pode duplicar dados.
5. Modelagem dimensional: defina a granularidade da tabela fato ANTES de modelar;
   crie dimensões (incluindo dim_data) e pelo menos uma fato.
6. dbt com: testes (unique, not_null, relationships, accepted_values),
   snapshot (SCD tipo 2) em ao menos uma dimensão, modelo incremental,
   source freshness e documentação gerada.
7. Orquestração: pipeline extrair -> carregar -> dbt run -> dbt test, com retries
   e agendamento diário.
8. Registro de logs de execução (linhas carregadas, duração, status).
9. Dashboard no Metabase respondendo 2 ou 3 perguntas de negócio definidas na etapa 1.
10. Credenciais via variáveis de ambiente (`.env` no `.gitignore`).
    Endpoint do S3 configurável por variável, para o mesmo código rodar no MinIO
    local e na AWS depois, sem mudanças na lógica.

# Dados e segurança

A fonte é a API de um sistema de serviço da empresa onde trabalho, à qual tenho
acesso. Não coloque nenhuma credencial, token ou dado real no repositório.
Crie também um modo com dados sintéticos (Faker), no mesmo formato da API, para
que o projeto possa ser publicado no GitHub sem expor dados da empresa.
Se o MinIO (imagem Docker ou console) não se comportar como a documentação
sugere, me avise e proponha uma alternativa compatível com S3 (Garage, SeaweedFS
ou LocalStack).

# Estrutura de repositório

projeto-dw/
├── docker-compose.yml
├── .env.example
├── extract/              # extração e carga
├── orchestration/        # Dagster
├── dbt_project/
│   ├── models/{staging,intermediate,marts}/
│   ├── snapshots/
│   └── tests/
├── docs/                 # diagrama de arquitetura e modelo dimensional
└── README.md

# Plano de etapas (siga esta ordem, parando ao fim de cada uma)

0. Perguntar-me sobre a API (endpoints, autenticação, campos de data) e propor
   1 ou 2 processos de negócio e as perguntas que o DW deve responder.
1. Subir a infraestrutura com Docker Compose (MinIO, Postgres, Metabase) e
   validar que cada serviço responde.
2. Extração de UMA entidade -> gravar no MinIO -> carregar no schema raw do Postgres.
3. Primeiro modelo staging no dbt + testes básicos.
4. Expandir para as demais entidades.
5. Modelo dimensional (fato + dimensões), snapshot e modelo incremental.
6. Orquestração com Dagster.
7. Logs de execução e qualidade de dados.
8. Dashboard no Metabase.
9. README com diagrama de arquitetura, decisões técnicas, como rodar
   (`docker compose up`) e prints.

Comece pela etapa 0. Não avance para a etapa 1 até eu responder.