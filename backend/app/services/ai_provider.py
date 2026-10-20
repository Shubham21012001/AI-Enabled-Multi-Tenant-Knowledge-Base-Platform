"""Embedding + chat model access behind one small interface.

`GeminiProvider` uses google.genai (text-embedding-004, gemini-1.5-flash).
`FakeProvider` is a deterministic, offline stand-in used by the automated tests.
Production refuses to start with FakeProvider.
"""
import hashlib
import logging
import math
import re
from collections.abc import Iterator
from functools import lru_cache
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100


class AIProviderError(Exception):
    """Upstream AI call failed (network, temporary rate limit, 5xx). Retryable."""


class AIProviderUnavailable(AIProviderError):
    """Permanent until an operator acts (no credit, bad key, no model access)."""

    def __init__(self, reason: str):
        super().__init__(f"AI provider unavailable: {reason}")
        self.reason = reason


class AIProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def stream_chat(self, system: str, user: str) -> Iterator[str]: ...


class GeminiProvider:
    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        if not settings.GEMINI_API_KEY:
            raise AIProviderUnavailable("GEMINI_API_KEY is not configured")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.types = types

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        try:
            for i in range(0, len(texts), EMBED_BATCH_SIZE):
                batch = texts[i : i + EMBED_BATCH_SIZE]
                for text in batch:
                    result = self.client.models.embed_content(
                        model=settings.EMBEDDING_MODEL,
                        contents=text,
                    )
                    vectors.append(result.embeddings[0].values)
        except Exception as exc:
            msg = str(exc).lower()
            if "api_key" in msg or "invalid" in msg or "authenticate" in msg:
                raise AIProviderUnavailable("invalid_api_key") from exc
            if "quota" in msg or "limit" in msg:
                raise AIProviderUnavailable("insufficient_quota") from exc
            raise AIProviderError(f"Embedding request failed: {type(exc).__name__}: {exc}") from exc
        return vectors

    def stream_chat(self, system: str, user: str) -> Iterator[str]:
        try:
            prompt = f"{system}\n\n{user}"
            response = self.client.models.generate_content_stream(
                model=settings.CHAT_MODEL,
                contents=prompt,
                config=self.types.GenerateContentConfig(
                    temperature=settings.CHAT_TEMPERATURE,
                    max_output_tokens=settings.CHAT_MAX_TOKENS,
                ),
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            msg = str(exc).lower()
            if "api_key" in msg or "invalid" in msg or "authenticate" in msg:
                raise AIProviderUnavailable("invalid_api_key") from exc
            if "quota" in msg or "limit" in msg:
                raise AIProviderUnavailable("insufficient_quota") from exc
            raise AIProviderError(f"Chat request failed: {type(exc).__name__}: {exc}") from exc


# --- Offline fake ---------------------------------------------------------------

_STOPWORDS = set(
    "a an the is are was were be been of to in on for and or with what how who when where why "
    "which do does did can i we you our your my me us it its this that these those at by from as "
    "about tell please there their they have has had will would should could".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 1]


class FakeProvider:
    """Hashed bag-of-words embeddings + extractive answers for tests."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * settings.EMBEDDING_DIM
        for tok in _tokens(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % settings.EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def stream_chat(self, system: str, user: str) -> Iterator[str]:
        context, _, question = user.rpartition("QUESTION:")
        q_tokens = set(_tokens(question))
        best, best_score = None, 0
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", context):
            if sentence.startswith("[Source") or not sentence.strip():
                continue
            score = len(q_tokens & set(_tokens(sentence)))
            if score > best_score:
                best, best_score = sentence.strip(), score
        answer = best if best and best_score >= 2 else settings.NOT_FOUND_MESSAGE
        for word in answer.split(" "):
            yield word + " "


@lru_cache
def get_ai_provider() -> AIProvider:
    if settings.AI_PROVIDER == "fake":
        logger.warning("Using FakeProvider - answers are NOT generated by an LLM")
        return FakeProvider()
    if settings.AI_PROVIDER == "gemini":
        return GeminiProvider()
    raise AIProviderUnavailable("unknown_provider")