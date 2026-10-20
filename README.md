# KnowBot

**An AI-powered, multi-tenant knowledge base SaaS.** Companies upload their internal documents (HR policies, SOPs, manuals). Employees ask questions in plain English. KnowBot finds the relevant passages with vector search and streams back an answer grounded **only** in those documents, with citations.

> Think: a private ChatGPT for a company's internal knowledge, where every answer shows its sources and one company can never see another's data.

---

## Features

| Area | What it does |
|---|---|
| **RAG pipeline** | PDF/DOCX/TXT → extract → clean → chunk (1000 chars, 200 overlap) → `gemini-embedding-001` → PostgreSQL + pgvector |
| **Grounded answers** | Top-5 cosine search scoped to the user's org → `gemini-3.8-flash` with a strict "answer only from context" prompt → streamed over SSE with numbered citations |
| **Reliable "not found"** | If no chunk is relevant enough, KnowBot answers *"I couldn't find this information in your company's documents."* **without calling the LLM** |
| **Multi-tenancy** | Every tenant row has `org_id`; it always comes from the authenticated user/API key, never from the client. Covered by cross-tenant tests |
| **Background processing** | Upload returns `202` immediately; processing runs in the background with 3 attempts and backoff, and resumes after restarts |
| **Semantic cache** | Redis, per organization, cosine > 0.92, 24h TTL, invalidated when documents change |
| **Auth** | bcrypt passwords, 15-min JWT access tokens, rotating 30-day refresh tokens with reuse detection, logout, password reset, invitations |
| **Roles** | Super admin (platform), org admin, member — enforced on the backend |
| **Plans** | Free / Pro / Enterprise limits on members, documents and monthly questions; warn at 80%, block at 100% |
| **Analytics** | Usage, daily questions, most-asked questions, most-cited documents, knowledge gaps (unanswered or thumbs-down) |
| **API keys** | Hashed at rest, shown once, revocable, usage-tracked; call `/chat/ask` with `X-API-Key` |
| **Protection** | Redis rate limits on login, refresh, register, upload, chat, API keys and password reset |
| **Notifications** | In-app + pluggable email (console/SMTP): document ready/failed, invitations, usage warnings |

## Tech stack

**Backend:** Python 3.12 · FastAPI 0.111 · SQLAlchemy 2.0 · Alembic · Pydantic 2.8 · PostgreSQL 16 + pgvector · Redis 7 · Google Gemini · pypdf · python-docx · passlib/bcrypt · python-jose
**Frontend:** React 18 · Vite · Tailwind CSS 3 · React Router 6 · React Query · Zustand · Axios · Framer Motion · Lucide · React Hot Toast
**Infrastructure:** Docker Compose · Caddy (automatic HTTPS) · nginx · AWS EC2 · AWS S3

---

## Architecture

                 ┌──────────────────────────── EC2 (docker compose) ───────────────────────────┐
 Browser ──HTTPS─▶ Caddy :443 ──▶ nginx (React build, /api proxy) ──▶ FastAPI (2 workers)        │
                 │   auto TLS        SSE unbuffered                     │      │       │          │
                 │                                                      ▼      ▼       ▼          │
                 │                                   PostgreSQL+pgvector   Redis    Gemini API    │
                 └──────────────────────────────────────────────────────────────────── │ ─────────┘
                                                                                    AWS S3 (files)



Backend layout (modular monolith — routes are thin, logic lives in services):

backend/app/
├── main.py app, middleware, error handlers
├── core/ config, database, security (JWT/bcrypt), deps (auth + tenant context), redis
├── models/ SQLAlchemy models
├── schemas/ Pydantic request/response models
├── routes/ HTTP layer only
├── services/ business logic: auth, orgs, documents, processing, chat, cache, plans, dashboard…
├── repositories/ vector search (tenant filter is a required argument)
└── utils/ upload validation




---

## Quick start (local development, Windows PowerShell)

Prerequisites: Docker Desktop, Python 3.12, Node.js 20+.

```powershell
# 1. Infrastructure: PostgreSQL+pgvector and Redis
cd knowbot
Copy-Item .env.example .env
docker compose up -d

# 2. Backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # then edit: JWT_SECRET_KEY, GEMINI_API_KEY
alembic upgrade head
uvicorn app.main:app --reload       # http://localhost:8000/docs

# 3. Frontend (new terminal)
cd knowbot\frontend
npm install
npm run dev                         # http://localhost:5173
```

No Gemini key yet? Set `AI_PROVIDER=fake` in `backend/.env`. That provider uses deterministic offline embeddings and extractive answers, so the whole app is usable for UI work (answers are **not** LLM-generated). Production refuses to start with it.

---

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `ENVIRONMENT` | `development` / `test` / `production` | `development` |
| `DATABASE_URL` | SQLAlchemy URL | local compose DB |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | HMAC secret for JWTs (32+ chars required in production) | — |
| `AI_PROVIDER` | `gemini` or `fake` | `gemini` |
| `GEMINI_API_KEY` | Google Gemini API key (free at aistudio.google.com) | — |
| `EMBEDDING_MODEL` | Gemini embedding model | `models/gemini-embedding-001` |
| `CHAT_MODEL` | Gemini chat model | `models/gemini-3.8-flash` |
| `STORAGE_BACKEND` | `local` or `s3` | `local` |
| `S3_BUCKET`, `AWS_REGION` | Document storage in production | — |
| `EMAIL_PROVIDER` | `console` or `smtp` (+ `SMTP_*`) | `console` |
| `SMTP_HOST` | SMTP server (e.g. `smtp.gmail.com`) | — |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username / Gmail address | — |
| `SMTP_PASSWORD` | SMTP password / Gmail App Password | — |
| `CORS_ORIGINS`, `FRONTEND_URL` | Browser origin / links in emails | `http://localhost:5173` |
| `RATE_LIMIT_*` | `"<requests>/<seconds>"` per endpoint group | see `app/core/config.py` |

All settings live in [backend/app/core/config.py](backend/app/core/config.py).

---

## API overview

Interactive docs: `http://localhost:8000/docs` (disabled in production).

| Method & path | Who | Purpose |
|---|---|---|
| `POST /auth/register` | public | Create an organization + its admin |
| `POST /auth/login` · `/auth/refresh` · `/auth/logout` | public | Sessions (refresh tokens rotate) |
| `GET/PATCH /auth/me`, `POST /auth/change-password` | user | Profile |
| `POST /auth/forgot-password` · `/auth/reset-password` | public | Password reset by email |
| `GET /auth/invitations/{token}` · `POST /auth/accept-invite` | public | Join an organization |
| `GET/PATCH /organizations/me`, `GET /organizations/me/usage`, `PUT /organizations/me/plan` | member / admin | Organization & plan |
| `GET/PATCH/DELETE /organizations/me/members[/{id}]` | admin (list: member) | Members & roles |
| `POST/GET/DELETE /organizations/me/invitations[/{id}]` | admin | Invitations |
| `POST /documents/upload` · `GET /documents/` · `GET/DELETE /documents/{id}` · `POST /documents/{id}/reprocess` | admin (read: member) | Documents |
| `POST /chat/ask` | member or API key | **Streaming** answer (`text/event-stream`) |
| `GET /conversations` · `GET/DELETE /conversations/{id}` · `PUT /conversations/{id}/feedback` | owner only | History & feedback |
| `GET /dashboard?days=30` | admin | Analytics |
| `POST/GET/DELETE /api-keys[/{id}]` | admin | API keys |
| `GET /notifications` · `POST /notifications/{id}/read` · `/notifications/read-all` | user | Notifications |
| `GET /admin/organizations` · `PUT /admin/organizations/{id}/plan` | super admin | Platform admin |
| `GET /health` | public | DB + Redis health |

**SSE event format** for `/chat/ask`:

{“type”:”meta”,”cached”:false}
{“type”:”token”,”content”:”Employees “}
{“type”:”sources”,”sources”:[{“document_id”:”…”,”document_name”:”policy.pdf”,”chunk_index”:3,”snippet”:”…”}]}
{“type”:”done”,”conversation_id”:”…”,”usage”:{“used”:12,”limit”:100,”warning”:false,”remaining”:88}}
{“type”:”error”,”message”:”…”}


---

## Deployment

Production runs as a single `docker compose` stack on an EC2 instance: Caddy terminates TLS with automatic Let's Encrypt certificates, nginx serves the React build and proxies `/api`, the API runs migrations on start, and documents go to S3. Step-by-step guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## More documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): RAG pipeline and design decisions
- [docs/SECURITY.md](docs/SECURITY.md): security & tenant-isolation audit
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): AWS EC2 + S3 + HTTPS
- [docs/DEMO.md](docs/DEMO.md): final-presentation demo script


