"""In-app notifications (plus email where useful). Always scoped to org + user."""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Notification, User
from app.models.enums import Role
from app.services.email import send_email


def notify_user(db: Session, user: User, type_: str, title: str, message: str, *, email: bool = False) -> None:
    if user.org_id is None:
        return
    db.add(Notification(org_id=user.org_id, user_id=user.id, type=type_, title=title, message=message))
    if email:
        send_email(user.email, f"KnowBot: {title}", message)


def notify_admins(db: Session, org_id: uuid.UUID, type_: str, title: str, message: str, *, email: bool = False) -> None:
    admins = db.scalars(
        select(User).where(User.org_id == org_id, User.role == Role.ADMIN.value, User.is_active.is_(True))
    ).all()
    for admin in admins:
        notify_user(db, admin, type_, title, message, email=email)


def list_for_user(db: Session, user: User, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    q = select(Notification).where(Notification.org_id == user.org_id, Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    return list(db.scalars(q.order_by(Notification.created_at.desc()).limit(limit)))


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.org_id == user.org_id,
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    ) or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> None:
    result = db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.org_id == user.org_id,
            Notification.user_id == user.id,
        )
        .values(is_read=True)
    )
    if result.rowcount == 0:
        raise NotFoundError("Notification not found")
    db.commit()


def mark_all_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(Notification.org_id == user.org_id, Notification.user_id == user.id)
        .values(is_read=True)
    )
    db.commit()
