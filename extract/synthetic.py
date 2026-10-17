"""Fonte sintética (Faker) no mesmo formato da API, para publicar o projeto sem dados reais.

Simula uma API viva, mas determinística:
- a partir de uma data-âncora fixa surgem PAYMENTS_PER_DAY pagamentos por dia;
- cada pagamento tem um "destino" (pago/cancelado/nunca pago) e uma data de quitação
  sorteados pelo próprio id; até essa data ele fica "Pendente Pagamento".
Assim, rodar duas vezes no mesmo instante devolve exatamente os mesmos dados, e com o
passar dos dias aparecem registros novos e mudanças de estado reais.
Atributos do contrato são sorteados pelo id do contrato (pagamentos coerentes entre si).
"""
import random
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from faker import Faker

SENTINEL_DATE = "2000-01-01T00:00:00Z"  # a API usa essa data para "não pago"
BRT = timezone(timedelta(hours=-3))

FIRST_PAYMENT_ID = 1001
FIRST_CONTRACT_ID = 501
ANCHOR = datetime(2025, 10, 1, tzinfo=timezone.utc)
PAYMENTS_PER_DAY = 15

_CAMPUS = ["São José", "Asa Sul", "Tijuca", "Ilha do Governador", "Centro", "Barra", "Moema", "Savassi"]
_BRANDS = ["Marca A", "Marca B", "Marca C", "Marca D", "Marca E"]
_BUDGETS = ["Limpeza Terceirizada", "Manut. Predial Corretiva", "Obra de Reforma", "Segurança", "TI"]
_USERS = [f"usuario{i:02d}@exemplo.com" for i in range(1, 16)]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


class _Pools:
    """Cadastros fixos (fornecedores etc.), gerados uma vez com semente fixa."""

    def __init__(self) -> None:
        fake = Faker("pt_BR")
        fake.seed_instance(42)
        self.suppliers = [
            {
                "id": 100 + i,
                "cpf_cnpj": fake.cnpj().replace(".", "").replace("/", "").replace("-", ""),
                "corporate_name": fake.company().upper(),
                "phone": fake.phone_number(),
                "email": fake.company_email(),
                "bank": f"{fake.random_int(1, 999):03d} - BANCO FICTICIO",
                "agency": f"{fake.random_int(1, 9999):04d}",
                "account": f"{fake.random_int(10000, 99999999)}-{fake.random_digit()}",
            }
            for i in range(60)
        ]


_POOLS = _Pools()


class SyntheticSource:
    """Imita /payments/: fetch_since devolve lotes de ids > last_id."""

    def __init__(self, batch_size: int = 500, now: datetime | None = None):
        self.batch_size = batch_size
        self.now = now or datetime.now(timezone.utc)
        # só "existem" os pagamentos já criados até agora
        self.max_id = FIRST_PAYMENT_ID - 1
        while self._created(self.max_id + 1) <= self.now:
            self.max_id += 1

    @staticmethod
    def _created(payment_id: int) -> datetime:
        offset = (payment_id - FIRST_PAYMENT_ID) / PAYMENTS_PER_DAY
        return ANCHOR + timedelta(days=offset, minutes=random.Random(-payment_id).randrange(60))

    def _contract(self, contract_id: int) -> dict:
        rnd = random.Random(contract_id)
        campus_idx = rnd.randrange(len(_CAMPUS))
        brand_idx = rnd.randrange(len(_BRANDS))
        budget_idx = rnd.randrange(len(_BUDGETS))
        return {
            "id": contract_id,
            "contract_code": f"CTR{contract_id}",
            "campus": {"id": 80 + campus_idx, "name": _CAMPUS[campus_idx]},
            "brand": {"id": 10 + brand_idx, "name": _BRANDS[brand_idx]},
            "budget": {"id": 1 + budget_idx, "name": _BUDGETS[budget_idx]},
            "supplier": rnd.choice(_POOLS.suppliers),
        }

    def payment(self, payment_id: int) -> dict:
        rnd = random.Random(payment_id)
        # ~2 pagamentos por contrato
        contract = self._contract(FIRST_CONTRACT_ID + (payment_id - FIRST_PAYMENT_ID) // 2)

        created = self._created(payment_id)
        deadline = (created + timedelta(days=rnd.choice([7, 15, 30]))).replace(hour=0, minute=0, second=0, microsecond=0)
        fate = rnd.choices(["Pago", "Cancelado", "Pendente Pagamento"], weights=[90, 8, 2])[0]
        settled_at = created + timedelta(days=rnd.uniform(1, 35))  # às vezes depois do prazo
        state = fate if settled_at <= self.now else "Pendente Pagamento"

        value = round(rnd.uniform(150, 25000), 2)
        paid = state == "Pago"
        payer = rnd.randrange(len(_USERS)) if paid else None
        updated = settled_at if state != "Pendente Pagamento" else created
        sup = contract["supplier"]

        return {
            "id": payment_id,
            "creation_date": created.astimezone(BRT).isoformat(),
            "payment_code": f"PGT{payment_id}",
            "payment_state": state,
            "created_by__id": (cb := rnd.randrange(len(_USERS))) + 1,
            "created_by__email": _USERS[cb],
            "paying__id": payer + 1 if payer is not None else None,
            "paying__email": _USERS[payer] if payer is not None else None,
            "contract_code__id": contract["id"],
            "contract_code__contract_code": contract["contract_code"],
            "contract_code__campus__id": contract["campus"]["id"],
            "contract_code__campus__name": contract["campus"]["name"],
            "contract_code__budget_allocation__id": contract["budget"]["id"],
            "contract_code__budget_allocation__name": contract["budget"]["name"],
            "contract_code__supplier__id": sup["id"],
            "contract_code__supplier__cpf_cnpj": sup["cpf_cnpj"],
            "contract_code__supplier__corporate_name": sup["corporate_name"],
            "contract_code__supplier__phone": sup["phone"],
            "contract_code__supplier__email": sup["email"],
            "contract_code__supplier__bank": sup["bank"],
            "contract_code__supplier__agency": sup["agency"],
            "contract_code__supplier__account": sup["account"],
            "payment_value": value,
            "amount_paid": value if paid else 0.0,
            "payment_date": _iso(settled_at) if paid else SENTINEL_DATE,
            "payment_deadline": _iso(deadline),
            "last_update_date": _iso(updated),
            "contract_code__brand__id": contract["brand"]["id"],
            "contract_code__brand__name": contract["brand"]["name"],
        }

    def fetch_since(self, endpoint: str, last_id: int) -> Iterator[tuple[int, list[dict]]]:
        if last_id < 1:
            raise ValueError("A API exige last_id >= 1")
        start = max(last_id + 1, FIRST_PAYMENT_ID)
        while start <= self.max_id:
            end = min(start + self.batch_size - 1, self.max_id)
            yield start - 1, [self.payment(i) for i in range(start, end + 1)]
            start = end + 1

    def close(self) -> None:
        pass
