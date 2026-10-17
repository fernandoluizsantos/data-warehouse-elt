import httpx
import pytest
from tenacity import wait_none

from extract.api_client import RetryableHTTPError, SeedClient

ENDPOINT = "/api/api-v2/payments/"


def make_client(handler, max_attempts=3):
    return SeedClient(
        "https://api.teste", "a@b.com", "x",
        max_attempts=max_attempts, wait=wait_none(),
        transport=httpx.MockTransport(handler),
    )


def fake_api(data_ids, calls, fail_first_with=None):
    """API falsa: devolve até 2 registros com id > last_id."""
    state = {"failed": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access": "tok"})
        if fail_first_with and not state["failed"]:
            state["failed"] = True
            return httpx.Response(fail_first_with, headers={"Retry-After": "0"})
        last_id = int(request.url.params["last_id"])
        calls.append(last_id)
        ids = [i for i in data_ids if i > last_id][:2]
        return httpx.Response(200, json=[{"id": i} for i in ids])

    return handler


def test_paginacao_avanca_pelo_maior_id_e_para_no_vazio():
    calls = []
    client = make_client(fake_api([10, 11, 15, 20, 21], calls))
    batches = list(client.fetch_since(ENDPOINT, 1))

    assert [[r["id"] for r in b] for _, b in batches] == [[10, 11], [15, 20], [21]]
    assert calls == [1, 11, 20, 21]  # a última chamada volta vazia e encerra


def test_retry_em_rate_limit():
    calls = []
    client = make_client(fake_api([5], calls, fail_first_with=429))
    batches = list(client.fetch_since(ENDPOINT, 1))
    assert [r["id"] for _, b in batches for r in b] == [5]


def test_desiste_apos_max_tentativas():
    def always_503(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access": "tok"})
        return httpx.Response(503)

    client = make_client(always_503, max_attempts=3)
    with pytest.raises(RetryableHTTPError):
        list(client.fetch_since(ENDPOINT, 1))


def test_last_id_zero_e_rejeitado():
    client = make_client(fake_api([], []))
    with pytest.raises(ValueError):
        list(client.fetch_since(ENDPOINT, 0))
