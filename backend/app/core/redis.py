import redis

from app.core.config import settings

# decode_responses=False because the semantic cache stores raw float32 bytes.
redis_client: redis.Redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)


def get_redis() -> redis.Redis:
    return redis_client
