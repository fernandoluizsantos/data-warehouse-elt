# Etapa 4 – Expandir para contratos

## Para quê
Trazer a segunda entidade do processo de negócio (contratos) reaproveitando a extração,
o lake e a carga, e confrontar as duas fontes para entender o significado real dos campos.

## O que foi feito
- `contracts` adicionado em `extract/config.py`. Nenhuma outra linha da extração mudou
  (desenho por configuração).
- Extração real: 26.535 contratos em 17s; a 2ª execução não inseriu nem alterou nada.
- `stg_contracts` + `_stg_contracts.yml` (unique em `contract_id` e `contract_code`,
  accepted_values em tipo e estado, not_null nos campos-chave).
- `relationships`: todo `stg_payments.contract_id` existe em `stg_contracts` (PASS).
- Testes singulares de reconciliação: `assert_contract_balance_closes`,
  `assert_contract_paid_matches_payments`.
- Modo sintético recusa `contracts` com erro claro (pendência).

## Conceitos
- **Perfilar antes de modelar**: `jsonb_each` + `jsonb_typeof` para ver tipos, nulos e vazios
  de cada campo; `GROUP BY` nos campos categóricos para ver os valores reais.
- **Testar hipóteses com dados**: comparar o campo da origem com várias definições candidatas
  e ficar com a que bate (aqui, 99,8%).
- **Renomear pelo significado** é papel do staging: `amount_paid` → `amount_committed`.
- **Teste `relationships`**: integridade referencial entre modelos (chave estrangeira lógica).
- **Diferenciar erro de dado de regra de negócio**: saldo zerado em contrato encerrado não é erro.
- **`dbt build`** = run + test na ordem do grafo; para dependentes se um teste `error` falhar.

## Achados (dados reais)
| Achado | Tratamento |
|---|---|
| `approval_date = 2000-01-01` nos 318 "Pendente Aprovação" | `approved_at` = NULL |
| `contract_validity` mistura `"2026"` e `"30/12/2025"` | Guarda o texto + `validity_year` (últimos 4 caracteres) |
| `legal_control` sempre vazio; `project_code` vazio em 89% | Removido; `''` → NULL |
| `amount_paid` do contrato = soma do `payment_value` dos pagamentos **não cancelados** (inclui pendentes) | Renomeado para `amount_committed` |
| `amount_to_pay` = valor − lançado, **zerado** em Encerrado/Cancelado | Renomeado para `amount_remaining`; teste ignora fechados |
| Lista aninhada `payments`: 28.010 itens, só 1 ausente em `/payments/` | Fica só no raw; fonte da fato é `/payments/` |

## Resultado
`dbt build --select staging`: PASS=30 WARN=5 ERROR=0.

| Aviso | Casos | Significado |
|---|---|---|
| `assert_payment_amount_consistent` | 348 | `amount_paid` do pagamento incoerente com o estado |
| `assert_contract_paid_matches_payments` | 48 | Lançado no contrato ≠ pagamentos não cancelados |
| `assert_contract_balance_closes` | 1 | Contrato aberto com saldo que não fecha |
| `not_null` contract_id / supplier_id (pagamentos) | 80 | Pagamentos sem contrato |

## Erros e soluções
| Erro | Causa | Solução |
|---|---|---|
| `function min(jsonb) does not exist` | `min` não aceita jsonb | `string_agg(DISTINCT jsonb_typeof(v), ',')` |
| Aviso de reconciliação com 4.538 casos | Hipótese errada sobre `amount_paid` do contrato | Testar hipóteses; regra correta reduziu para 48 |
| Aviso de saldo com 2.253 casos | Regra de negócio (saldo zerado ao encerrar) tratada como erro | Excluir Encerrado/Cancelado do teste; sobrou 1 |

## Definições propostas para a etapa 5
| Pergunta | Definição |
|---|---|
| Valor contratado | `sum(contract_value)` |
| Valor pago | `sum(payment_value)` dos pagamentos Pago sem `has_amount_inconsistency` |
| Saldo | contratado − pago, só contratos abertos (Aprovado) |
| Gasto por fornecedor | valor pago por fornecedor |
| Extra: comprometido | lançado em pagamentos ainda pendentes |

## Pendência
Fonte sintética de contratos (coerente com os `contract_id` dos pagamentos sintéticos),
obrigatória antes de publicar no GitHub.
