from __future__ import annotations
import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from infrastructure.logger import log


class CacheClient:
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            log.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            log.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    @retry(
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get(self, key: str) -> str | None:
        if not self.redis:
            return None
        try:
            return self.redis.get(key)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            log.error(f"Redis get error: {e}")
            return None

    @retry(
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def set(self, key: str, value: str, expire: int = 86400) -> None:
        if not self.redis:
            return
        try:
            self.redis.set(key, value, ex=expire)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            log.error(f"Redis set error: {e}")

    def delete(self, key: str) -> None:
        if not self.redis:
            return
        try:
            self.redis.delete(key)
        except Exception as e:
            log.error(f"Redis delete error: {e}")


cache_client = CacheClient()
