-- Soma dos pagamentos VÁLIDOS por contrato. Única fonte da regra de "pago" usada pelos contratos.
-- Pagamentos com amount_paid incoerente (has_amount_inconsistency) ficam de fora, como na fct_pagamentos.

select
    contract_id,
    count(*)                                                            as qtd_pagamentos,
    sum(payment_value) filter (where payment_state = 'Pago')            as valor_pago,
    sum(payment_value) filter (where payment_state = 'Pendente Pagamento') as valor_pendente,
    sum(payment_value) filter (where payment_state = 'Cancelado')       as valor_cancelado,
    max(paid_at)                                                        as ultimo_pagamento_em
from {{ ref('stg_payments') }}
where contract_id is not null
  and not has_amount_inconsistency
group by contract_id
