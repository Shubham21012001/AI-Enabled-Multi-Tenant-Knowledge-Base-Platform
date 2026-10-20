# Security & Tenant-Isolation Audit

This audit was done at the end of the build. Each item lists how it's handled and the test that proves it. All tests live in `backend/tests/` and pass against real PostgreSQL/pgvector and Redis.

## Tenant isolation

| Surface | Control | Verified by |
|---|---|---|
| Source of `org_id` | Taken only from the authenticated principal (`core/deps.py`); request schemas forbid extra fields such as `org_id` / `role` | `test_register_rejects_privilege_fields` |
| Documents (read/delete/reprocess) | Every query filters on `Document.org_id == user.org_id`; another org's document returns **404**, not 403, so its existence isn't revealed | `test_cross_tenant_document_access_blocked` |
| Vector retrieval | `chunk_repository.search_similar(db, org_id, …)`: `org_id` is a required argument, filtered on both chunks and documents | `test_retrieval_is_tenant_isolated`, `test_chunk_repository_never_returns_other_org` |
| Semantic cache | Keys are namespaced `semcache:{org_id}:…` | `test_semantic_cache_is_org_scoped` |
| Conversations & feedback | Filter on `org_id` **and** `user_id`, so members see only their own | `test_conversation_saved_and_private` |
| Members / roles / invitations | Scoped to the admin's org | `test_cross_tenant_member_management_blocked` |
| API keys | Created and revoked within the org; a key authenticates only as its own org | `test_api_key_lifecycle_and_chat` |
| Notifications | Filter on `org_id` + `user_id` | `test_notifications_are_private` |
| Analytics | All dashboard queries filter by org | `test_dashboard_statistics` (another org's activity is checked to be absent) |
| Super admin | Has no org, so tenant endpoints refuse them; platform endpoints are separate | `test_super_admin_platform_endpoints` |

## Authentication & authorization

- **Passwords:** bcrypt via passlib (`bcrypt==4.0.1`). Minimum 8 characters with letters and digits; values over 72 bytes are rejected because bcrypt would silently truncate them. Verified by `test_password_is_hashed_with_bcrypt`.
- **Login:** the same error for an unknown email or a wrong password, and a dummy bcrypt check equalises timing, so attackers can't discover which emails exist.
- **JWT:** HS256 with the algorithm pinned on decode; 15-minute expiry; the user is re-loaded and `is_active` re-checked on every request. Verified by `test_expired_access_token_rejected`, `test_protected_route_requires_valid_token` (forged signature), `test_deactivated_user_blocked`.
- **Refresh tokens:** random 256-bit, stored as SHA-256, 30 days, rotated on every use. Replaying an old token revokes all of that user's sessions. Verified by `test_refresh_rotation_and_reuse_detection`, `test_logout_revokes_refresh_token`.
- **Password reset / invitations:** random tokens stored hashed, single-use and short-lived; reset revokes all sessions. Verified by `test_password_reset_flow`, `test_invitation_token_single_use`.
- **Roles:** enforced by dependencies (`require_admin`, `require_super_admin`). Role changes revoke the member's sessions. The last admin can't be demoted or removed. Verified by `test_member_cannot_perform_admin_actions`, `test_role_change_and_last_admin_protection`.
- **API keys:** `kb_live_` + 256-bit random; only a SHA-256 hash and a display prefix are stored; the raw key is returned once.

## Input & file handling

- **SQL injection:** all queries go through SQLAlchemy with bound parameters; search uses `icontains(..., autoescape=True)`. Verified by `test_sql_injection_in_search_is_inert`.
- **Path traversal:** storage keys are server-generated (`{org_id}/{uuid}.{ext}`). The user's filename is sanitised and used for display only, and `LocalStorage` refuses paths outside its root. Verified by `test_path_traversal_filename_is_neutralised`.
- **File validation:** extension allow-list, magic-byte/content check (PDF header, DOCX zip with `word/document.xml`, text without NUL bytes), and a 10 MB limit enforced at three layers (nginx `client_max_body_size`, `Content-Length` middleware, bounded read). Verified by `test_invalid_extension_rejected`, `test_content_must_match_extension`, `test_oversized_file_rejected`.
- **Validation:** Pydantic schemas with length limits; questions are 1–2000 characters; UUID path parameters are typed.
- **XSS:** React escapes all output; the answer formatter builds elements, never `dangerouslySetInnerHTML`. nginx sends a strict CSP (`script-src 'self'`, `frame-ancestors 'none'`).

## Abuse & cost control

- Redis rate limits apply to login (per IP **and** per email), refresh, register, password reset, invitation lookup, upload, chat (per user / per API key) and API key creation. They fail open if Redis is down, so an outage doesn't lock everyone out. Verified by `test_rate_limit_*`, `test_rate_limiter_fails_open_without_redis`, `test_token_refresh_not_limited_by_login_budget`.
- Monthly question limits are enforced on the backend **before** any OpenAI call (402 at 100%). The semantic cache reduces repeated LLM spend.
- Behind the proxies, nginx trusts only the private Docker network for `X-Forwarded-For`, and Caddy discards client-supplied values, so per-IP limits see the real client and can't be spoofed.

## Secrets & transport

- No secrets in code. Production refuses to start with the default or a short `JWT_SECRET_KEY`, or with the fake AI provider.
- `.env`, `.env.production`, uploads, `venv` and `node_modules` are git-ignored; only `*.example` files are committed.
- HTTPS everywhere via Caddy (automatic Let's Encrypt) with HSTS; HTTP redirects to HTTPS.
- Postgres, Redis and the API aren't published on the host. Redis requires a password in production.
- Containers run as a non-root user (backend).
- **Logging:** request logs record method, path, status and duration only (no query strings). Services log IDs, never passwords, tokens, questions or document text. In production the console email provider logs recipient and subject only, because email bodies contain tokens.

## Known limitations / accepted risks

1. **Refresh token in `localStorage`.** Any XSS could read it. Mitigated by the strict CSP, React escaping, rotation with reuse detection and 15-minute access tokens. Hardening option: move it to an `HttpOnly; Secure; SameSite=Strict` cookie.
2. **Plan changes are a demo.** Admins can switch plans without payment. A real deployment must put a payment provider (e.g. Stripe/Razorpay) in front of `PUT /organizations/me/plan`.
3. **Prompt injection** from document content is reduced by the system prompt but can't be fully eliminated. The impact is limited to the text of an answer within the same organization.
4. **Background jobs are in-process.** If the server crashes mid-processing, jobs are resumed on the next start rather than immediately.
