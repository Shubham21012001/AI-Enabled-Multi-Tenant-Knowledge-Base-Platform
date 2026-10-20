"""Conversation history and feedback. Users only ever see their own Q&A."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Conversation, User


def _own(user: User):
    return (Conversation.org_id == user.org_id, Conversation.user_id == user.id)


def list_for_user(db: Session, user: User, *, limit: int = 50, offset: int = 0, q: str | None = None) -> tuple[list[Conversation], int]:
    filters = list(_own(user))
    if q:
        filters.append(Conversation.question.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(Conversation).where(*filters)) or 0
    items = db.scalars(
        select(Conversation).where(*filters).order_by(Conversation.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


def get_for_user(db: Session, user: User, conv_id: uuid.UUID) -> Conversation:
    conv = db.scalar(select(Conversation).where(Conversation.id == conv_id, *_own(user)))
    if conv is None:
        raise NotFoundError("Conversation not found")
    return conv


def set_feedback(db: Session, user: User, conv_id: uuid.UUID, feedback: str | None) -> Conversation:
    conv = get_for_user(db, user, conv_id)
    conv.feedback = feedback
    db.commit()
    return conv


def delete_for_user(db: Session, user: User, conv_id: uuid.UUID) -> None:
    conv = get_for_user(db, user, conv_id)
    db.delete(conv)
    db.commit()
