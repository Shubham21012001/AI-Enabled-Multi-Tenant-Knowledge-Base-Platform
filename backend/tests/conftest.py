"""Test setup: real PostgreSQL+pgvector and Redis (from docker compose), isolated
in the `knowbot_test` database and Redis DB 15. The AI provider is the offline
FakeProvider, so tests are deterministic and free.
"""
import json
import os
import tempfile

# Must be set before any `app` import reads settings.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "AI_PROVIDER": "fake",
        "DATABASE_URL": os.getenv(
            "TEST_DATABASE_URL", "postgresql+psycopg2://knowbot:knowbot_dev_password@localhost:5432/knowbot_test"
        ),
        "REDIS_URL": os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15"),
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-1234567890",
        "UPLOAD_DIR": tempfile.mkdtemp(prefix="knowbot-test-uploads-"),
        "RATE_LIMIT_ENABLED": "false",
        "EMAIL_PROVIDER": "console",
        "LOG_LEVEL": "WARNING",
    }
)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import get_redis
from app.main import app
from app.services import processing

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    """Build the schema with the real Alembic migrations (this also tests them)."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    with engine.begin() as conn:
        # Fail fast (instead of hanging) if a test leaked an open transaction.
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    get_redis().flushdb()
    # Don't actually sleep between processing retries in tests.
    monkeypatch.setattr(processing, "RETRY_BACKOFF_SECONDS", (0, 0, 0))
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --- helpers -------------------------------------------------------------------

class Org:
    def __init__(self, client: TestClient, name: str, email: str, password: str = "Passw0rd123"):
        r = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": f"{name} Admin", "organization_name": name},
        )
        assert r.status_code == 201, r.text
        self.client = client
        self.tokens = r.json()
        self.headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
        self.me = client.get("/auth/me", headers=self.headers).json()
        self.org_id = self.me["org_id"]
        self.email = email
        self.password = password

    def upload(self, filename: str, content: bytes, content_type: str = "text/plain"):
        return self.client.post(
            "/documents/upload", headers=self.headers, files={"file": (filename, content, content_type)}
        )

    def invite_member(self, email: str, role: str = "member", password: str = "Passw0rd123") -> dict:
        r = self.client.post("/organizations/me/invitations", headers=self.headers, json={"email": email, "role": role})
        assert r.status_code == 201, r.text
        token = r.json()["invite_url"].split("token=")[1]
        r = self.client.post(
            "/auth/accept-invite", json={"token": token, "password": password, "full_name": email.split("@")[0]}
        )
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def ask(self, question: str, headers: dict | None = None) -> dict:
        return ask(self.client, headers or self.headers, question)


def ask(client: TestClient, headers: dict, question: str) -> dict:
    """POST /chat/ask and parse the SSE stream into a summary dict."""
    with client.stream("POST", "/chat/ask", headers=headers, json={"question": question}) as r:
        status, ctype = r.status_code, r.headers.get("content-type", "")
        body = r.read().decode()
    result = {"status": status, "content_type": ctype, "events": [], "answer": "", "sources": None, "raw": body}
    if status != 200:
        result["json"] = json.loads(body)
        return result
    for block in body.split("\n\n"):
        if block.startswith("data: "):
            event = json.loads(block[len("data: "):])
            result["events"].append(event)
            if event["type"] == "token":
                result["answer"] += event["content"]
            elif event["type"] == "sources":
                result["sources"] = event["sources"]
            elif event["type"] in ("done", "meta", "error"):
                result[event["type"]] = event
    result["answer"] = result["answer"].strip()
    return result


HR_POLICY = (
    "Acme Corp Leave Policy.\n\n"
    "Every full-time employee receives 24 days of paid annual leave per calendar year. "
    "Unused annual leave days can be carried over to the next year, up to a maximum of 10 days.\n\n"
    "Sick leave: employees are entitled to 12 days of paid sick leave annually. "
    "A medical certificate is required for sick leave longer than 3 consecutive days.\n\n"
    "Remote work: employees may work from home up to 2 days per week with manager approval."
).encode()

PRODUCT_MANUAL = (
    "Globex Rocket Engine Manual.\n\n"
    "The rocket engine requires liquid oxygen fuel and must be inspected every 500 flight hours. "
    "The maximum thrust of the Globex engine is 900 kilonewtons."
).encode()


@pytest.fixture
def org_a(client):
    return Org(client, "Acme Corp", "admin@acme.com")


@pytest.fixture
def org_b(client):
    return Org(client, "Globex Inc", "admin@globex.com")
