from datetime import datetime, timedelta, timezone

from extract.lake import batch_key
from extract.synthetic import SENTINEL_DATE, SyntheticSource

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def test_sintetico_e_deterministico():
    a = SyntheticSource(now=NOW).payment(1050)
    b = SyntheticSource(now=NOW).payment(1050)
    assert a == b


def test_sintetico_cresce_com_o_tempo_e_pendente_vira_final():
    hoje = SyntheticSource(now=NOW)
    depois = SyntheticSource(now=NOW + timedelta(days=60))
    assert depois.max_id > hoje.max_id
    # todo pendente de hoje que já tem destino final muda em até 60 dias (quitação <= 35 dias)
    pendentes = [i for i in range(hoje.max_id - 300, hoje.max_id + 1)
                 if hoje.payment(i)["payment_state"] == "Pendente Pagamento"]
    mudaram = [i for i in pendentes if depois.payment(i)["payment_state"] != "Pendente Pagamento"]
    assert pendentes and len(mudaram) >= len(pendentes) * 0.9


def test_sintetico_respeita_last_id_e_lotes():
    src = SyntheticSource(batch_size=50, now=NOW)
    batches = [b for _, b in src.fetch_since("/x", src.max_id - 60)]
    ids = [r["id"] for b in batches for r in b]
    assert ids[0] == src.max_id - 59 and ids[-1] == src.max_id
    assert [len(b) for b in batches] == [50, 10]


def test_sintetico_tem_formato_da_api():
    p = SyntheticSource(now=NOW).payment(1001)
    for campo in ["payment_state", "contract_code__id", "contract_code__supplier__id",
                  "payment_value", "amount_paid", "payment_date", "last_update_date"]:
        assert campo in p
    if p["payment_state"] != "Pago":
        assert p["payment_date"] == SENTINEL_DATE


def test_chave_particionada():
    key = batch_key("payments", NOW, "abcdef12-3456", 3)
    assert key == "payments/ano=2026/mes=10/dia=17/payments_20261017T120000_abcdef12_0003.json"
