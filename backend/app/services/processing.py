"""Background document processing: extract → clean → chunk → embed → store.

Runs via FastAPI BackgroundTasks after the upload response has been sent, so
the user never waits for the AI pipeline. We chose this over Celery because a
final-year-scale deployment doesn't need a separate broker/worker fleet; the
trade-off (in-flight jobs lost if the process dies) is covered by
`resume_pending()`, which re-queues unfinished documents on startup.
"""
import logging
import threading
import time
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.models import Document, DocumentChunk, User
from app.models.enums import DocumentStatus
from app.services import notification_service, semantic_cache
from app.services.ai_provider import AIProviderUnavailable, get_ai_provider
from app.services.chunking import chunk_text
from app.services.extraction import ExtractionError, extract_text
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

RETRY_BACKOFF_SECONDS = (2, 5, 10)
AI_UNAVAILABLE_MESSAGE = "The AI service is currently unavailable. Please retry processing later."


def process_document(doc_id: uuid.UUID) -> None:
    """Entry point for the background task. Never raises."""
    db = SessionLocal()
    try:
        _process_with_retries(db, doc_id)
    except Exception:
        logger.exception("Unexpected error processing doc_id=%s", doc_id)
    finally:
        db.close()


def _process_with_retries(db: Session, doc_id: uuid.UUID) -> None:
    max_attempts = settings.PROCESSING_MAX_ATTEMPTS
    last_error = "Unknown error"
    for attempt in range(1, max_attempts + 1):
        doc = db.get(Document, doc_id)
        if doc is None:
            logger.info("doc_id=%s was deleted before processing finished", doc_id)
            return
        doc.processing_attempts = attempt
        db.commit()
        try:
            chunk_count = _run_pipeline(db, doc)
        except ExtractionError as exc:
            # Bad file — retrying won't help.
            db.rollback()
            _mark_failed(db, doc_id, str(exc))
            return
        except AIProviderUnavailable as exc:
            # No credit / bad key: permanent until an operator fixes it.
            db.rollback()
            logger.error("AI provider unavailable (%s) while processing doc_id=%s", exc.reason, doc_id)
            _mark_failed(db, doc_id, AI_UNAVAILABLE_MESSAGE)
            return
        except Exception as exc:
            db.rollback()
            last_error = "Processing failed. Please try again later."
            logger.warning(
                "Processing attempt %d/%d failed doc_id=%s: %s", attempt, max_attempts, doc_id, type(exc).__name__
            )
            if attempt < max_attempts:
                time.sleep(RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)])
            continue
        logger.info("Processed doc_id=%s chunks=%d attempt=%d", doc_id, chunk_count, attempt)
        return
    _mark_failed(db, doc_id, last_error)


def _run_pipeline(db: Session, doc: Document) -> int:
    data = get_storage().read(doc.file_path)
    text = extract_text(data, doc.file_type)
    chunks = chunk_text(text)
    if not chunks:
        raise ExtractionError("No text found in this document")
    vectors = get_ai_provider().embed(chunks)
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch")

    # Idempotent: a retry or reprocess replaces any partial earlier result.
    db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc.id))
    db.add_all(
        DocumentChunk(doc_id=doc.id, org_id=doc.org_id, content=content, embedding=vec, chunk_index=i)
        for i, (content, vec) in enumerate(zip(chunks, vectors))
    )
    doc.status = DocumentStatus.READY.value
    doc.chunk_count = len(chunks)
    doc.error_message = None
    _notify_uploader(
        db, doc, "document_ready", "Document ready", f'"{doc.original_filename}" is ready for questions.'
    )
    db.commit()
    # New knowledge may change answers that were previously "not found".
    semantic_cache.invalidate_org(doc.org_id)
    return len(chunks)


def _mark_failed(db: Session, doc_id: uuid.UUID, message: str) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        return
    doc.status = DocumentStatus.FAILED.value
    doc.error_message = message[:500]
    _notify_uploader(
        db, doc, "document_failed", "Document processing failed", f'"{doc.original_filename}": {message}'
    )
    db.commit()
    logger.warning("Marked doc_id=%s as failed: %s", doc_id, message)


def _notify_uploader(db: Session, doc: Document, type_: str, title: str, message: str) -> None:
    if doc.created_by is None:
        return
    user = db.scalar(select(User).where(User.id == doc.created_by, User.org_id == doc.org_id))
    if user:
        notification_service.notify_user(db, user, type_, title, message, email=type_ == "document_failed")


def resume_pending() -> None:
    """Re-queue documents left in uploading/processing by a previous crash/restart.

    With several Uvicorn workers every worker runs startup, so a short Redis
    lock ensures only one of them resumes the backlog.
    """
    try:
        if not get_redis().set("lock:resume-documents", "1", nx=True, ex=60):
            return
    except Exception:
        logger.warning("Could not take resume lock (Redis unavailable); resuming anyway")
    db = SessionLocal()
    try:
        ids = db.scalars(
            select(Document.id).where(
                Document.status.in_([DocumentStatus.PROCESSING.value, DocumentStatus.UPLOADING.value])
            )
        ).all()
    finally:
        db.close()
    if not ids:
        return
    logger.info("Resuming %d unfinished document(s)", len(ids))

    def _run() -> None:
        for doc_id in ids:
            process_document(doc_id)

    threading.Thread(target=_run, name="resume-documents", daemon=True).start()
