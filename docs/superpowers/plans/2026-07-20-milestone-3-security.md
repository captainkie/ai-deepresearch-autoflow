# Milestone 3 — Security: Vault + Auth + RBAC + First-run Setup + OAuth + Audit

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development. Steps use
> checkbox (`- [ ]`). Security code is high-stakes — write the failing test first, every time.
> Implements design spec §6, §6a, §7, §8 (auth/admin groups).

**Goal:** turn the open M2 API into a secure, multi-user platform. API keys move from env into an
encrypted **vault**; every sensitive action is gated by **auth + RBAC**; a fresh install onboards
its first **superadmin** via a Strapi-style first-run flow; **Google OAuth** is an additional
sign-in; credential actions are **audited**. The engine/provider layers do not change — only the
single seam `services/provider_keys.get_key(provider)` is re-backed by the vault.

**Non-goals (M3):** org/workspaces, per-run sharing ACLs beyond role checks, password reset email,
2FA. (Tracked for later.)

## Slices (each a branch → PR → merge; independently useful)

- **M3a — Vault** (crypto + `provider_credentials` + repo + admin credential API + audit for cred
  ops; swap `get_key` env→vault with env fallback). *No auth yet — endpoints open, wrapped by M3b.*
- **M3b — Auth + RBAC + First-run setup** (Argon2id, JWT access + rotating refresh cookies, RBAC
  deps, `/setup`, `/auth/*`, guard all admin/cred/run routes).
- **M3c — Google OAuth** (Authorization Code + PKCE; link by verified email).

Rationale: the vault is self-contained and the security centerpiece; auth builds the identity model
setup/RBAC need; OAuth is additive. Shipping in this order keeps each PR reviewable.

## New dependencies (`pyproject.toml`)

```
cryptography>=43       # AES-256-GCM (hazmat AESGCM) + constant-time compare
argon2-cffi>=23        # Argon2id password hashing
pyjwt>=2.9             # JWT access tokens (HS256)
# OAuth: reuse existing httpx for Google token exchange (no authlib) + `secrets` for PKCE/state
```

## Data model additions (`app/db/schema.sql` — additive; migration runner already execs on startup)

```sql
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  password_hash TEXT, google_sub TEXT UNIQUE, role TEXT NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL, revoked_at TEXT, user_agent TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_credentials (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, label TEXT NOT NULL,
  ciphertext BLOB NOT NULL, nonce BLOB NOT NULL, key_version INTEGER NOT NULL,
  masked_hint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  created_by TEXT, created_at TEXT NOT NULL, expires_at TEXT, last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL,
  target_type TEXT, target_id TEXT, meta_json TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cred_provider ON provider_credentials(provider, status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
```

`runs.owner_id` already unused by M2? If absent, add `owner_id TEXT` to `runs` (nullable; set on
create once auth exists). Keep backward-compatible.

---

## M3a — Vault

**Files:** `app/security/__init__.py`, `app/security/crypto.py` (AESGCM vault), `app/security/keys.py`
(master-key resolution), `app/db/repositories.py` (+`CredentialRepo`, `AuditRepo`),
`app/services/vault_service.py`, `app/api/admin.py` (credential routes), `app/services/provider_keys.py`
(vault-backed with env fallback). `app/settings.py` (+`master_key`, `app_env`).

### Task 1 — Master key + settings
- [ ] `security/keys.py`: `load_master_key() -> bytes` reads `AUTOFLOW_MASTER_KEY` (base64, 32 bytes).
  `APP_ENV=production` → **fail-fast** if missing/invalid. Dev → generate ephemeral key + `logger.warning`
  loud banner. `generate_master_key() -> str` (base64) helper for docs/CLI.
- [ ] Add `app_env: str = "development"` and `master_key: str | None = None` to `AppSettings`
  (env `APP_ENV`, `AUTOFLOW_MASTER_KEY`). **Test:** prod+missing raises; dev+missing warns+returns 32 bytes;
  valid base64 decodes to 32 bytes; wrong length raises.

### Task 2 — AES-256-GCM vault (crypto core) — TESTS FIRST
- [ ] **Failing tests** `tests/test_crypto.py`: `encrypt(plaintext) -> (ciphertext, nonce, key_version)`
  then `decrypt(...) == plaintext`; nonce is 96-bit and **unique** across calls; tampering ciphertext/nonce
  raises (GCM auth); `masked_hint("sk-abcd...wxyz")` shows only a safe prefix/suffix; **plaintext never
  appears** in `repr`/log of the vault object.
- [ ] Implement `crypto.py` `Vault(key: bytes, key_version: int)` using `AESGCM`; random 12-byte nonce
  per secret; `rotate(new_key)` re-encrypts. Tests → PASS. Commit `feat(security): AES-256-GCM vault`.

### Task 3 — Credential + Audit repositories
- [ ] **Failing tests** `tests/test_db.py`: `CredentialRepo.create/get/list/set_status/set_last_used/
  update_ciphertext`; `AuditRepo.append/list` (newest first). Ciphertext stored/retrieved as BLOB.
- [ ] Implement in `repositories.py` (async, parameterized, timestamps passed in). PASS.
  Commit `feat(db): credential + audit repositories`.

### Task 4 — Vault service (encrypt-on-write, decrypt-at-use, never return plaintext)
- [ ] **Failing tests** `tests/test_vault_service.py`: `add_credential(provider,label,plaintext,actor)`
  → returns metadata with `masked_hint` **only** (never plaintext); `resolve(provider) -> str|None`
  decrypts newest **active, non-expired** cred + records `last_used_at` + audit `credential.use`;
  `revoke`/`expire` make `resolve` skip it; `rotate_master_key(new)` re-encrypts all + bumps
  `key_version`; every mutation writes an `audit_log` row; **a serialized credential dict never
  contains the plaintext or raw key bytes**.
- [ ] Implement `vault_service.py`. PASS. Commit `feat(security): vault service + audit`.

### Task 5 — Admin credential API (open for now; M3b wraps with RBAC)
- [ ] Routes in `app/api/admin.py`: `GET/POST/DELETE /api/admin/credentials`, `POST .../{id}/revoke`,
  `POST .../rotate` (master key), `GET /api/admin/audit`. POST accepts plaintext; **all reads return
  `masked_hint` + metadata only**.
- [ ] **Failing tests** `tests/test_api_credentials.py`: create → list shows masked only, never plaintext;
  revoke → status flips; audit lists the actions; **assert the plaintext string is absent from every
  response body** (the M3 headline test).
- [ ] Commit `feat(api): admin credential + audit endpoints`.

### Task 6 — Swap `provider_keys.get_key` env→vault (fallback to env)
- [ ] `get_key(provider)` first tries `vault_service.resolve(provider)`, else env (back-compat/dev).
  Wire the vault service through `deps.py`/app state. **Test:** with a vaulted cred, `get_key` returns
  decrypted value + records use; with none, falls back to env; mock providers still need no key
  (offline E2E stays green).
- [ ] Commit `feat(security): resolve provider keys from vault (env fallback)`.

### Task 7 — Gates + docs
- [ ] `ruff` + `pytest` green; update `.env.example` (`AUTOFLOW_MASTER_KEY`, `APP_ENV`), `docs/SECURITY.md`
  (vault design, threat model, rotation), `docs/API_CONTRACT.md` (admin/credential shapes). PR M3a.

---

## M3b — Auth + RBAC + First-run Setup

**Files:** `app/security/passwords.py` (Argon2id), `app/security/jwt.py`, `app/security/rbac.py`
(FastAPI deps), `app/db/repositories.py` (+`UserRepo`, `RefreshTokenRepo`), `app/services/auth_service.py`,
`app/api/auth.py`, `app/api/setup.py`, `app/api/admin.py` (+user mgmt). Cookies: httpOnly, Secure,
SameSite=Lax.

### Task 1 — Passwords (Argon2id) — TESTS FIRST
- [ ] **Failing tests** `tests/test_passwords.py`: `hash_password` → verify true for right pw, false for
  wrong; hash != plaintext; `needs_rehash` supported. Implement with `argon2-cffi`. Commit.

### Task 2 — JWT access + refresh tokens
- [ ] **Failing tests** `tests/test_jwt.py`: `make_access(sub, role, ttl)` / `decode` round-trip;
  expired token rejected; tampered rejected; wrong secret rejected. Refresh tokens are **random opaque**
  strings stored **hashed** (sha256) in `refresh_tokens`, rotated on use, revocable. Implement
  `jwt.py` (HS256, secret from settings `AUTOFLOW_JWT_SECRET`, ~15 min access TTL). Commit.

### Task 3 — User + RefreshToken repos + auth service
- [ ] **Failing tests**: `UserRepo.create/get_by_email/get_by_google_sub/list/set_role/set_disabled`
  (email UNIQUE); `RefreshTokenRepo.create/get_by_hash/revoke/revoke_all_for_user`.
- [ ] `auth_service.py`: `register/login` (password), `issue_tokens`, `rotate_refresh`, `logout`
  (revoke), `current_user_from_access`. Tests. Commit.

### Task 4 — First-run setup (Strapi-style, replay-guarded)
- [ ] **Failing tests** `tests/test_api_setup.py`: `GET /api/setup/status` → `{needs_setup:true}` when 0
  users; `POST /api/setup` creates role `superadmin`, sets `settings.setup_completed=true`, returns tokens;
  a **second** `POST /api/setup` → **409** (cannot re-seize); after setup `status.needs_setup=false`.
- [ ] `app/api/setup.py`. Commit `feat(api): first-run superadmin setup`.

### Task 5 — Auth routes + RBAC deps
- [ ] `app/api/auth.py`: `POST /register /login /logout /refresh`, `GET /me`. Set/clear refresh cookie.
- [ ] `security/rbac.py`: `require_user`, `require_role("admin")`, `require_superadmin`, ownership check
  for runs. Roles `superadmin|admin|member|viewer` (spec §6).
- [ ] **Failing tests** `tests/test_api_auth.py` + `tests/test_rbac.py`: login flow issues cookies;
  `/me` needs a valid access token; refresh rotates + old refresh is revoked; **RBAC matrix** — viewer
  can't create runs, member can't hit admin, admin can manage creds/users, superadmin can rotate master
  key / manage admins; disabled user is rejected. Commit.

### Task 6 — Gate existing routes + `runs.owner_id`
- [ ] Apply RBAC to `runs` (owner or admin), `admin/*` (admin+), master-key rotate + admin mgmt
  (superadmin). Set `runs.owner_id` on create. Update `RunService`/routes.
- [ ] **Failing tests**: unauthenticated run creation 401; non-owner member can't read another's run;
  admin can. Regression: existing M2 run tests updated to authenticate first. Commit.

### Task 7 — Setup-mode + frontend contract + gates
- [ ] `GET /api/setup/status` drives frontend routing (M4). Update `docs/API_CONTRACT.md` (auth/setup/admin
  shapes, cookie semantics), `docs/SECURITY.md` (sessions, RBAC), `.env.example`
  (`AUTOFLOW_JWT_SECRET`). `ruff`+`pytest` green. PR M3b.

---

## M3c — Google OAuth (Authorization Code + PKCE)

**Files:** `app/api/auth.py` (+google routes), `app/services/oauth_service.py`, settings
(`GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`).

### Task 1 — OAuth service (PKCE, state) — TESTS FIRST (mock Google)
- [ ] **Failing tests** `tests/test_oauth.py` (mock the token/userinfo HTTP via httpx transport):
  `start()` returns an auth URL with `code_challenge` (S256) + signed `state`; `callback(code,state)`
  validates state, exchanges code, fetches userinfo, requires `email_verified`. Bad/replayed state → 400.
- [ ] Implement `oauth_service.py` using `httpx` + `secrets`/`hashlib` for PKCE. Commit.

### Task 2 — Link/create user by verified email + routes
- [ ] `GET /api/auth/google/start` (sets state cookie) + `GET /api/auth/google/callback` (links to a user
  by verified email, or creates a `member`; sets `google_sub`; issues tokens). **Never** creates a
  superadmin via OAuth.
- [ ] **Failing tests** `tests/test_api_google.py`: new verified email → member created + tokens; existing
  email → linked (`google_sub` set), no dup; unverified email → rejected. Commit.

### Task 3 — Gates + docs
- [ ] `ruff`+`pytest` green; `docs/CONFIGURATION.md` (Google OAuth setup), `.env.example`
  (`GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`), `docs/API_CONTRACT.md`. PR M3c.

---

## Cross-cutting test doctrine (the security bar)

- **Plaintext-never-serialized:** dedicated assertions that no API response / logged object / serialized
  dict ever contains a credential plaintext or raw key bytes (spec §6, §13 top risk).
- **Vault round-trip + tamper:** GCM auth failure on any ciphertext/nonce mutation.
- **Setup replay-guard:** second `POST /api/setup` → 409, always ≥1 superadmin.
- **RBAC matrix:** every role × every sensitive action, incl. disabled-user rejection.
- **Refresh rotation:** used refresh token is revoked; reuse rejected.
- **Offline E2E stays green:** mock providers need no keys; vault fallback to env keeps M1/M2 tests passing.
- Secret-scan (**gitleaks**) + `AUTOFLOW_MASTER_KEY`/`AUTOFLOW_JWT_SECRET` fail-fast in prod land in M6 CI,
  but `.env`/`*.db` remain gitignored now.

## Self-Review
- **Spec coverage:** vault (§6), first-run setup (§6a), data model (§7 users/refresh/creds/audit), API
  groups (§8 auth/admin/setup), RBAC roles (§6). OAuth (§6).
- **Seam preserved:** only `provider_keys.get_key` is re-backed; engine/providers untouched → M1/M2 tests
  hold with env fallback.
- **Slice independence:** M3a usable without auth (open, then wrapped); M3b adds identity; M3c additive.
