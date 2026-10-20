from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.services import auth_service
from tests.conftest import Org


def test_register_creates_org_and_admin(client, org_a):
    assert org_a.me["email"] == "admin@acme.com"
    assert org_a.me["role"] == "admin"
    org = client.get("/organizations/me", headers=org_a.headers).json()
    assert org["name"] == "Acme Corp" and org["plan"] == "free" and org["members_count"] == 1


def test_register_rejects_privilege_fields(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "evil@x.com", "password": "Passw0rd123", "full_name": "E",
            "organization_name": "Evil", "role": "super_admin",
        },
    )
    assert r.status_code == 422
    r = client.post(
        "/auth/register",
        json={
            "email": "evil@x.com", "password": "Passw0rd123", "full_name": "E",
            "organization_name": "Evil", "org_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert r.status_code == 422


def test_duplicate_email_case_insensitive(client, org_a):
    r = client.post(
        "/auth/register",
        json={"email": "ADMIN@acme.com", "password": "Passw0rd123", "full_name": "X", "organization_name": "Other"},
    )
    assert r.status_code == 409


def test_weak_password_rejected(client):
    r = client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "short", "full_name": "A", "organization_name": "Org"},
    )
    assert r.status_code == 422


def test_login_success_and_wrong_password(client, org_a):
    r = client.post("/auth/login", json={"email": "admin@acme.com", "password": org_a.password})
    assert r.status_code == 200 and r.json()["access_token"]
    r = client.post("/auth/login", json={"email": "admin@acme.com", "password": "WrongPass123"})
    assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "nobody@acme.com", "password": "WrongPass123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"  # same message: no enumeration


def test_protected_route_requires_valid_token(client, org_a):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    # Token signed with a different secret
    forged = jwt.encode(
        {"sub": org_a.me["id"], "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "attacker-secret",
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_access_token_rejected(client, org_a):
    expired = jwt.encode(
        {"sub": org_a.me["id"], "type": "access", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_access_token_expiry_is_15_minutes(org_a):
    claims = jwt.get_unverified_claims(org_a.tokens["access_token"])
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert org_a.tokens["expires_in"] == 900


def test_refresh_rotation_and_reuse_detection(client, org_a):
    old = org_a.tokens["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    assert new != old
    # Re-using the rotated token is treated as theft: rejected and all sessions revoked.
    assert client.post("/auth/refresh", json={"refresh_token": old}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_logout_revokes_refresh_token(client, org_a):
    rt = org_a.tokens["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": rt}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_password_reset_flow(client, org_a, monkeypatch):
    sent = {}
    monkeypatch.setattr(auth_service, "send_email", lambda to, subject, body: sent.update(to=to, body=body))
    r = client.post("/auth/forgot-password", json={"email": "admin@acme.com"})
    assert r.status_code == 200
    token = sent["body"].split("token=")[1].split()[0]

    r = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd9"})
    assert r.status_code == 200
    # Token is single-use
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "Another1234"}).status_code == 422
    assert client.post("/auth/login", json={"email": "admin@acme.com", "password": "NewPassw0rd9"}).status_code == 200
    # Old sessions were revoked
    assert client.post("/auth/refresh", json={"refresh_token": org_a.tokens["refresh_token"]}).status_code == 401


def test_forgot_password_unknown_email_same_response(client):
    r = client.post("/auth/forgot-password", json={"email": "ghost@nowhere.com"})
    assert r.status_code == 200


def test_profile_update_and_change_password(client, org_a):
    r = client.patch("/auth/me", headers=org_a.headers, json={"full_name": "New Name"})
    assert r.status_code == 200 and r.json()["full_name"] == "New Name"
    # Role can't be changed through the profile endpoint
    assert client.patch("/auth/me", headers=org_a.headers, json={"full_name": "X", "role": "super_admin"}).status_code == 422

    r = client.post(
        "/auth/change-password", headers=org_a.headers,
        json={"current_password": "wrong-pass-1", "new_password": "Changed1234"},
    )
    assert r.status_code == 401
    r = client.post(
        "/auth/change-password", headers=org_a.headers,
        json={"current_password": org_a.password, "new_password": "Changed1234"},
    )
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": org_a.email, "password": "Changed1234"}).status_code == 200


def test_deactivated_user_blocked(client, org_a):
    from app.core.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    db.get(User, __import__("uuid").UUID(org_a.me["id"])).is_active = False
    db.commit()
    db.close()
    assert client.get("/auth/me", headers=org_a.headers).status_code == 401


def test_password_is_hashed_with_bcrypt(org_a):
    from app.core.database import SessionLocal
    from app.models import User
    from sqlalchemy import select

    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == org_a.email))
    db.close()
    assert user.hashed_password.startswith("$2b$") and org_a.password not in user.hashed_password


def test_second_org_is_independent(client, org_a):
    b = Org(client, "Beta", "boss@beta.com")
    assert b.org_id != org_a.org_id
