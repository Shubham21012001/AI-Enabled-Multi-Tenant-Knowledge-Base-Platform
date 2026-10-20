import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import Principal, get_principal, get_tenant_user
from app.models import User
from app.schemas.common import AskRequest, ConversationOut, ConversationPage, FeedbackRequest
from app.services import chat_service, conversation_service, rate_limiter

router = APIRouter(tags=["chat"])


@router.post("/chat/ask")
def ask(data: AskRequest, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Ask a question. Streams Server-Sent Events (text/event-stream).

    Authenticate with `Authorization: Bearer <access token>` or `X-API-Key`.
    """
    rate_limiter.check("chat", principal.rate_limit_key, settings.RATE_LIMIT_CHAT)
    chat_service.precheck(db, principal)
    return StreamingResponse(
        chat_service.stream_answer(principal, data.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # disable nginx buffering
    )


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200),
    user: User = Depends(get_tenant_user),
    db: Session = Depends(get_db),
):
    items, total = conversation_service.list_for_user(db, user, limit=limit, offset=offset, q=q)
    return ConversationPage(items=items, total=total)


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: uuid.UUID, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return conversation_service.get_for_user(db, user, conv_id)


@router.put("/conversations/{conv_id}/feedback", response_model=ConversationOut)
def set_feedback(
    conv_id: uuid.UUID, data: FeedbackRequest, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)
):
    return conversation_service.set_feedback(db, user, conv_id, data.feedback)


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: uuid.UUID, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    conversation_service.delete_for_user(db, user, conv_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
