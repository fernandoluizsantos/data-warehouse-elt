# Endepoints
---

Base: `API_BASE_URL` (definida no `.env`; o endereço real não fica no repositório)

- Auth: `{API_BASE_URL}/api/token/`
    - [POST] -> {email: "", password: ""}
    - Pegar o Acess Token para enviar nos GETS

- Contratos: `{API_BASE_URL}/api/api-v2/contracts/`
- Pagamentos: `{API_BASE_URL}/api/api-v2/payments/`


# O que responder
----

- Quantidade de valor contratado
- Quantidade de Valor pago
- Quantidade de Saldo 
- Quantidade Gasta por Fornecedor


# Análise da fonte (etapa 0)
----

## Contrato da API
- `last_id` é **obrigatório** (>= 1) e a API devolve apenas ids **maiores** que ele.
- Contratos e pagamentos têm sequências de id independentes.
- Volume atual: > 25 mil contratos e > 25 mil pagamentos (carga inicial pequena).
- Campos aninhados viram colunas com `__` (ex.: `supplier__id`, `contract_code__campus__name`).

## Contratos (`/contracts/`)
- Chave: `id` (`contract_code` = código de negócio, ex.: CTR26460).
- Medidas: `contract_value`, `amount_paid`, `amount_to_pay` (já calculados pela fonte).
- Atributos: `contract_type`, `contract_state`, `contract_validity`, `campus`, `brand`, `budget_allocation`, `supplier`, `obra_type_fk`, criador e aprovador.
- Datas: `creation_date`, `approval_date`.
- Traz a lista aninhada `payments` (duplica o endpoint de pagamentos).
- Flags `has_*` (documentos anexados).

## Pagamentos (`/payments/`)
- Chave: `id` (`payment_code`, ex.: PGT28264); FK `contract_code__id` -> contrato.
- Medidas: `payment_value`, `amount_paid`.
- Estado: `payment_state` (ex.: "Pendente Pagamento").
- Datas: `creation_date`, `payment_date`, `payment_deadline`, `last_update_date`.
- Traz fornecedor, campus, marca e verba **desnormalizados** do contrato.

## Pontos de atenção
1. **Sentinela de data:** `payment_date = 2000-01-01` significa "não pago". Tratar como NULL no staging.
2. **Fusos mistos:** `-03:00` em `creation_date` de pagamentos e `Z` (UTC) nos demais. Padronizar no staging.
3. **Registros mudam:** pagamento passa de pendente para pago; contrato muda de estado/valor. Só `last_id` perde essas mudanças.
4. **Dados pessoais/sensíveis (LGPD):** e-mails de usuários, telefone, e-mail, CPF/CNPJ e dados bancários de fornecedores. O raw guarda sem alteração (somente local). Nos marts, mascarar/omitir; no modo Faker, tudo sintético.
5. **`amount_to_pay` e `amount_paid` do contrato** podem divergir da soma dos pagamentos: virar teste de qualidade no dbt.
6. Lista aninhada `payments` no contrato: a fonte da fato de pagamentos será o endpoint `/payments/`; o aninhado serve só para conferência.

## Decisões
- **Processo de negócio:** gestão financeira de contratos (do contrato ao pagamento).
- **Granularidade (opção A, duas fatos):**
  - `fct_contratos`: 1 linha por contrato (mede o valor contratado).
  - `fct_pagamentos`: 1 linha por pagamento/parcela (mede o valor pago).
  - Saldo = valor contratado - soma dos valores pagos, calculado em mart por contrato.
- **Dimensões candidatas:** `dim_fornecedor`, `dim_contrato` (SCD2), `dim_campus`, `dim_marca`, `dim_verba`, `dim_data`.
- **Estratégia incremental:** `last_id` + reextração a partir do menor id de registro ainda não finalizado (a confirmar com os valores de `payment_state` / `contract_state`).
- **Paginação:** laço usando o maior id recebido como próximo `last_id` até a resposta vir vazia (validar na etapa 2 se a API limita o tamanho da resposta).

## Estados (confirmados)
| Entidade | Estados finais | Estados não finais |
|---|---|---|
| `payment_state` | Pago, Cancelado | Pendente Pagamento |
| `contract_state` | Encerrado, Finalizado, Reprovado, Cancelado | Aprovado, Pendente Aprovação |

- Reextração parte do menor id em estado não final. Risco: um registro antigo esquecido como pendente
  puxa o `last_id` para trás e reextrai muita coisa. Mitigação: limite de janela + full refresh semanal.
- A semântica exata de Encerrado x Finalizado não foi confirmada; tratados como finais.
- `accepted_values` no dbt usará essas listas (e avisará se a fonte criar um estado novo).

## Pendências para a etapa 2
- A API limita o tamanho da resposta? Há rate limit? (desconhecido; descobrir testando)
- `contracts` possui `last_update_date`? (o script antigo o descartava).
