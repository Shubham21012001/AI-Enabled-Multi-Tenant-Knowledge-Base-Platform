"""Admin analytics. Every query is filtered by the admin's org_id."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models import Conversation, Document, User
from app.models.enums import DocumentStatus, Feedback
from app.services import plans
from app.services.org_service import get_org


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def overview(db: Session, admin: User, days: int = 30) -> dict:
    org = get_org(db, admin.org_id)
    org_id = org.id
    since = _since(days)

    totals = db.execute(
        select(
            func.count(),
            func.count().filter(Conversation.is_answered.is_(False)),
            func.count().filter(Conversation.from_cache.is_(True)),
            func.count().filter(Conversation.feedback == Feedback.THUMBS_UP.value),
            func.count().filter(Conversation.feedback == Feedback.THUMBS_DOWN.value),
        ).where(Conversation.org_id == org_id, Conversation.created_at >= since)
    ).one()
    total, unanswered, cached, up, down = totals

    doc_status = dict(
        db.execute(
            select(Document.status, func.count()).where(Document.org_id == org_id).group_by(Document.status)
        ).all()
    )

    return {
        "organization": {"id": str(org.id), "name": org.name, "plan": org.plan},
        "usage": plans.usage_summary(db, org),
        "period_days": days,
        "questions": {
            "total": total,
            "answered": total - unanswered,
            "unanswered": unanswered,
            "answer_rate": round((total - unanswered) / total * 100, 1) if total else None,
            "cache_hits": cached,
        },
        "feedback": {"thumbs_up": up, "thumbs_down": down},
        "documents": {s.value: doc_status.get(s.value, 0) for s in DocumentStatus},
        "daily_questions": daily_questions(db, org_id, days),
        "most_asked": most_asked(db, org_id, days),
        "most_cited_documents": most_cited_documents(db, org_id),
        "knowledge_gaps": knowledge_gaps(db, org_id, days),
    }


def daily_questions(db: Session, org_id, days: int) -> list[dict]:
    day = cast(func.timezone("UTC", Conversation.created_at), Date)
    rows = dict(
        db.execute(
            select(day, func.count())
            .where(Conversation.org_id == org_id, Conversation.created_at >= _since(days))
            .group_by(day)
        ).all()
    )
    today = datetime.now(timezone.utc).date()
    # Fill missing days with zero so the chart has a continuous x-axis.
    return [
        {"date": (d := today - timedelta(days=i)).isoformat(), "count": rows.get(d, 0)}
        for i in range(days - 1, -1, -1)
    ]


def _normalized_question():
    return func.lower(func.trim(Conversation.question))


def most_asked(db: Session, org_id, days: int, limit: int = 10) -> list[dict]:
    q = _normalized_question()
    rows = db.execute(
        select(func.min(Conversation.question), func.count().label("n"))
        .where(Conversation.org_id == org_id, Conversation.created_at >= _since(days))
        .group_by(q)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [{"question": r[0], "count": r[1]} for r in rows]


def knowledge_gaps(db: Session, org_id, days: int, limit: int = 10) -> list[dict]:
    """Questions KnowBot couldn't answer, or whose answers got a thumbs down."""
    q = _normalized_question()
    unanswered = func.count().filter(Conversation.is_answered.is_(False))
    downvoted = func.count().filter(Conversation.feedback == Feedback.THUMBS_DOWN.value)
    rows = db.execute(
        select(func.min(Conversation.question), unanswered, downvoted, func.max(Conversation.created_at))
        .where(
            Conversation.org_id == org_id,
            Conversation.created_at >= _since(days),
            (Conversation.is_answered.is_(False)) | (Conversation.feedback == Feedback.THUMBS_DOWN.value),
        )
        .group_by(q)
        .order_by((unanswered + downvoted).desc(), func.max(Conversation.created_at).desc())
        .limit(limit)
    ).all()
    return [
        {
            "question": r[0],
            "unanswered_count": r[1],
            "thumbs_down_count": r[2],
            "last_asked": r[3].isoformat(),
        }
        for r in rows
    ]


def most_cited_documents(db: Session, org_id, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(Document.id, Document.original_filename, Document.file_type, Document.question_count)
        .where(Document.org_id == org_id, Document.question_count > 0)
        .order_by(Document.question_count.desc())
        .limit(limit)
    ).all()
    return [
        {"document_id": str(r[0]), "document_name": r[1], "file_type": r[2], "question_count": r[3]}
        for r in rows
    ]
