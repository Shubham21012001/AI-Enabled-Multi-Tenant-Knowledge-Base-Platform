# Final Demo Script (about 10 minutes)

Sample documents are in [`demo/sample-documents/`](../demo/sample-documents/): two for **Acme Corp** and one for **Globex Inc**. The Globex manual deliberately also mentions *annual leave* (18 days, versus Acme's 24) to show that one company's answers never use another company's documents.

## Before the demo

```powershell
cd knowbot
docker compose up -d
cd backend; .\venv\Scripts\Activate.ps1; uvicorn app.main:app      # terminal 1
cd frontend; npm run dev                                            # terminal 2
```

Make sure `backend/.env` has `AI_PROVIDER=openai` and a valid `OPENAI_API_KEY` **with billing credit**, then run `python scripts\verify_real_rag.py` the day before. Every check should pass.
Use a normal browser window for Acme and a **private/incognito** window for Globex.

## Script

| # | Show | Say |
|---|---|---|
| 1 | Register **Acme Corp** (admin) | Signup creates a new tenant; the user becomes its admin. There is no way to pick an `org_id` or role. |
| 2 | Documents → drag in both Acme files | Upload returns instantly. Status goes *Processing → Ready* while extraction, chunking (1000/200) and embeddings run in the background. |
| 3 | Chat: *"How many days of annual leave can I carry over?"* | Answer streams token by token with a citation chip. Click it to show the source snippet. |
| 4 | Chat: *"What is the policy on lost laptops?"* | Retrieval picks the IT policy, not the HR handbook. |
| 5 | Ask question 3 again | **Instant answer** badge: Redis semantic cache (org-scoped, 24h). |
| 6 | Chat: *"What is the CEO's salary?"* | *"I couldn't find this information…"* No hallucination. |
| 7 | Incognito: register **Globex Inc**, upload the rocket manual | A second, completely separate tenant. |
| 8 | Globex asks *"How many days of annual leave do we get?"* | Answers **18 days** from its own manual and never sees Acme's 24. Then ask *"What is the policy on lost laptops?"* → not found. **Tenant isolation.** |
| 9 | Acme: Settings → Members → invite a member, open the link in another browser, accept | Invitation tokens are single-use and hashed. Members can chat but can't upload or see the dashboard. |
| 10 | Acme: thumbs-down one answer, then open the Dashboard | Usage meters, daily chart, most-asked questions, most-cited documents, **knowledge gaps** (the CEO-salary question and the thumbs-down appear). |
| 11 | Settings → API Keys → create, then run the curl example in a terminal | The key is shown once, stored as a hash, and revocable. |
| 12 | Settings → Plan | Free-plan limits; warning at 80%, blocked at 100%, enforced on the backend. |
| 13 | Terminal: `pytest` | 90 automated tests against real Postgres/pgvector/Redis, including cross-tenant attack tests. |
| 14 | Resize the browser to phone width | Responsive layout, drawer navigation, 44px touch targets. |

## Likely viva questions

- **Why chunk overlap?** So facts split across a boundary still appear whole in one chunk.
- **Why pgvector and not a separate vector DB?** One database, transactional consistency with the documents table, and SQL `WHERE org_id = …` filtering for isolation.
- **HNSW vs IVFFlat?** See [ARCHITECTURE.md §3](ARCHITECTURE.md#3-key-decisions).
- **How do you stop hallucinations?** A relevance threshold, so with no relevant chunks the LLM is never called; a strict prompt with an exact not-found sentence; temperature 0; and citations shown to users.
- **What if two orgs ask the same question?** The cache keys include `org_id`, so each org has its own cache. `test_semantic_cache_is_org_scoped` proves it.
- **Why not Celery?** Not needed at this scale; BackgroundTasks plus resume-on-restart keeps the architecture simple.
