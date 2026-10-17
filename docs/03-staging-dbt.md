# Etapa 3 – Primeiro modelo staging no dbt + testes

## Para quê
Transformar o JSON bruto de `raw.payments` em uma tabela tipada e limpa (`staging.stg_payments`),
e deixar testes automáticos vigiando a qualidade do dado a cada execução.

## Estrutura do dbt_project
| Caminho | Função |
|---|---|
| `dbt_project.yml` | Identidade do projeto e regras por pasta (staging/intermediate = view, marts = table) |
| `profiles.yml` | Conexão com o banco, só via `env_var()` (versionável) |
| `macros/generate_schema_name.sql` | Usa `staging`/`marts` direto, em vez de `analytics_staging` |
| `models/staging/_sources.yml` | Declara `raw.payments` como source + testes + freshness |
| `models/staging/_stg_payments.yml` | Documentação e testes do modelo |
| `models/staging/stg_payments.sql` | O modelo |
| `tests/assert_payment_amount_consistent.sql` | Teste singular (relatório de qualidade) |
| `target/`, `logs/` | Gerados pelo dbt; fora do git |

## Conceitos
- **Camadas**: staging (limpa, 1:1 com a fonte, sem join) → intermediate (preparação) → marts (fato/dimensão).
- **CTE** (`with x as (...)`): consulta nomeada usada logo abaixo; deixa o SQL legível como uma receita.
- **`source()`**: em vez de escrever `raw.payments`; dá linhagem e freshness.
- **`payload ->> 'campo'`**: extrai do JSON como texto; depois cast (`::bigint`, `::numeric(14,2)`, `::timestamptz`).
- **Dinheiro em `numeric`**, nunca `float` (erro de arredondamento em somas).
- **Sentinela → NULL comparando depois do cast** (`nullif(x::timestamptz, '2000-01-01T00:00:00Z'::timestamptz)`):
  robusto a variações de formato do texto.
- **Data "pura" vinda como meia-noite UTC**: `left(texto, 10)::date`, para o fuso da sessão não mudar o dia.
- **Testes genéricos** (yml) × **singulares** (SQL em `tests/` que deve voltar vazio).
- **Severidade `warn`**: o teste avisa sem bloquear o pipeline; usado para problemas conhecidos de origem.
- **Staging não apaga dado**: marca com flag; a decisão de excluir fica nos marts.

## Comandos
```powershell
cd dbt_project
$env:DBT_PROFILES_DIR='.'
dotenv -f ..\.env run -- dbt debug
dotenv -f ..\.env run -- dbt build --select stg_payments     # cria + testa
dotenv -f ..\.env run -- dbt show --select stg_payments --limit 5
dotenv -f ..\.env run -- dbt source freshness
dotenv -f ..\.env run -- dbt build --no-partial-parse        # força re-parse
```

## Resultado
`dbt build --select stg_payments`: PASS=10 WARN=3 ERROR=0.

## Achados de qualidade (dados reais)
| Achado | Volume | Tratamento |
|---|---|---|
| Pagamentos sem nenhum dado de contrato | 80 (R$ 1,3 mi) | Mantidos; teste `warn`; membro desconhecido nos marts |
| `amount_paid` incoerente com o estado (ex.: 100x/1000x o valor; cancelado com valor pago) | 348 | Flag `has_amount_inconsistency`; excluídos das métricas nos marts; teste `warn` lista os casos |

Sem o tratamento, "valor pago" somando `amount_paid` dava R$ 137,9 mi contra R$ 128,8 mi de
`payment_value` dos pagos (~R$ 9 mi inflados por poucos registros).

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| `dbt build` rodou só o modelo (TOTAL=1), sem testes | Cache de parsing parcial de quando o modelo não existia | `--no-partial-parse` |
| `not_null` de `contract_id`/`supplier_id` falhou (80) | Pagamentos sem contrato na origem | Investigado; severidade `warn` + membro desconhecido |
| `set-returning functions are not allowed in HAVING` | `jsonb_object_keys` no HAVING | Usar `jsonb_each_text` no FROM |
