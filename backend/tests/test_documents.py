import io

from docx import Document as DocxDocument
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import DocumentChunk
from tests.conftest import HR_POLICY


def _chunk_count(doc_id: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    finally:
        db.close()


def make_docx(text: str) -> bytes:
    doc = DocxDocument()
    for para in text.split("\n\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_returns_processing_then_ready(client, org_a):
    r = org_a.upload("policy.txt", HR_POLICY)
    assert r.status_code == 202
    body = r.json()
    # The response is sent before the pipeline runs.
    assert body["status"] == "processing"
    # TestClient runs background tasks after the response; by now it's done.
    doc = client.get(f"/documents/{body['id']}", headers=org_a.headers).json()
    assert doc["status"] == "ready", doc
    assert doc["chunk_count"] >= 1
    assert _chunk_count(body["id"]) == doc["chunk_count"]


def test_upload_docx(client, org_a):
    r = org_a.upload(
        "handbook.docx", make_docx(HR_POLICY.decode()),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert r.status_code == 202
    assert client.get(f"/documents/{r.json()['id']}", headers=org_a.headers).json()["status"] == "ready"


def test_invalid_extension_rejected(org_a):
    r = org_a.upload("malware.exe", b"MZ\x90\x00", "application/octet-stream")
    assert r.status_code == 422 and r.json()["code"] == "invalid_file_type"


def test_content_must_match_extension(org_a):
    r = org_a.upload("fake.pdf", b"this is not a pdf", "application/pdf")
    assert r.status_code == 422 and r.json()["code"] == "invalid_file_content"
    r = org_a.upload("fake.docx", b"PK\x03\x04garbage", "application/octet-stream")
    assert r.status_code == 422


def test_empty_file_rejected(org_a):
    assert org_a.upload("empty.txt", b"").status_code == 422


def test_oversized_file_rejected(org_a):
    big = b"a" * (settings.max_upload_bytes + 10)
    r = org_a.upload("big.txt", big)
    assert r.status_code in (413, 422)
    assert r.json()["code"] == "file_too_large"


def test_path_traversal_filename_is_neutralised(client, org_a):
    r = org_a.upload("../../../etc/passwd.txt", HR_POLICY)
    assert r.status_code == 202
    body = r.json()
    assert body["original_filename"] == "passwd.txt"
    db = SessionLocal()
    from app.models import Document

    doc = db.get(Document, body["id"])
    db.close()
    assert ".." not in doc.file_path and doc.file_path.startswith(org_a.org_id + "/")


def test_unextractable_pdf_marked_failed(client, org_a):
    # Valid PDF header but no readable pages.
    r = org_a.upload("scan.pdf", b"%PDF-1.4\n%broken\n", "application/pdf")
    assert r.status_code == 202
    doc = client.get(f"/documents/{r.json()['id']}", headers=org_a.headers).json()
    assert doc["status"] == "failed"
    assert doc["error_message"]


def test_processing_retries_transient_errors(client, org_a, monkeypatch):
    from app.services import ai_provider

    calls = {"n": 0}
    real = ai_provider.FakeProvider.embed

    def flaky(self, texts):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ai_provider.AIProviderError("temporary")
        return real(self, texts)

    monkeypatch.setattr(ai_provider.FakeProvider, "embed", flaky)
    r = org_a.upload("policy.txt", HR_POLICY)
    doc = client.get(f"/documents/{r.json()['id']}", headers=org_a.headers).json()
    assert doc["status"] == "ready" and calls["n"] == 3


def test_processing_fails_after_3_attempts(client, org_a, monkeypatch):
    from app.services import ai_provider

    def broken(self, texts):
        raise ai_provider.AIProviderError("down")

    monkeypatch.setattr(ai_provider.FakeProvider, "embed", broken)
    r = org_a.upload("policy.txt", HR_POLICY)
    doc_id = r.json()["id"]
    from app.models import Document

    db = SessionLocal()
    doc = db.get(Document, doc_id)
    db.close()
    assert doc.status == "failed" and doc.processing_attempts == 3

    # Failure notification for the uploader
    notes = client.get("/notifications", headers=org_a.headers).json()
    assert any(n["type"] == "document_failed" for n in notes["items"])

    # Reprocess once the provider recovers
    monkeypatch.undo()
    r = client.post(f"/documents/{doc_id}/reprocess", headers=org_a.headers)
    assert r.status_code == 202
    assert client.get(f"/documents/{doc_id}", headers=org_a.headers).json()["status"] == "ready"


def test_member_can_list_but_not_upload_or_delete(client, org_a):
    doc_id = org_a.upload("policy.txt", HR_POLICY).json()["id"]
    m = org_a.invite_member("emp@acme.com")
    assert len(client.get("/documents/", headers=m).json()) == 1
    r = client.post("/documents/upload", headers=m, files={"file": ("x.txt", b"hello world", "text/plain")})
    assert r.status_code == 403
    assert client.delete(f"/documents/{doc_id}", headers=m).status_code == 403


def test_delete_document_removes_chunks(client, org_a):
    doc_id = org_a.upload("policy.txt", HR_POLICY).json()["id"]
    assert _chunk_count(doc_id) > 0
    assert client.delete(f"/documents/{doc_id}", headers=org_a.headers).status_code == 204
    assert _chunk_count(doc_id) == 0
    assert client.get(f"/documents/{doc_id}", headers=org_a.headers).status_code == 404
    assert client.get("/organizations/me", headers=org_a.headers).json()["docs_count"] == 0


def test_cross_tenant_document_access_blocked(client, org_a, org_b):
    doc_id = org_a.upload("policy.txt", HR_POLICY).json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=org_b.headers).status_code == 404
    assert client.delete(f"/documents/{doc_id}", headers=org_b.headers).status_code == 404
    assert client.post(f"/documents/{doc_id}/reprocess", headers=org_b.headers).status_code == 404
    assert client.get("/documents/", headers=org_b.headers).json() == []
    # Org A's document still exists
    assert client.get(f"/documents/{doc_id}", headers=org_a.headers).status_code == 200


def test_free_plan_document_limit(client, org_a):
    for i in range(5):
        assert org_a.upload(f"doc{i}.txt", HR_POLICY).status_code == 202
    r = org_a.upload("doc6.txt", HR_POLICY)
    assert r.status_code == 402 and r.json()["code"] == "plan_limit_reached"


def test_quota_exhausted_fails_fast_without_retries(client, org_a, monkeypatch):
    """No OpenAI credit / bad key is permanent: one attempt, clear message."""
    from app.services import ai_provider

    calls = {"n": 0}

    def no_credit(self, texts):
        calls["n"] += 1
        raise ai_provider.AIProviderUnavailable("insufficient_quota")

    monkeypatch.setattr(ai_provider.FakeProvider, "embed", no_credit)
    doc = client.get(f"/documents/{org_a.upload('policy.txt', HR_POLICY).json()['id']}", headers=org_a.headers).json()
    assert doc["status"] == "failed" and calls["n"] == 1
    assert "AI service is currently unavailable" in doc["error_message"]
    assert "quota" not in doc["error_message"]  # provider details stay in server logs
