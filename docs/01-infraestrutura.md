# Etapa 1 – Infraestrutura com Docker Compose

## Para quê
Ambiente reproduzível: qualquer pessoa sobe o lake, o DW e o BI com `docker compose up -d`.

## Serviços
| Serviço | Papel | Porta |
|---|---|---|
| `seaweedfs` | Data lake (API S3) + navegador de arquivos | 8333 (S3), 8888 (filer) |
| `seaweedfs-init` | Cria o bucket `raw` e encerra (idempotente) | – |
| `postgres` | Data warehouse (`dw`) + banco de metadados do Metabase | 5432 |
| `metabase` | Visualização / BI | 3000 |

Schemas criados no init: `raw`, `staging`, `intermediate`, `marts`, `audit`.

## Conceitos
- **Healthcheck + `depends_on: condition: service_healthy`**: um serviço só sobe quando a dependência está pronta, não apenas iniciada.
- **Volumes nomeados**: dados sobrevivem a `down`; só `down -v` apaga.
- **`docker-entrypoint-initdb.d`**: scripts rodam só na primeira criação do volume.
- **Contêiner de init**: tarefa de preparação que roda uma vez e sai com `Exited (0)`.
- **Idempotência**: rodar o init de novo não quebra nem duplica nada.
- **Endpoint S3 por variável**: o mesmo código `boto3` funciona no SeaweedFS e na AWS.
- **Banco de metadados do Metabase**: separado do DW (H2 embutido não serve para produção).

## Comandos
```powershell
docker compose up -d                 # sobe tudo
docker compose ps -a                 # status (inclui contêineres encerrados)
docker compose logs <servico>        # logs
docker compose down                  # para (mantém dados)
docker compose down -v               # para e apaga volumes
# SQL no Postgres via stdin (evita problema de aspas/barras no PowerShell)
"SELECT 1;" | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| `metabase:v0.50.0 not found` | Tag inexistente | Consultar tags no Docker Hub; fixado `v0.59.31` |
| `postgres:16 Interrupted` | Compose aborta todos os pulls quando um falha | Corrigir a imagem que falhou de fato |
| `quay.io/minio/minio ... 401 UNAUTHORIZED` | MinIO deixou de publicar imagens públicas | Trocar por SeaweedFS (compatível com S3) |
| `\dn` virando `dn` no `psql` | PowerShell/sh consumindo a barra | Enviar o SQL por stdin |

## Decisão registrada
SeaweedFS no lugar do MinIO: um contêiner, API S3 completa, código cliente inalterado.
