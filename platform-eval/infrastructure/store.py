"""
Session store: Redis hot + Postgres-first write-through.
"""
from __future__ import annotations
import json
import psycopg
from infrastructure.logger import log
from infrastructure.cache import cache_client
from config.settings import settings

_SESSION_KEY_PREFIX = "eval:session:"
_MEMORY_STORE: dict[str, dict] = {}           # used when STORE_BACKEND=memory
_MEMORY_BLUEPRINT_STORE: dict[str, dict] = {} # used when STORE_BACKEND=memory
_CREATE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS eval_sessions (
    id TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""


def _session_key(session_id: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{session_id}"


def init_schema() -> None:
    """Called on service lifespan startup to ensure the eval_sessions table exists."""
    try:
        with psycopg.connect(settings.postgres_dsn) as conn:
            conn.execute(_CREATE_SESSIONS_SQL)
            conn.commit()
        log.info("eval_sessions table ready")
    except Exception as e:
        log.error(f"Failed to init eval schema: {e}")


class SessionStore:
    def save(self, session_id: str, session_data: dict) -> None:
        """Postgres-first write-through, then Redis. In-memory when STORE_BACKEND=memory."""
        if settings.store_backend == "memory":
            _MEMORY_STORE[session_id] = session_data
            return

        raw = json.dumps(session_data)

        # 1. Postgres (durable)
        try:
            with psycopg.connect(settings.postgres_dsn) as conn:
                conn.execute(
                    """
                    INSERT INTO eval_sessions (id, data, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (id) DO UPDATE
                        SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    (session_id, raw),
                )
                conn.commit()
        except Exception as e:
            log.error(f"Postgres save failed for session {session_id}: {e}")
            raise

        # 2. Redis (hot cache)
        try:
            cache_client.set(_session_key(session_id), raw, expire=settings.session_ttl_seconds)
        except Exception as e:
            log.warning(f"Redis warm failed for session {session_id}: {e}")
            # Non-fatal — Postgres is the source of truth

    def load(self, session_id: str) -> dict | None:
        """Redis-first; rehydrates from Postgres on miss. In-memory when STORE_BACKEND=memory."""
        if settings.store_backend == "memory":
            return _MEMORY_STORE.get(session_id)

        # 1. Redis
        try:
            raw = cache_client.get(_session_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.warning(f"Redis load failed for session {session_id}: {e}")

        # 2. Postgres fallback
        try:
            with psycopg.connect(settings.postgres_dsn) as conn:
                row = conn.execute(
                    "SELECT data FROM eval_sessions WHERE id = %s", (session_id,)
                ).fetchone()
            if row:
                data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                # Re-warm Redis
                try:
                    cache_client.set(
                        _session_key(session_id),
                        json.dumps(data),
                        expire=settings.session_ttl_seconds,
                    )
                except Exception:
                    pass
                return data
        except Exception as e:
            log.error(f"Postgres load failed for session {session_id}: {e}")

        return None

    def save_blueprint(self, problem_id: str, data: dict) -> None:
        """Write blueprint into problems.blueprint (by slug) and warm Redis cache."""
        if settings.store_backend == "memory":
            _MEMORY_BLUEPRINT_STORE[problem_id] = data
            return

        raw = json.dumps(data)
        try:
            with psycopg.connect(settings.postgres_dsn) as conn:
                cur = conn.execute(
                    "UPDATE problems SET blueprint = %s::jsonb WHERE slug = %s",
                    (raw, problem_id),
                )
                if cur.rowcount == 0:
                    log.warning(
                        f"save_blueprint: no problems row with slug={problem_id!r} — "
                        f"blueprint not persisted to DB"
                    )
                conn.commit()
        except Exception as e:
            log.error(f"Postgres save_blueprint failed for {problem_id}: {e}")
            raise

        try:
            cache_client.set(f"blueprint:{problem_id}", raw, expire=3600)
        except Exception as e:
            log.warning(f"Redis warm failed for blueprint {problem_id}: {e}")

    def load_blueprint(self, problem_id: str) -> dict | None:
        """Read problems.blueprint by slug. Caller handles Redis caching."""
        if settings.store_backend == "memory":
            return _MEMORY_BLUEPRINT_STORE.get(problem_id)

        try:
            with psycopg.connect(settings.postgres_dsn) as conn:
                row = conn.execute(
                    "SELECT blueprint FROM problems WHERE slug = %s", (problem_id,)
                ).fetchone()
            if row and row[0] is not None:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception as e:
            log.error(f"Postgres load_blueprint failed for {problem_id}: {e}")
        return None


session_store = SessionStore()
