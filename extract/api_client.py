"""Cliente da API SEED: autenticação, retry com backoff e paginação por last_id."""
import logging
from collections.abc import Iterator

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)

AUTH_ENDPOINT = "/api/token/"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    """Erro temporário (rate limit ou falha do servidor): vale tentar de novo."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


_exponential = wait_exponential_jitter(initial=1, max=30)


def _wait(retry_state) -> float:
    # Se a API disser quanto esperar (Retry-After), respeita; senão, backoff exponencial.
    exc = retry_state.outcome.exception()
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        return min(retry_after, 60)
    return _exponential(retry_state)


class SeedClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        timeout: float = 60,
        max_attempts: int = 5,
        wait=_wait,
        transport: httpx.BaseTransport | None = None,  # injetável nos testes
    ):
        self._email = email
        self._password = password
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._token: str | None = None
        self._retrying = Retrying(
            retry=retry_if_exception_type((RetryableHTTPError, httpx.TransportError)),
            wait=wait,
            stop=stop_after_attempt(max_attempts),
            reraise=True,
            before_sleep=lambda rs: log.warning(
                "Tentativa %s falhou (%s). Nova tentativa em %.1fs",
                rs.attempt_number, rs.outcome.exception(), rs.next_action.sleep,
            ),
        )

    def _authenticate(self) -> None:
        resp = self._http.post(AUTH_ENDPOINT, json={"email": self._email, "password": self._password})
        if resp.status_code != 200:
            # não loga o corpo da requisição: contém a senha
            raise RuntimeError(f"Falha ao autenticar (HTTP {resp.status_code})")
        self._token = resp.json()["access"]

    def _get_once(self, endpoint: str, params: dict) -> list[dict]:
        if self._token is None:
            self._authenticate()
        resp = self._http.get(endpoint, params=params, headers={"Authorization": f"Bearer {self._token}"})

        if resp.status_code == 401:
            # token expirou no meio da extração: renova e tenta de novo
            self._token = None
            raise RetryableHTTPError("Token expirado (HTTP 401)", retry_after=0)
        if resp.status_code in RETRYABLE_STATUS:
            retry_after = resp.headers.get("Retry-After")
            raise RetryableHTTPError(
                f"HTTP {resp.status_code} em {endpoint}",
                retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        resp.raise_for_status()

        data = resp.json()
        if isinstance(data, dict) and "results" in data:  # caso a API passe a paginar com envelope
            data = data["results"]
        if not isinstance(data, list):
            raise ValueError(f"Resposta inesperada de {endpoint}: esperado uma lista")
        return data

    def get(self, endpoint: str, params: dict) -> list[dict]:
        return self._retrying(self._get_once, endpoint, params)

    def fetch_since(self, endpoint: str, last_id: int) -> Iterator[tuple[int, list[dict]]]:
        """Busca registros com id > last_id, em lotes.

        A API devolve só ids maiores que last_id. Usamos o maior id recebido como
        próximo last_id até a resposta vir vazia. Rende (last_id_usado, lote).
        """
        if last_id < 1:
            raise ValueError("A API exige last_id >= 1")
        while True:
            batch = self.get(endpoint, {"last_id": last_id})
            if not batch:
                return
            yield last_id, batch
            next_id = max(int(r["id"]) for r in batch)
            if next_id <= last_id:  # proteção contra laço infinito
                raise RuntimeError(f"API não avançou: last_id={last_id}, maior id recebido={next_id}")
            last_id = next_id

    def close(self) -> None:
        self._http.close()
