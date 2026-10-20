"""Redis semantic cache, scoped per organisation.

Layout (all keys include the org_id, so one org can never read another's):
    semcache:{org_id}:index        sorted set  entry_id -> created timestamp
    semcache:{org_id}:entry:{id}   hash        embedding(float32 bytes), question, answer, sources

Lookup embeds the question and compares it (cosine similarity, numpy) against
the org's recent entries. Similarity > 0.92 = cache hit. Linear scan over at
most SEMANTIC_CACHE_MAX_ENTRIES vectors per org is ~1 ms and needs no Redis
modules (redis:7-alpine doesn't ship RediSearch).
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass

import numpy as np
import redis

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass
class CacheHit:
    answer: str
    sources: list[dict]
    similarity: float


def _index_key(org_id: uuid.UUID) -> str:
    return f"semcache:{org_id}:index"


def _entry_key(org_id: uuid.UUID, entry_id: str) -> str:
    return f"semcache:{org_id}:entry:{entry_id}"


def lookup(org_id: uuid.UUID, embedding: list[float]) -> CacheHit | None:
    r = get_redis()
    try:
        ids = r.zrevrange(_index_key(org_id), 0, settings.SEMANTIC_CACHE_MAX_ENTRIES - 1)
        if not ids:
            return None
        pipe = r.pipeline()
        for entry_id in ids:
            pipe.hgetall(_entry_key(org_id, entry_id.decode()))
        entries = pipe.execute()

        query = np.asarray(embedding, dtype=np.float32)
        query /= np.linalg.norm(query) or 1.0
        best: tuple[float, dict] | None = None
        expired = []
        for entry_id, entry in zip(ids, entries):
            if not entry:  # TTL expired; clean the index lazily
                expired.append(entry_id)
                continue
            vec = np.frombuffer(entry[b"embedding"], dtype=np.float32)
            sim = float(np.dot(query, vec / (np.linalg.norm(vec) or 1.0)))
            if best is None or sim > best[0]:
                best = (sim, entry)
        if expired:
            r.zrem(_index_key(org_id), *expired)
        if best and best[0] > settings.SEMANTIC_CACHE_THRESHOLD:
            entry = best[1]
            return CacheHit(
                answer=entry[b"answer"].decode(),
                sources=json.loads(entry[b"sources"]),
                similarity=best[0],
            )
    except redis.RedisError:
        logger.warning("Semantic cache lookup failed (Redis error); continuing without cache")
    return None


def store(org_id: uuid.UUID, question: str, embedding: list[float], answer: str, sources: list[dict]) -> None:
    r = get_redis()
    entry_id = uuid.uuid4().hex
    ttl = settings.SEMANTIC_CACHE_TTL_SECONDS
    try:
        pipe = r.pipeline()
        pipe.hset(
            _entry_key(org_id, entry_id),
            mapping={
                "embedding": np.asarray(embedding, dtype=np.float32).tobytes(),
                "question": question,
                "answer": answer,
                "sources": json.dumps(sources),
            },
        )
        pipe.expire(_entry_key(org_id, entry_id), ttl)
        pipe.zadd(_index_key(org_id), {entry_id: time.time()})
        pipe.expire(_index_key(org_id), ttl)
        # Keep the index bounded: drop the oldest entries beyond the cap.
        pipe.zremrangebyrank(_index_key(org_id), 0, -settings.SEMANTIC_CACHE_MAX_ENTRIES - 1)
        pipe.execute()
    except redis.RedisError:
        logger.warning("Semantic cache store failed (Redis error)")


def invalidate_org(org_id: uuid.UUID) -> None:
    """Drop all cached answers for an org (after its documents change)."""
    r = get_redis()
    try:
        keys = list(r.scan_iter(match=f"semcache:{org_id}:*", count=500))
        if keys:
            r.delete(*keys)
    except redis.RedisError:
        logger.warning("Semantic cache invalidation failed for org_id=%s", org_id)
