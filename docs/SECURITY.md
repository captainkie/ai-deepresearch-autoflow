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

## Roadmap (later M3 slices)

- **M3b** — Argon2id passwords, JWT access + rotating refresh cookies, RBAC
  (`superadmin/admin/member/viewer`), Strapi-style first-run superadmin setup;
  the admin credential/audit routes above become **admin-only**.
- **M3c** — Google OAuth (Authorization Code + PKCE), link by verified email.

## Reporting a vulnerability

Please open a private report to the maintainer (see the repository's security
contact / `SECURITY` advisories) rather than a public issue. We aim to
acknowledge within a few days.
