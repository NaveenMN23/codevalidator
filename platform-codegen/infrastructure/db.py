"""Postgres client for codegen — blueprint persistence only."""
from __future__ import annotations
import json
import psycopg
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from infrastructure.logger import log

_TRANSIENT = (psycopg.OperationalError,)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(_TRANSIENT),
    reraise=True,
)
def save_blueprint(problem_id: str, blueprint: dict) -> None:
    """Write blueprint JSON into problems.blueprint by slug."""
    with psycopg.connect(settings.postgres_dsn) as conn:
        cur = conn.execute(
            "UPDATE problems SET blueprint = %s::jsonb WHERE slug = %s",
            (json.dumps(blueprint), problem_id),
        )
        if cur.rowcount == 0:
            log.warning(
                f"[blueprint] No problems row with slug={problem_id!r} — "
                f"blueprint not persisted to DB"
            )
        conn.commit()
    log.info(f"[blueprint] Saved to problems.blueprint: {problem_id}")
