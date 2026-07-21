# Configuration

Every environment variable **AI DeepResearch AutoFlow** reads, what it does, its
default, and whether it's required.

- **Backend** config is environment variables read from **`backend/.env`** (copy
  `backend/.env.example`). Most use the **`AUTOFLOW_`** prefix; a few conventional
  names are **un-prefixed** (`APP_ENV`, `GOOGLE_*`, and the provider API keys).
- **Frontend** config uses the **`NEXT_PUBLIC_`** prefix, read from
  `frontend/.env.local`.

The whole stack runs offline on **mock providers with no keys set**, so nothing
below is required for local development. See **[`INSTALL.md`](./INSTALL.md)** to
get running and **[`ARCHITECTURE.md`](./ARCHITECTURE.md)** for how config flows
into a run. The `Required?` column: **No** = optional everywhere, **Prod** =
required when `APP_ENV=production`.

---

## Core application

| Var | What it does | Default | Required? |
|---|---|---|---|
| `APP_ENV` | Run mode: `development` or `production`. In `production` the secret vars below fail-fast if missing; in `development` they're generated ephemerally. *(un-prefixed)* | `development` | No |
| `AUTOFLOW_DB_PATH` | Path to the SQLite database file (parent dir auto-created). | `./data/autoflow.db` | No |
| `AUTOFLOW_CORS_ORIGINS` | Comma-separated browser origins allowed by CORS. Must include your frontend origin. | `http://localhost:3000` | No |
| `AUTOFLOW_DEFAULT_LANGUAGE` | Fallback report language for a new run that doesn't specify one (`en` / `th`). | `en` | No |
| `AUTOFLOW_DEFAULT_REQUIRE_PLAN_APPROVAL` | Default human-in-the-loop plan approval for new runs. | `true` | No |
| `AUTOFLOW_RATE_LIMIT_ENABLED` | In-process rate limiting on auth endpoints (disable in tests). | `true` | No |

---

## Security & secrets

| Var | What it does | Default | Required? |
|---|---|---|---|
| `AUTOFLOW_MASTER_KEY` | KEK for the AES-256-GCM credential vault. **Base64, 32 bytes.** | _(none)_ | **Prod** |
| `AUTOFLOW_JWT_SECRET` | HS256 signing secret for access tokens. **≥32 chars.** | _(none)_ | **Prod** |

In production the app **fails fast at startup** if either is missing or malformed.
In development a missing value yields a loud, **ephemeral** key (vault data /
sessions won't survive a restart), so you can boot without ceremony.

Generate them (from `backend/`):

```bash
# AUTOFLOW_MASTER_KEY — base64, 32 bytes
uv run autoflow gen-key

# AUTOFLOW_JWT_SECRET — ≥32 chars
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste each into `backend/.env`. See [`SECURITY.md`](./SECURITY.md) for the vault
design and master-key rotation (after rotating in-app, update
`AUTOFLOW_MASTER_KEY` to the new key — env is the source of truth on restart).

---

## Google OAuth (optional)

"Continue with Google" is enabled only when all three `GOOGLE_*` vars are set;
otherwise `/api/v1/auth/google/*` returns `503`. OAuth never creates a
`superadmin` — new Google users join as `member`.

| Var | What it does | Default | Required? |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Web-application client id (Google Cloud Console). *(un-prefixed)* | _(none)_ | No |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 client secret. *(un-prefixed)* | _(none)_ | No |
| `GOOGLE_REDIRECT_URI` | Must match the URI registered in Google Cloud Console, e.g. `http://localhost:8000/api/v1/auth/google/callback`. *(un-prefixed)* | _(none)_ | No |
| `AUTOFLOW_FRONTEND_URL` | Where the OAuth callback returns the browser after a successful login. | `http://localhost:3000` | No |

---

## Provider API keys

Provider keys are **resolved at call time**, so you only need the ones you
actually use, and mock providers need none. Each key is un-prefixed (conventional
provider name). You can also add keys **in-app** via **Admin → Credentials**
(stored encrypted in the vault); the vault is checked first, the env var is the
fallback (see [`SECURITY.md`](./SECURITY.md#resolution-order)).

### LLM (via LiteLLM)

| Var | What it does | Default | Required? |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude models. | _(none)_ | No |
| `OPENAI_API_KEY` | OpenAI models. | _(none)_ | No |
| `GEMINI_API_KEY` | Google Gemini models. | _(none)_ | No |
| `ZAI_API_KEY` | z.ai GLM (LiteLLM `zai/` prefix, e.g. `zai/glm-4.6`). | _(none)_ | No |
| `MOONSHOT_API_KEY` | Moonshot Kimi (LiteLLM `moonshot/` prefix). | _(none)_ | No |
| `MOONSHOT_API_BASE` | Optional override for the Moonshot API base URL. | LiteLLM default | No |

### Search

| Var | What it does | Default | Required? |
|---|---|---|---|
| `TAVILY_API_KEY` | Tavily search. | _(none)_ | No |
| `SERPER_API_KEY` | Serper search. | _(none)_ | No |
| `EXA_API_KEY` | Exa search. | _(none)_ | No |

> **DuckDuckGo** search is keyless — no variable required.

### Crawl

| Var | What it does | Default | Required? |
|---|---|---|---|
| `JINA_API_KEY` | Optional key for the Jina reader crawl provider (`r.jina.ai`). | _(none)_ | No |

> `mock` and `trafilatura` crawl providers need no key; `trafilatura` is listed as
> available only when its optional package is installed.

---

## Provider selection & run defaults

Over HTTP, the **active** provider/model is chosen in **Settings** (persisted to
the DB `settings` table via `GET`/`POST /api/v1/config`), with optional per-run
overrides in `POST /api/v1/runs`. The `AUTOFLOW_*` selectors below set the
**`RunConfig` defaults** used by the **`autoflow` CLI** and the engine when a value
isn't otherwise specified.

| Var | What it does | Default | Required? |
|---|---|---|---|
| `AUTOFLOW_LLM_PROVIDER` | Default LLM provider (`mock`, `anthropic`, `openai`, `gemini`, `litellm`). | `mock` | No |
| `AUTOFLOW_LLM_MODEL` | Default LLM model string. | `mock-1` | No |
| `AUTOFLOW_SEARCH_PROVIDER` | Default search provider (`mock`, `tavily`, `serper`, `exa`, `duckduckgo`). | `mock` | No |
| `AUTOFLOW_CRAWL_PROVIDER` | Default crawl provider (`mock`, `jina`, `trafilatura`). | `mock` | No |
| `AUTOFLOW_LANGUAGE` | Default report language for the CLI/engine (`en` / `th`). | `en` | No |
| `AUTOFLOW_TEMPLATE` | Default research template id. | `deep_research` | No |
| `AUTOFLOW_REQUIRE_PLAN_APPROVAL` | Default HITL plan approval for the CLI/engine. | `false` | No |

**Templates** (`GET /api/v1/templates`): `deep_research` (narrative), plus the
entity-mode `competitor_brand`, `market_landscape`, `swot`, and `pricing_analysis`
(which render cited comparison tables).

### `verification_level`

Selected in **Settings** (persisted; not an env var). Controls how the research
loop treats findings:

| Value | Meaning |
|---|---|
| `off` | Legacy path: `search → summarize → cited note`. No claim/verification/contradiction events. |
| `light` **(default)** | Engine v2: extract claims, verify each against its source, detect contradictions, and build the report from verified claims only. Tuned for lower cost/latency. |
| `strict` | Same verified-claim pipeline as `light`, as the strictest posture. |

The **verifier** runs on a separately-configurable model (`RunConfig`'s
`verifier_provider` / `verifier_model`), defaulting to the main LLM — run it on a
cheap/fast model (e.g. Haiku / GLM / Kimi) to cut verification cost.

---

## Demo mode

Hardening for a public sandbox: force mock providers and refuse credential entry
so nobody can run up cost or paste a real key. Used by the hosted demo (see
[`DEMO.md`](./DEMO.md)); leave unset for a normal install.

| Var | What it does | Default | Required? |
|---|---|---|---|
| `AUTOFLOW_DEMO_MODE` | Force mock providers and disable credential entry / provider switching. | `false` | No |
| `AUTOFLOW_DEMO_ADMIN_EMAIL` | Seed this superadmin on startup when the DB has zero users (ephemeral-DB demos). Both email + password must be set to seed. | _(none)_ | No |
| `AUTOFLOW_DEMO_ADMIN_PASSWORD` | Password for the seeded demo superadmin. | _(none)_ | No |
| `AUTOFLOW_DEMO_PUBLIC_ADMIN_EMAIL` | A published admin-role account whose credentials are shown to visitors so they can explore the admin panel. | _(none)_ | No |
| `AUTOFLOW_DEMO_PUBLIC_ADMIN_PASSWORD` | Password for the published demo admin account. | _(none)_ | No |
| `AUTOFLOW_DEMO_RESET_TOKEN` | Shared secret for the demo-only `/demo/reset` endpoint (a scheduled job wipes the ephemeral DB). Unset ⇒ reset is refused. | _(none)_ | No |

---

## Frontend

| Var | What it does | Default | Required? |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | Base URL of the backend (FastAPI). Read by the browser. Must point at your backend origin. | `http://localhost:8000` | No |

---

## Production checklist

When `APP_ENV=production`:

- **Required (fail-fast):** `AUTOFLOW_MASTER_KEY`, `AUTOFLOW_JWT_SECRET` — generate
  with the commands [above](#security--secrets).
- **Set for your deployment:** `AUTOFLOW_CORS_ORIGINS` (real frontend origin),
  `NEXT_PUBLIC_API_BASE` (real backend origin), and provider keys for whatever
  LLM/search providers you enable.
- **Optional:** Google OAuth (`GOOGLE_*` + `AUTOFLOW_FRONTEND_URL`).
