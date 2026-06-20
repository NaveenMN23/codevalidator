import redis
import redis.exceptions
import json
import hashlib
from loguru import logger
from src.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class CacheClient:
    def __init__(self):
        self._connect()

    def _connect(self):
        try:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=5
            )
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        reraise=False
    )
    def get_blueprint(self, challenge_id: str) -> dict:
        if not self.redis: return None
        key = f"blueprint:{challenge_id}"
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            logger.error(f"Error reading blueprint from Redis: {e}")
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        reraise=False
    )
    def get_semantic_cache(self, challenge_id: str, diff_hash: str) -> dict:
        if not self.redis: return None
        key = f"eval_cache:{challenge_id}:{diff_hash}"
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            logger.error(f"Error reading semantic cache from Redis: {e}")
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        reraise=False
    )
    def set_semantic_cache(self, challenge_id: str, diff_hash: str, feedback: dict):
        if not self.redis: return
        key = f"eval_cache:{challenge_id}:{diff_hash}"
        try:
            self.redis.set(key, json.dumps(feedback), ex=86400) # 24h cache
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            logger.error(f"Failed to set semantic cache: {e}")

    def get_diff_hash(self, diff: str) -> str:
        return hashlib.sha256(diff.encode()).hexdigest()

cache_client = CacheClient()
