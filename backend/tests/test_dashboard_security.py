from app.core.config import settings
from app.services import rate_limiter
from tests.conftest import HR_POLICY, PRODUCT_MANUAL, ask

LEAVE_Q = "How many days of paid annual leave does each employee receive?"


def test_dashboard_statistics(client, org_a, org_b):
    doc_id = org_a.upload("leave-policy.txt", HR_POLICY).json()["id"]
    org_a.invite_member("emp@acme.com")
    org_a.ask(LEAVE_Q)
    org_a.ask(LEAVE_Q)
    conv = org_a.ask("What is the parking policy for visitors?")  # not in docs
    client.put(f"/conversations/{conv['done']['conversation_id']}/feedback", headers=org_a.headers, json={"feedback": "thumbs_down"})

    # Org B activity must not leak into Org A's dashboard
    org_b.upload("engine.txt", PRODUCT_MANUAL)
    org_b.ask("What is the maximum thrust of the engine?")

    d = client.get("/dashboard", headers=org_a.headers).json()
    assert d["usage"]["documents"]["used"] == 1
    assert d["usage"]["members"]["used"] == 2
    assert d["usage"]["questions"] == {
        "used": 3, "limit": 100, "remaining": 97, "percent": 3.0, "warning": False, "blocked": False,
    }
    assert d["questions"]["total"] == 3 and d["questions"]["unanswered"] == 1 and d["questions"]["cache_hits"] == 1
    assert len(d["daily_questions"]) == 30 and d["daily_questions"][-1]["count"] == 3
    assert d["most_asked"][0] == {"question": LEAVE_Q, "count": 2}
    assert d["most_cited_documents"][0]["document_id"] == doc_id
    gaps = d["knowledge_gaps"]
    assert len(gaps) == 1 and gaps[0]["question"].startswith("What is the parking policy")
    assert gaps[0]["unanswered_count"] == 1 and gaps[0]["thumbs_down_count"] == 1
    assert all("thrust" not in q["question"] for q in d["most_asked"])
    assert d["feedback"]["thumbs_down"] == 1


def test_rate_limit_chat(client, org_a, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT", "3/60")
    statuses = [ask(client, org_a.headers, f"question {i}")["status"] for i in range(4)]
    assert statuses == [200, 200, 200, 429]


def test_rate_limit_login(client, org_a, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/60")
    codes = [client.post("/auth/login", json={"email": org_a.email, "password": "Wrong12345"}).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]
    r = client.post("/auth/login", json={"email": org_a.email, "password": "Wrong12345"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_rate_limit_upload(client, org_a, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOAD", "2/60")
    codes = [org_a.upload(f"d{i}.txt", HR_POLICY).status_code for i in range(3)]
    assert codes == [202, 202, 429]


def test_rate_limiter_fails_open_without_redis(monkeypatch):
    import redis

    class Broken:
        def pipeline(self):
            raise redis.ConnectionError("down")

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(rate_limiter, "get_redis", lambda: Broken())
    rate_limiter.check("x", "y", "1/60")  # must not raise


def test_notifications_are_private(client, org_a, org_b):
    org_a.upload("leave-policy.txt", HR_POLICY)
    a_notes = client.get("/notifications", headers=org_a.headers).json()
    assert a_notes["unread"] == 1 and a_notes["items"][0]["type"] == "document_ready"
    note_id = a_notes["items"][0]["id"]
    assert client.get("/notifications", headers=org_b.headers).json()["items"] == []
    assert client.post(f"/notifications/{note_id}/read", headers=org_b.headers).status_code == 404
    assert client.post(f"/notifications/{note_id}/read", headers=org_a.headers).status_code == 204
    assert client.get("/notifications", headers=org_a.headers).json()["unread"] == 0


def test_security_headers_and_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok", "redis": "ok"}
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_cors_only_allows_configured_origin(client):
    ok = client.options("/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_sql_injection_in_search_is_inert(client, org_a):
    r = client.get("/conversations", headers=org_a.headers, params={"q": "'; DROP TABLE users; --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/auth/me", headers=org_a.headers).status_code == 200


def test_invalid_uuid_path_rejected(client, org_a):
    assert client.get("/documents/not-a-uuid", headers=org_a.headers).status_code == 422


def test_production_settings_reject_weak_secret():
    import pytest

    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="short", AI_PROVIDER="openai")
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 40, AI_PROVIDER="fake")


def test_token_refresh_not_limited_by_login_budget(client, org_a, monkeypatch):
    """Regression: page reloads refresh tokens; they must not share the strict login limit."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "2/60")
    rt = org_a.tokens["refresh_token"]
    for _ in range(5):
        r = client.post("/auth/refresh", json={"refresh_token": rt})
        assert r.status_code == 200, r.text
        rt = r.json()["refresh_token"]
