# Security

AutoFlow is built to be handed to a non-technical team: the operator manages
provider API keys, and members run research without ever seeing raw secrets.
This document covers the **credential vault** (shipped in M3a). Auth, RBAC, and
first-run setup arrive in M3b; Google OAuth in M3c.

## Credential vault (M3a)

Provider API keys are **encrypted at rest** and only ever decrypted inside the
provider layer at call time. No endpoint returns a stored secret.

### Encryption

- **AES-256-GCM** (authenticated encryption) via `cryptography`'s `AESGCM`.
- A fresh random **96-bit nonce** per secret; the ciphertext carries the GCM
  tag, so tampering with either the ciphertext or the nonce fails decryption.
- The key-encryption key (**KEK**) is 32 bytes, provided base64-encoded via
  `AUTOFLOW_MASTER_KEY`. Generate one with:

  ```bash
  autoflow gen-key        # prints a base64, 32-byte key
  ```

- **Production requires a real key** — the app fails fast at startup if
  `APP_ENV=production` and `AUTOFLOW_MASTER_KEY` is missing or malformed.
  In development a missing key yields a **loud, ephemeral** key (encrypted data
  will not survive a restart) so you can boot without ceremony.

### Storage (`provider_credentials`)

Only `ciphertext`, `nonce`, `key_version`, and a **`masked_hint`** (e.g.
`sk-p…wxyz`) plus metadata are stored. Reads (`GET /api/admin/credentials`)
return the masked hint and metadata **only** — never the plaintext.

- **Write-only via API**: create accepts plaintext; it is encrypted immediately.
- **Revoke** (`status=revoked`) and **expire** (`expires_at`) — the vault skips
  non-active / expired credentials when resolving a provider key.
- **Rotation**: `POST /api/admin/credentials/rotate` re-encrypts every credential
  under a new KEK and bumps `key_version`. Decrypt-all happens before any write,
  so a bad secret aborts the rotation before mutating anything. **After rotating,
  update `AUTOFLOW_MASTER_KEY` to the new key** (env is the source of truth on
  restart).

### Resolution order

`get_key(provider)` used by the engine resolves a **vault** credential first,
then falls back to an environment variable (`ANTHROPIC_API_KEY`, …). Mock
providers need no key, so the offline pipeline runs with an empty vault.

## Audit log (`audit_log`)

Every credential action is recorded: `credential.create`, `credential.revoke`,
`credential.use`, `credential.rotate` — with actor (once auth lands), target, a
JSON meta blob, and a timestamp. `GET /api/admin/audit` lists them newest-first.
The audit trail never contains plaintext.

## What is *not* logged

Key material and plaintext secrets are never written to logs or returned in any
response. The `Vault` object's `repr` is `Vault(key=***)`.

## Guardrails

- `.env`, `*.db`, and secrets are gitignored; keep real keys out of version control.
- `APP_ENV=production` fail-fast on a missing master key.
- (M6) CI runs **gitleaks** on every PR.

## Authentication & RBAC (M3b)

- **Passwords**: Argon2id (`argon2-cffi`); a wrong password returns `False`, never raises.
- **Sessions**: a short-lived (~15 min) **JWT access token** (HS256, signed with
  `AUTOFLOW_JWT_SECRET` — ≥32 chars, prod fail-fast / dev ephemeral) is returned in the
  login/register/refresh body and sent back as `Authorization: Bearer`. The **refresh token**
  is a long opaque string stored only as a SHA-256 hash, delivered as an **httpOnly** cookie
  (Secure in production, SameSite=Lax), and **rotated on every use** — a reused (already-rotated)
  refresh token is rejected.
- **First-run setup**: on an empty `users` table the app is in setup mode; `POST /api/setup`
  creates the first **superadmin** and is guarded to run only when zero users exist (409 on replay),
  so it can never be used to seize a running instance.
- **RBAC** (`viewer < member < admin < superadmin`), resolved from the DB row on each request
  (a promotion or disable takes effect immediately, even for a live token):
  - **member+** create/manage their own runs; a non-owner gets 404 (existence hidden).
  - **admin+** manage credentials, audit, provider config, and members/viewers.
  - **superadmin** rotates the master key and manages admins. There is always ≥1 superadmin.
  - A **disabled** user is rejected on every authenticated route.

## Roadmap (next M3 slice)

- **M3c** — Google OAuth (Authorization Code + PKCE), link to a user by verified email;
  OAuth never creates a superadmin.

## Reporting a vulnerability

Please open a private report to the maintainer (see the repository's security
contact / `SECURITY` advisories) rather than a public issue. We aim to
acknowledge within a few days.
