"""Configuração: variáveis de ambiente e definição das entidades extraídas."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Entity:
    name: str                    # nome lógico; vira prefixo no lake e tabela no raw
    endpoint: str                # caminho na API
    state_field: str             # campo de estado usado na regra de reextração
    final_states: frozenset[str] # estados que não mudam mais


ENTITIES: dict[str, Entity] = {
    "payments": Entity(
        name="payments",
        endpoint="/api/api-v2/payments/",
        state_field="payment_state",
        final_states=frozenset({"Pago", "Cancelado"}),
    ),
    "contracts": Entity(
        name="contracts",
        endpoint="/api/api-v2/contracts/",
        state_field="contract_state",
        final_states=frozenset({"Encerrado", "Finalizado", "Reprovado", "Cancelado"}),
    ),
}


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_email: str | None
    api_password: str | None
    use_synthetic: bool
    s3_endpoint_url: str | None  # None = AWS de verdade
    s3_bucket: str
    s3_region: str
    pg_conninfo: str
    reextract_max_ids: int       # teto da janela de reextração (em ids)


def get_settings() -> Settings:
    env = os.environ
    return Settings(
        api_base_url=env.get("API_BASE_URL", "https://api.example.com"),
        api_email=env.get("API_EMAIL"),
        api_password=env.get("API_PASSWORD"),
        use_synthetic=env.get("USE_SYNTHETIC_DATA", "true").lower() == "true",
        s3_endpoint_url=env.get("S3_ENDPOINT_URL") or None,
        s3_bucket=env.get("S3_BUCKET", "raw"),
        s3_region=env.get("S3_REGION", "us-east-1"),
        pg_conninfo=(
            f"host={env.get('POSTGRES_HOST', 'localhost')} "
            f"port={env.get('POSTGRES_PORT', '5432')} "
            f"dbname={env['POSTGRES_DB']} "
            f"user={env['POSTGRES_USER']} "
            f"password={env['POSTGRES_PASSWORD']}"
        ),
        reextract_max_ids=int(env.get("REEXTRACT_MAX_IDS", "5000")),
    )
