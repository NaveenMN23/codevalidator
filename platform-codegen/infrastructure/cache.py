import os
import redis
import hashlib
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from infrastructure.logger import log

class CacheClient:
    def __init__(self):
        self.host = os.environ.get('REDIS_HOST', 'localhost')
        self.port = int(os.environ.get('REDIS_PORT', 6379))
        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            log.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            log.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    def get_cache_key(self, challenge_name: str, language: str, tags: list, source_hash: str = "") -> str:
        config = {
            "name": challenge_name,
            "lang": language,
            "tags": sorted(tags),
            "v": source_hash,  # changes when gold-master files change, auto-invalidates stale scaffolds
        }
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    @retry(
        retry=retry_if_exception_type((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def get(self, key: str) -> str:
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
        reraise=True
    )
    def set(self, key: str, value: str, expire: int = 86400):
        if not self.redis:
            return
        try:
            self.redis.set(key, value, ex=expire)
            log.info(f"Cached key {key} for {expire}s")
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            raise
        except Exception as e:
            log.error(f"Redis set error: {e}")

cache_client = CacheClient()
