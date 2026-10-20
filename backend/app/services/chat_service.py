"""The /chat/ask flow, emitted as Server-Sent Events.

    question → embedding → semantic cache? ─hit─→ stream cached answer
                                │miss
                                ↓
                  pgvector top-5 (org-scoped) → relevant? ─no─→ "not found" (no LLM call)
                                │yes
                                ↓
                  gpt-4o-mini (streamed) → sources → save conversation → cache

SSE event payloads (JSON in `data:`):
    {"type":"meta","cached":bool}
    {"type":"token","content":"..."}
    {"type":"sources","sources":[...]}
    {"type":"done","conversation_id":"...","usage":{...}}
    {"type":"error","message":"..."}
"""
import json
import logging
import math
import uuid
from collections.abc import Iterator

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import Principal
from app.models import Conversation, Document
from app.repositories.chunk_repository import search_similar
from app.services import notification_service, plans, rag_service, semantic_cache
from app.services.ai_provider import AIProviderUnavailable, get_ai_provider
from app.services.org_service import get_org

logger = logging.getLogger(__name__)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def precheck(db: Session, principal: Principal) -> None:
    """Runs before streaming starts so plan errors become proper HTTP responses."""
    plans.ensure_can_ask(db, get_org(db, principal.org_id))


def stream_answer(principal: Principal, question: str) -> Iterator[str]:
    # The request-scoped DB session is closed before a StreamingResponse body
    # runs, so the generator owns its own session.
    db = SessionLocal()
    try:
        yield from _stream(db, principal, question)
    except AIProviderUnavailable as exc:
        db.rollback()
        logger.error("AI provider unavailable (%s) for chat org_id=%s", exc.reason, principal.org_id)
        yield sse({"type": "error", "message": "KnowBot's AI service is temporarily unavailable. Please try again later."})
    except Exception:
        db.rollback()
        logger.exception("Chat failed org_id=%s", principal.org_id)
        yield sse({"type": "error", "message": "Something went wrong while generating the answer. Please try again."})
    finally:
        db.close()


def _stream(db: Session, principal: Principal, question: str) -> Iterator[str]:
    provider = get_ai_provider()
    org_id = principal.org_id
    query_vec = provider.embed([question])[0]

    # 1) Semantic cache (org-scoped)
    hit = semantic_cache.lookup(org_id, query_vec)
    if hit:
        yield sse({"type": "meta", "cached": True})
        for piece in _split_for_streaming(hit.answer):
            yield sse({"type": "token", "content": piece})
        yield sse({"type": "sources", "sources": hit.sources})
        conv_id, usage = _finish(db, principal, question, hit.answer, hit.sources, answered=True, cached=True)
        yield sse({"type": "done", "conversation_id": str(conv_id), "usage": usage})
        return

    yield sse({"type": "meta", "cached": False})

    # 2) Retrieval (org-scoped)
    chunks = search_similar(db, org_id, query_vec, settings.RETRIEVAL_TOP_K)
    relevant = [c for c in chunks if c.similarity >= settings.RETRIEVAL_MIN_SIMILARITY]

    # 3) Generation — or a deterministic "not found" without calling the LLM.
    if not relevant:
        answer = settings.NOT_FOUND_MESSAGE
        for piece in _split_for_streaming(answer):
            yield sse({"type": "token", "content": piece})
    else:
        parts: list[str] = []
        for token in provider.stream_chat(
            rag_service.SYSTEM_PROMPT, rag_service.build_user_prompt(question, relevant)
        ):
            parts.append(token)
            yield sse({"type": "token", "content": token})
        answer = "".join(parts).strip()

    answered = not rag_service.is_not_found(answer)
    sources = rag_service.build_sources(answer, relevant) if answered else []
    yield sse({"type": "sources", "sources": sources})

    conv_id, usage = _finish(db, principal, question, answer, sources, answered=answered, cached=False)
    if answered:
        semantic_cache.store(org_id, question, query_vec, answer, sources)
    yield sse({"type": "done", "conversation_id": str(conv_id), "usage": usage})


def _finish(
    db: Session, principal: Principal, question: str, answer: str, sources: list[dict], *, answered: bool, cached: bool
) -> tuple[uuid.UUID, dict]:
    org = get_org(db, principal.org_id)
    conv = Conversation(
        user_id=principal.user_id,
        api_key_id=principal.api_key_id,
        org_id=org.id,
        question=question,
        answer=answer,
        sources=sources,
        is_answered=answered,
        from_cache=cached,
    )
    db.add(conv)
    doc_ids = {uuid.UUID(s["document_id"]) for s in sources}
    if doc_ids:
        db.execute(
            update(Document)
            .where(Document.id.in_(doc_ids), Document.org_id == org.id)
            .values(question_count=Document.question_count + 1)
        )
    used, limit = plans.record_question(db, org)
    if limit and used == math.ceil(limit * plans.WARNING_THRESHOLD):
        notification_service.notify_admins(
            db,
            org.id,
            "usage_warning",
            "80% of monthly questions used",
            f"Your organization has used {used} of {limit} questions this month.",
            email=True,
        )
    db.commit()
    usage = {
        "used": used,
        "limit": limit,
        "warning": plans.is_warning(used, limit),
        "remaining": None if limit is None else max(limit - used, 0),
    }
    return conv.id, usage


def _split_for_streaming(text: str) -> list[str]:
    words = text.split(" ")
    return [w + (" " if i < len(words) - 1 else "") for i, w in enumerate(words)]
