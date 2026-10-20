"""Subscription plan limits and usage enforcement.

Limits are always checked with real COUNT(*) queries scoped to the org, so the
denormalised counters on `organizations` can never let an org exceed its plan.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError
from app.models import Document, Invitation, Organization, PlanUsage, User
from app.models.enums import Plan

WARNING_THRESHOLD = 0.8


@dataclass(frozen=True)
class PlanLimits:
    members: int | None  # None = unlimited
    documents: int | None
    questions_per_month: int | None


PLAN_LIMITS: dict[str, PlanLimits] = {
    Plan.FREE.value: PlanLimits(members=3, documents=5, questions_per_month=100),
    Plan.PRO.value: PlanLimits(members=20, documents=50, questions_per_month=5000),
    Plan.ENTERPRISE.value: PlanLimits(members=None, documents=None, questions_per_month=None),
}


def limits_for(org: Organization) -> PlanLimits:
    return PLAN_LIMITS.get(org.plan, PLAN_LIMITS[Plan.FREE.value])


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def count_members(db: Session, org_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.org_id == org_id)) or 0


def count_pending_invites(db: Session, org_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    return db.scalar(
        select(func.count()).select_from(Invitation).where(
            Invitation.org_id == org_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > now,
        )
    ) or 0


def count_documents(db: Session, org_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Document).where(Document.org_id == org_id)) or 0


def questions_used(db: Session, org_id: uuid.UUID, month: str | None = None) -> int:
    return db.scalar(
        select(PlanUsage.questions_used).where(
            PlanUsage.org_id == org_id, PlanUsage.month == (month or current_month())
        )
    ) or 0


def ensure_can_add_member(db: Session, org: Organization) -> None:
    limit = limits_for(org).members
    # Pending invitations reserve seats, otherwise an admin could invite 50
    # people on the free plan and have them all accept.
    if limit is not None and count_members(db, org.id) + count_pending_invites(db, org.id) >= limit:
        raise PlanLimitError(f"Your {org.plan} plan allows {limit} members. Upgrade to add more.")


def ensure_can_add_document(db: Session, org: Organization) -> None:
    limit = limits_for(org).documents
    if limit is not None and count_documents(db, org.id) >= limit:
        raise PlanLimitError(f"Your {org.plan} plan allows {limit} documents. Upgrade to upload more.")


def ensure_can_ask(db: Session, org: Organization) -> None:
    limit = limits_for(org).questions_per_month
    if limit is not None and questions_used(db, org.id) >= limit:
        raise PlanLimitError(
            f"Your organization has used all {limit} questions for this month. Upgrade to continue."
        )


def record_question(db: Session, org: Organization) -> tuple[int, int | None]:
    """Atomically increment this month's question counter. Returns (used, limit)."""
    month = current_month()
    stmt = (
        insert(PlanUsage)
        .values(id=uuid.uuid4(), org_id=org.id, month=month, questions_used=1, docs_count=0)
        .on_conflict_do_update(
            constraint="uq_plan_usage_org_month",
            set_={"questions_used": PlanUsage.questions_used + 1},
        )
        .returning(PlanUsage.questions_used)
    )
    used = db.execute(stmt).scalar_one()
    return used, limits_for(org).questions_per_month


def sync_docs_count(db: Session, org: Organization) -> None:
    """Keep organizations.docs_count and this month's plan_usage.docs_count accurate."""
    count = count_documents(db, org.id)
    org.docs_count = count
    stmt = (
        insert(PlanUsage)
        .values(id=uuid.uuid4(), org_id=org.id, month=current_month(), questions_used=0, docs_count=count)
        .on_conflict_do_update(constraint="uq_plan_usage_org_month", set_={"docs_count": count})
    )
    db.execute(stmt)


def sync_members_count(db: Session, org: Organization) -> None:
    org.members_count = count_members(db, org.id)


def usage_ratio(used: int, limit: int | None) -> float:
    return 0.0 if not limit else used / limit


def is_warning(used: int, limit: int | None) -> bool:
    return limit is not None and WARNING_THRESHOLD <= usage_ratio(used, limit) < 1.0


def usage_summary(db: Session, org: Organization) -> dict:
    limits = limits_for(org)
    members = count_members(db, org.id)
    docs = count_documents(db, org.id)
    questions = questions_used(db, org.id)

    def item(used: int, limit: int | None) -> dict:
        return {
            "used": used,
            "limit": limit,
            "remaining": None if limit is None else max(limit - used, 0),
            "percent": round(usage_ratio(used, limit) * 100, 1),
            "warning": is_warning(used, limit),
            "blocked": limit is not None and used >= limit,
        }

    return {
        "plan": org.plan,
        "month": current_month(),
        "members": item(members, limits.members),
        "documents": item(docs, limits.documents),
        "questions": item(questions, limits.questions_per_month),
    }
