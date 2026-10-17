-- As duas fatos precisam contar a mesma história:
-- valor pago na fct_pagamentos (pagamentos com contrato) = valor pago somado na fct_contratos.

with by_payments as (
    select coalesce(sum(valor_pago), 0) as total
    from {{ ref('fct_pagamentos') }}
    where contrato_id <> -1
),

by_contracts as (
    select coalesce(sum(valor_pago), 0) as total
    from {{ ref('fct_contratos') }}
)

select
    p.total as total_fct_pagamentos,
    c.total as total_fct_contratos,
    p.total - c.total as diferenca
from by_payments as p
cross join by_contracts as c
where abs(p.total - c.total) > 0.01
