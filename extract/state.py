"""Estado da extração: calcula o last_id a partir do que já está no raw."""
import psycopg
from psycopg import sql

from extract.config import Entity


def next_last_id(conn: psycopg.Connection, entity: Entity, max_window: int) -> int:
    """Regra de reextração.

    - Tabela vazia: começa do 1 (a API exige last_id >= 1).
    - Senão: volta até o menor id ainda em estado não final, para recapturar
      registros que podem ter mudado (ex.: pendente -> pago).
    - Teto: no máximo `max_window` ids para trás do maior id, para um registro
      esquecido como pendente não forçar uma reextração enorme.
    """
    row = conn.execute(sql.SQL("""
        SELECT
            max(id) AS max_id,
            min(id) FILTER (WHERE NOT (payload ->> {state_field} = ANY(%(finals)s))) AS min_open_id
        FROM raw.{table}
    """).format(
        table=sql.Identifier(entity.name),
        state_field=sql.Literal(entity.state_field),
    ), {"finals": list(entity.final_states)}).fetchone()

    max_id, min_open_id = row
    if max_id is None:
        return 1
    if min_open_id is None:
        return max_id
    return max(min_open_id - 1, max_id - max_window, 1)
