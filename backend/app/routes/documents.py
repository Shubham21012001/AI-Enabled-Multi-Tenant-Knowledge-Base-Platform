import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_tenant_user, require_admin
from app.core.exceptions import ValidationError
from app.models import User
from app.schemas.common import DocumentOut
from app.services import document_service, rate_limiter
from app.services.processing import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Validates and stores the file, then processes it in the background.

    Returns 202 immediately with status="processing"; poll GET /documents/{id}.
    """
    rate_limiter.check("upload", f"user:{admin.id}", settings.RATE_LIMIT_UPLOAD)
    # Read at most limit+1 bytes so an oversized file is rejected without
    # loading all of it into memory.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit", code="file_too_large")
    doc = document_service.upload(db, admin, file.filename, data)
    background.add_task(process_document, doc.id)
    return doc


@router.get("/", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return document_service.list_documents(db, user)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: uuid.UUID, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return document_service.get_document(db, user, doc_id)


@router.post("/{doc_id}/reprocess", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def reprocess(
    doc_id: uuid.UUID, background: BackgroundTasks, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    doc = document_service.mark_for_reprocess(db, admin, doc_id)
    background.add_task(process_document, doc.id)
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    document_service.delete_document(db, admin, doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
