-- Calendário: uma linha por dia. Usada com papéis diferentes pelas fatos
-- (data de criação, de pagamento, de vencimento, de aprovação).

with days as (
    select generate_series('2020-01-01'::date, '2030-12-31'::date, interval '1 day')::date as data
),

calendar as (
    select
        to_char(data, 'YYYYMMDD')::int                                  as date_key,
        data,
        extract(year from data)::int                                    as ano,
        extract(quarter from data)::int                                 as trimestre,
        extract(month from data)::int                                   as mes,
        (array['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho',
               'Agosto','Setembro','Outubro','Novembro','Dezembro'])
            [extract(month from data)::int]                             as nome_mes,
        to_char(data, 'YYYY-MM')                                        as ano_mes,
        extract(day from data)::int                                     as dia,
        extract(isodow from data)::int                                  as dia_semana,      -- 1 = segunda
        (array['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'])
            [extract(isodow from data)::int]                            as nome_dia_semana,
        extract(isodow from data) in (6, 7)                             as fim_de_semana
    from days
),

unknown as (
    -- para datas ausentes (ex.: pagamento ainda não pago)
    select -1, null::date, null::int, null::int, null::int, 'Sem data',
           'Sem data', null::int, null::int, 'Sem data', null::boolean
)

select * from calendar
union all
select * from unknown
