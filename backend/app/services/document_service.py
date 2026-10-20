"""Document upload, listing and deletion (all scoped to the caller's org)."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models import Document, User
from app.models.enums import DocumentStatus
from app.services import plans, semantic_cache
from app.services.org_service import get_org
from app.services.storage import get_storage, make_key
from app.utils.files import ALLOWED_EXTENSIONS, content_matches_type, get_extension, sanitize_display_name

logger = logging.getLogger(__name__)


def upload(db: Session, admin: User, original_name: str | None, data: bytes) -> Document:
    display_name = sanitize_display_name(original_name)
    ext = get_extension(display_name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Only PDF, DOCX and TXT files are supported", code="invalid_file_type")
    if len(data) == 0:
        raise ValidationError("The file is empty", code="empty_file")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(
            f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit", code="file_too_large"
        )
    if not content_matches_type(data, ext):
        raise ValidationError(
            f"File content doesn't match the .{ext} extension", code="invalid_file_content"
        )

    org = get_org(db, admin.org_id)
    plans.ensure_can_add_document(db, org)

    filename, key = make_key(org.id, ext)
    doc = Document(
        org_id=org.id,
        filename=filename,
        original_filename=display_name,
        file_path=key,
        file_size=len(data),
        file_type=ext,
        status=DocumentStatus.UPLOADING.value,
        created_by=admin.id,
    )
    db.add(doc)
    db.flush()
    get_storage().save(key, data)
    doc.status = DocumentStatus.PROCESSING.value
    plans.sync_docs_count(db, org)
    db.commit()
    logger.info("Uploaded doc_id=%s org_id=%s type=%s size=%d", doc.id, org.id, ext, len(data))
    return doc


def list_documents(db: Session, user: User) -> list[Document]:
    return list(
        db.scalars(select(Document).where(Document.org_id == user.org_id).order_by(Document.created_at.desc()))
    )


def get_document(db: Session, user: User, doc_id: uuid.UUID) -> Document:
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == user.org_id))
    if doc is None:
        raise NotFoundError("Document not found")
    return doc


def delete_document(db: Session, admin: User, doc_id: uuid.UUID) -> None:
    doc = get_document(db, admin, doc_id)
    key = doc.file_path
    db.delete(doc)  # chunks are removed by ON DELETE CASCADE
    db.flush()
    plans.sync_docs_count(db, get_org(db, admin.org_id))
    db.commit()
    try:
        get_storage().delete(key)
    except Exception:
        logger.exception("Failed to delete stored file for doc_id=%s", doc_id)
    # Cached answers may cite this document — drop them.
    semantic_cache.invalidate_org(admin.org_id)
    logger.info("Deleted doc_id=%s org_id=%s", doc_id, admin.org_id)


def mark_for_reprocess(db: Session, admin: User, doc_id: uuid.UUID) -> Document:
    doc = get_document(db, admin, doc_id)
    if doc.status != DocumentStatus.FAILED.value:
        raise ValidationError("Only failed documents can be reprocessed")
    doc.status = DocumentStatus.PROCESSING.value
    doc.error_message = None
    doc.processing_attempts = 0
    db.commit()
    return doc
