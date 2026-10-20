from sqlalchemy import update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import PlanUsage
from app.services import plans
from tests.conftest import HR_POLICY, PRODUCT_MANUAL, ask

LEAVE_Q = "How many days of paid annual leave does each employee receive?"


def test_streaming_answer_with_sources(client, org_a):
    doc_id = org_a.upload("leave-policy.txt", HR_POLICY).json()["id"]
    r = org_a.ask(LEAVE_Q)
    assert r["status"] == 200
    assert r["content_type"].startswith("text/event-stream")
    # Streamed progressively: many token events, not one blob.
    assert sum(1 for e in r["events"] if e["type"] == "token") > 3
    assert "24 days" in r["answer"]
    assert r["meta"]["cached"] is False
    src = r["sources"][0]
    assert src["document_id"] == doc_id and src["document_name"] == "leave-policy.txt" and src["chunk_index"] == 0
    assert r["done"]["conversation_id"]


def test_not_found_without_documents(org_a):
    r = org_a.ask("What is the CEO's favourite colour?")
    assert r["answer"] == settings.NOT_FOUND_MESSAGE
    assert r["sources"] == []


def test_not_found_for_unrelated_question(org_a):
    org_a.upload("leave-policy.txt", HR_POLICY)
    r = org_a.ask("What is the capital city of Australia?")
    assert r["answer"] == settings.NOT_FOUND_MESSAGE
    assert r["sources"] == []


def test_retrieval_is_tenant_isolated(client, org_a, org_b):
    org_a.upload("leave-policy.txt", HR_POLICY)
    org_b.upload("engine-manual.txt", PRODUCT_MANUAL)

    # Org B asks about Org A's content: must not find it.
    r = org_b.ask(LEAVE_Q)
    assert r["answer"] == settings.NOT_FOUND_MESSAGE
    assert r["sources"] == []
    # And vice versa.
    r = org_a.ask("What is the maximum thrust of the rocket engine?")
    assert r["answer"] == settings.NOT_FOUND_MESSAGE
    # Each org can find its own content.
    r = org_b.ask("What is the maximum thrust of the rocket engine?")
    assert "900 kilonewtons" in r["answer"]
    assert all(s["document_name"] == "engine-manual.txt" for s in r["sources"])


def test_chunk_repository_never_returns_other_org(client, org_a, org_b):
    import uuid

    from app.repositories.chunk_repository import search_similar
    from app.services.ai_provider import FakeProvider

    org_a.upload("leave-policy.txt", HR_POLICY)
    vec = FakeProvider().embed([LEAVE_Q])[0]
    db = SessionLocal()
    try:
        assert search_similar(db, uuid.UUID(org_b.org_id), vec, 5) == []
        assert len(search_similar(db, uuid.UUID(org_a.org_id), vec, 5)) >= 1
    finally:
        db.close()


def test_conversation_saved_and_private(client, org_a):
    org_a.upload("leave-policy.txt", HR_POLICY)
    member = org_a.invite_member("emp@acme.com")
    org_a.ask(LEAVE_Q)
    ask(client, member, "How many days of sick leave do employees get?")

    admin_hist = client.get("/conversations", headers=org_a.headers).json()
    member_hist = client.get("/conversations", headers=member).json()
    assert admin_hist["total"] == 1 and member_hist["total"] == 1
    assert admin_hist["items"][0]["question"] == LEAVE_Q
    assert "sick leave" in member_hist["items"][0]["question"]
    assert member_hist["items"][0]["sources"]

    # A member cannot read, rate or delete someone else's conversation.
    admin_conv = admin_hist["items"][0]["id"]
    assert client.get(f"/conversations/{admin_conv}", headers=member).status_code == 404
    assert client.put(f"/conversations/{admin_conv}/feedback", headers=member, json={"feedback": "thumbs_down"}).status_code == 404
    assert client.delete(f"/conversations/{admin_conv}", headers=member).status_code == 404


def test_conversation_search(client, org_a):
    org_a.ask("first question about 100% things")
    org_a.ask("second question")
    r = client.get("/conversations", headers=org_a.headers, params={"q": "100%"}).json()
    assert r["total"] == 1


def test_feedback(client, org_a):
    org_a.upload("leave-policy.txt", HR_POLICY)
    conv_id = org_a.ask(LEAVE_Q)["done"]["conversation_id"]
    r = client.put(f"/conversations/{conv_id}/feedback", headers=org_a.headers, json={"feedback": "thumbs_up"})
    assert r.status_code == 200 and r.json()["feedback"] == "thumbs_up"
    assert client.put(f"/conversations/{conv_id}/feedback", headers=org_a.headers, json={"feedback": "love"}).status_code == 422
    r = client.put(f"/conversations/{conv_id}/feedback", headers=org_a.headers, json={"feedback": None})
    assert r.json()["feedback"] is None


def test_question_count_incremented_for_cited_docs(client, org_a):
    doc_id = org_a.upload("leave-policy.txt", HR_POLICY).json()["id"]
    org_a.ask(LEAVE_Q)
    assert client.get(f"/documents/{doc_id}", headers=org_a.headers).json()["question_count"] == 1


def test_semantic_cache_hit(client, org_a):
    org_a.upload("leave-policy.txt", HR_POLICY)
    first = org_a.ask(LEAVE_Q)
    second = org_a.ask(LEAVE_Q)
    assert first["meta"]["cached"] is False
    assert second["meta"]["cached"] is True
    assert second["answer"] == first["answer"]
    assert second["sources"] == first["sources"]
    # Cached answers still count as questions and are saved.
    assert second["done"]["usage"]["used"] == 2


def test_semantic_cache_is_org_scoped(client, org_a, org_b):
    org_a.upload("leave-policy.txt", HR_POLICY)
    org_a.ask(LEAVE_Q)  # populates Org A's cache
    r = org_b.ask(LEAVE_Q)
    assert r["meta"]["cached"] is False
    assert r["answer"] == settings.NOT_FOUND_MESSAGE


def test_cache_invalidated_when_documents_change(client, org_a):
    doc_id = org_a.upload("leave-policy.txt", HR_POLICY).json()["id"]
    org_a.ask(LEAVE_Q)
    client.delete(f"/documents/{doc_id}", headers=org_a.headers)
    r = org_a.ask(LEAVE_Q)
    assert r["meta"]["cached"] is False
    assert r["answer"] == settings.NOT_FOUND_MESSAGE


def _set_questions_used(org_id: str, used: int):
    db = SessionLocal()
    plans_month = plans.current_month()
    existing = db.query(PlanUsage).filter_by(org_id=org_id, month=plans_month).first()
    if existing:
        existing.questions_used = used
    else:
        db.add(PlanUsage(org_id=org_id, month=plans_month, questions_used=used, docs_count=0))
    db.commit()
    db.close()


def test_usage_warning_at_80_percent(client, org_a):
    _set_questions_used(org_a.org_id, 79)  # free plan: 100/month
    r = org_a.ask("anything")
    assert r["done"]["usage"] == {"used": 80, "limit": 100, "warning": True, "remaining": 20}
    notes = client.get("/notifications", headers=org_a.headers).json()
    assert any(n["type"] == "usage_warning" for n in notes["items"])
    usage = client.get("/organizations/me/usage", headers=org_a.headers).json()
    assert usage["questions"]["warning"] is True


def test_questions_blocked_at_100_percent(client, org_a):
    _set_questions_used(org_a.org_id, 100)
    r = org_a.ask("anything")
    assert r["status"] == 402
    assert r["json"]["code"] == "plan_limit_reached"
    # Enterprise is unlimited
    client.put("/organizations/me/plan", headers=org_a.headers, json={"plan": "enterprise"})
    assert org_a.ask("anything")["status"] == 200


def test_question_validation(client, org_a):
    assert ask(client, org_a.headers, "   ")["status"] == 422
    assert ask(client, org_a.headers, "x" * 2001)["status"] == 422


def test_chat_requires_auth(client):
    r = client.post("/chat/ask", json={"question": "hi"})
    assert r.status_code == 401


def test_api_key_lifecycle_and_chat(client, org_a, org_b):
    org_a.upload("leave-policy.txt", HR_POLICY)
    r = client.post("/api-keys", headers=org_a.headers, json={"name": "Slack bot"})
    assert r.status_code == 201
    raw, key_id = r.json()["key"], r.json()["id"]
    assert raw.startswith("kb_live_")

    # Listing never returns the raw key.
    listed = client.get("/api-keys", headers=org_a.headers).json()
    assert "key" not in listed[0] and listed[0]["prefix"] == raw[:14]

    # The DB stores only a hash.
    from app.models import ApiKey

    db = SessionLocal()
    stored = db.get(ApiKey, key_id)
    db.close()
    assert stored.key_hash != raw and raw not in stored.key_hash

    # Use the key to ask a question.
    r = ask(client, {"X-API-Key": raw}, LEAVE_Q)
    assert r["status"] == 200 and "24 days" in r["answer"]
    assert client.get("/api-keys", headers=org_a.headers).json()[0]["usage_count"] == 1

    # Another org can't revoke it.
    assert client.delete(f"/api-keys/{key_id}", headers=org_b.headers).status_code == 404
    # Revoke -> rejected.
    assert client.delete(f"/api-keys/{key_id}", headers=org_a.headers).status_code == 204
    assert ask(client, {"X-API-Key": raw}, LEAVE_Q)["status"] == 401
    assert ask(client, {"X-API-Key": "kb_live_doesnotexist"}, LEAVE_Q)["status"] == 401


def test_llm_failure_streams_error_and_does_not_count(client, org_a, monkeypatch):
    from app.services import ai_provider

    org_a.upload("leave-policy.txt", HR_POLICY)

    def broken(self, system, user):
        raise ai_provider.AIProviderError("down")
        yield  # pragma: no cover

    monkeypatch.setattr(ai_provider.FakeProvider, "stream_chat", broken)
    r = org_a.ask(LEAVE_Q)
    assert r["status"] == 200 and r["error"]["type"] == "error"
    assert client.get("/conversations", headers=org_a.headers).json()["total"] == 0
    db = SessionLocal()
    try:
        assert plans.questions_used(db, org_a.org_id) == 0
    finally:
        db.close()
