from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import client_ip, get_current_user
from app.models import User
from app.schemas.auth import (
    AcceptInvitationRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InvitationInfo,
    LoginRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth_service, rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Create a new organization and its first admin account."""
    rate_limiter.check("register", client_ip(request), settings.RATE_LIMIT_REGISTER)
    _, tokens = auth_service.register(db, data)
    return tokens


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("login", client_ip(request), settings.RATE_LIMIT_LOGIN)
    # Also limit per target account, so a distributed attack can't hammer one user.
    rate_limiter.check("login-email", data.email.lower(), settings.RATE_LIMIT_LOGIN)
    user = auth_service.authenticate(db, data.email, data.password)
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("refresh", client_ip(request), settings.RATE_LIMIT_REFRESH)
    return auth_service.refresh(db, data.refresh_token)


@router.post("/logout", response_model=Message)
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    auth_service.logout(db, data.refresh_token)
    return Message(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name.strip()
    db.commit()
    return user


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    data: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Changes the password, signs out every other session, returns fresh tokens."""
    auth_service.change_password(db, user, data.current_password, data.new_password)
    return auth_service.issue_tokens(db, user)


@router.post("/forgot-password", response_model=Message)
def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("forgot", client_ip(request), settings.RATE_LIMIT_PASSWORD_RESET)
    auth_service.request_password_reset(db, data.email)
    return Message(message="If an account exists for that email, a reset link has been sent.")


@router.post("/reset-password", response_model=Message)
def reset_password(data: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("reset", client_ip(request), settings.RATE_LIMIT_PASSWORD_RESET)
    auth_service.reset_password(db, data.token, data.new_password)
    return Message(message="Password updated. Please sign in.")


@router.get("/invitations/{token}", response_model=InvitationInfo)
def invitation_info(token: str, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("invite-lookup", client_ip(request), settings.RATE_LIMIT_LOGIN)
    return auth_service.invitation_info(db, token)


@router.post("/accept-invite", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def accept_invite(data: AcceptInvitationRequest, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check("accept-invite", client_ip(request), settings.RATE_LIMIT_LOGIN)
    _, tokens = auth_service.accept_invitation(db, data)
    return tokens
