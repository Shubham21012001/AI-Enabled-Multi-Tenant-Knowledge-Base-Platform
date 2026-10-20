"""Import every model so Alembic autogenerate and relationships can see them."""
from app.core.database import Base
from app.models.api_key import ApiKey
from app.models.auth_tokens import Invitation, PasswordResetToken, RefreshToken
from app.models.conversation import Conversation
from app.models.document import Document, DocumentChunk
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.plan_usage import PlanUsage
from app.models.user import User

__all__ = [
    "Base",
    "ApiKey",
    "Conversation",
    "Document",
    "DocumentChunk",
    "Invitation",
    "Notification",
    "Organization",
    "PasswordResetToken",
    "PlanUsage",
    "RefreshToken",
    "User",
]
