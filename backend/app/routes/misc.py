"""Dashboard, API keys, notifications and health."""
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_tenant_user, require_admin
from app.core.redis import get_redis
from app.models import User
from app.schemas.common import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, NotificationList, NotificationOut
from app.services import api_key_service, dashboard_service, notification_service, rate_limiter

router = APIRouter()


@router.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", **checks}, status_code=200 if ok else 503)


# --- Dashboard ---

@router.get("/dashboard", tags=["dashboard"])
def dashboard(
    days: int = Query(30, ge=1, le=90), admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return dashboard_service.overview(db, admin, days)


# --- API keys ---

@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED, tags=["api keys"])
def create_key(data: ApiKeyCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rate_limiter.check("api-keys", f"user:{admin.id}", settings.RATE_LIMIT_API_KEYS)
    key, raw = api_key_service.create(db, admin, data.name)
    return ApiKeyCreated.model_validate({**ApiKeyOut.model_validate(key).model_dump(), "key": raw})


@router.get("/api-keys", response_model=list[ApiKeyOut], tags=["api keys"])
def list_keys(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return api_key_service.list_keys(db, admin)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["api keys"])
def revoke_key(key_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    api_key_service.revoke(db, admin, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Notifications ---

@router.get("/notifications", response_model=NotificationList, tags=["notifications"])
def list_notifications(
    unread_only: bool = False, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)
):
    return NotificationList(
        items=notification_service.list_for_user(db, user, unread_only=unread_only),
        unread=notification_service.unread_count(db, user),
    )


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, tags=["notifications"])
def read_notification(
    notification_id: uuid.UUID, user: User = Depends(get_tenant_user), db: Session = Depends(get_db)
):
    notification_service.mark_read(db, user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, tags=["notifications"])
def read_all(user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    notification_service.mark_all_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
