-- SCD2: cada contrato precisa ter exatamente uma versão atual
-- e as versões não podem se sobrepor no tempo.

with ordered as (
    select
        contrato_id,
        versao_atual,
        valido_ate,
        lead(valido_de) over (partition by contrato_id order by valido_de) as proximo_valido_de
    from {{ ref('dim_contrato') }}
),

checks as (
    select
        contrato_id,
        count(*) filter (where versao_atual)                    as versoes_atuais,
        count(*) filter (where valido_ate > proximo_valido_de)  as sobreposicoes
    from ordered
    group by contrato_id
)

select *
from checks
where versoes_atuais <> 1 or sobreposicoes > 0
