"""Redis fixed-window rate limiter.

Each (scope, identity) pair gets a counter key that expires at the end of the
window. INCR is atomic, so concurrent requests can't race past the limit.
"""
import logging

import redis

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def parse_rule(rule: str) -> tuple[int, int]:
    limit, window = rule.split("/")
    return int(limit), int(window)


def check(scope: str, identity: str, rule: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    limit, window = parse_rule(rule)
    key = f"ratelimit:{scope}:{identity}"
    r = get_redis()
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        count, _ = pipe.execute()
        if count > limit:
            ttl = r.ttl(key)
            raise RateLimitError("Too many requests. Please slow down.", retry_after=max(int(ttl), 1))
    except redis.RedisError:
        # Fail open: a Redis outage must not take down login or chat entirely.
        logger.warning("Rate limiter unavailable (Redis error); allowing request scope=%s", scope)
