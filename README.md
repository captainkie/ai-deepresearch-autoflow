<h1 align="center">🔎 AI DeepResearch AutoFlow</h1>

<p align="center">
  <b>Deep research your team can trust — self-hosted, secure, every claim cited &amp; verified.</b><br/>
  A multi-user web platform that turns a research goal into a thorough, source-cited report with
  claim-level verification, confidence, and surfaced contradictions —
  built for marketing teams researching competitors and markets.
</p>

<p align="center">
  <a href="https://github.com/captainkie/ai-deepresearch-autoflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/captainkie/ai-deepresearch-autoflow/actions/workflows/ci.yml/badge.svg"></a>
  <a href="./LICENSE"><img alt="License: AGPL v3" src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-16-black">
  <a href="https://github.com/sponsors/captainkie"><img alt="Sponsor" src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-ff69b4"></a>
  <a href="https://buymeacoffee.com/captainkiez"><img alt="Buy Me a Coffee" src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buymeacoffee&logoColor=black"></a>
</p>

---

## What it does

Type a goal like *"Analyze competitor brand X"*, optionally review the AI-generated research
plan, then watch the system search the web, read sources, and synthesize a detailed
**Markdown report with citations** — live, in Thai or English. Every claim is grounded in a
source and checked by a separate verifier, so the report shows **confidence** and **flags
contradictions** rather than asking you to trust a wall of text.

## Highlights

- 🔐 **Secure by default** — API keys live in an encrypted vault (AES-256-GCM), write-only, with
  revoke / expire / rotate and a full audit log. Hand the app to non-technical teammates; the admin
  holds the keys.
- ✅ **Verified, not just generated** — every claim is grounded in a cited source and checked by a
  separate (adversarial) verifier, with a **confidence** badge and **surfaced contradictions**. The
  report body renders only verified claims; the rest goes to an "Unverified" appendix.
- 🧠 **Custom async deep-research engine** — plan → parallel multi-step research loop →
  extract & verify claims → synthesize, with a live event stream (SSE) and adaptive stopping.
- 📊 **Marketing-grade reports** — structured templates (Competitor Teardown, Market Landscape,
  SWOT, Pricing Analysis, Deep Research) render cited, confidence-scored **comparison tables**.
- 🔌 **Swappable providers** — LLM (Claude / OpenAI / Gemini via LiteLLM, + z.ai GLM / Moonshot Kimi)
  and search (Tavily / Serper / Exa / DuckDuckGo). Run the verifier on a cheap/fast model. Mock
  providers run the whole pipeline offline — no keys needed.
- 👥 **Auth + RBAC** — email/password + Google OAuth; `superadmin` / `admin` / `member` / `viewer`
  roles; an admin panel to manage users and provider credentials.
- 🌏 **i18n reports** — choose Thai or English output per job.
- ✅ **Quality gates** — lint, type-check, tests, and secret-scanning in CI.

---

## 🌐 Try the live demo

**[autoflow-research.fosivo.com](https://autoflow-research.fosivo.com)** — a hosted, safe sandbox.

- **Sign in with Google** to explore as a `member` and start a research run right away. (Email
  sign-up is disabled in the demo — Google-only — to keep bots from creating throwaway accounts.)
- Want the admin view? Use the shared **demo admin** login (one click on the sign-in page):
  `demo-admin@autoflow-research.fosivo.com` / `autoflow-demo-admin`. It opens the admin panel —
  users, audit log, and the credentials screen (key entry stays disabled in the demo).
- It runs on **mock providers only**: the full plan → research → verify → report pipeline plays out
  deterministically, with no real web search or LLM calls. **Don't enter real API keys or anything
  sensitive** — a banner says so on every page, and key entry / provider switching is disabled.
- The demo database is **ephemeral** — reset on a schedule (and on every redeploy) — the backend is
  **rate-limited per client** and sits behind **Cloudflare**, so shared use can't run up cost, pile
  up data, or get spammed.

> Frontend on Vercel, backend on Render (free tier — the first request after idle may cold-start for
> a few seconds). Steps to stand up your own hosted demo are in [`docs/DEMO.md`](docs/DEMO.md).

---

## Quick start (Docker)

The fastest way to run the whole stack (backend + frontend, hot-reload) is Docker Compose.
You need **Docker** with the Compose plugin.

```bash
git clone https://github.com/captainkie/ai-deepresearch-autoflow.git
cd ai-deepresearch-autoflow

# 1) Create the backend env file (mock providers need NO keys)
cp backend/.env.example backend/.env

# 2) Bring the stack up
docker compose up --build
```

Then open **http://localhost:3000**. On first run the app is in **setup mode** — create the
initial `superadmin` account, and you're in. The backend API is on **http://localhost:8000**
(versioned under `/api/v1`; health at `/api/v1/health`).

- Frontend (Next.js dev): http://localhost:3000
- Backend (FastAPI): http://localhost:8000
- SQLite DB persists to `./backend/data/` on the host.

Out of the box everything uses **mock** providers, so a full research run works offline. Add real
keys (below) to search the live web and use a real LLM.

---

## Manual setup (without Docker)

**Prerequisites:** Python **3.11 or 3.12**, [`uv`](https://docs.astral.sh/uv/), Node **22+**, and
`pnpm` (via `corepack enable`).

### Backend

```bash
cd backend
cp .env.example .env            # mock providers need no keys
uv sync                         # install deps into .venv
uv run autoflow serve --reload  # → http://127.0.0.1:8000  (uvicorn, factory app)
```

### Frontend

```bash
cd frontend
cp .env.example .env.local      # NEXT_PUBLIC_API_BASE defaults to http://localhost:8000
pnpm install
pnpm dev                        # → http://localhost:3000
```

---

## Configuration &amp; secrets

All backend config is environment variables (prefix `AUTOFLOW_`), read from `backend/.env`.
See **[`backend/.env.example`](./backend/.env.example)** for the fully-commented list.

### Generate the required secrets (production)

In development a missing key is generated ephemerally (won't survive a restart). For a real
deployment (`APP_ENV=production`) these are **required**:

```bash
cd backend

# AUTOFLOW_MASTER_KEY — KEK for the AES-256-GCM credential vault (base64, 32 bytes)
uv run autoflow gen-key

# AUTOFLOW_JWT_SECRET — HS256 signing secret for access tokens (≥32 chars)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste each into `backend/.env`.

### Provider keys

Providers resolve keys at call time, so you only need what you actually use. You can also add keys
in-app via **Admin → Credentials** (stored encrypted in the vault). Env vars:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ZAI_API_KEY`, `MOONSHOT_API_KEY`
(LLM) and `TAVILY_API_KEY`, `SERPER_API_KEY`, `EXA_API_KEY` (search — DuckDuckGo is keyless).

### Google sign-in (optional)

"Continue with Google" lights up when all three OAuth vars are set:

1. In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an
   **OAuth 2.0 Client ID** of type **Web application**.
2. Add the authorized redirect URI:
   `http://localhost:8000/api/v1/auth/google/callback`
   (match your real backend origin in production).
3. Set in `backend/.env`:
   ```env
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
   AUTOFLOW_FRONTEND_URL=http://localhost:3000   # where the callback returns the browser
   ```
4. Restart the backend. (OAuth never creates a `superadmin` — new Google users join as `member`.)

---

## Project structure

```
ai-deepresearch-autoflow/
├── docker-compose.yml         # dev stack (backend + frontend, hot reload)
├── backend/                   # Python · FastAPI · SQLite · uv
│   ├── app/
│   │   ├── api/               # HTTP routers + wire schemas (versioned: API_V1 = "/api/v1")
│   │   ├── core/              # the research engine: planner, researcher, claims,
│   │   │                      #   verifier, contradictions, synthesizer, engine
│   │   ├── providers/         # swappable llm / search / crawl adapters (+ mock)
│   │   ├── services/          # run lifecycle, auth, config, vault, oauth
│   │   ├── security/          # argon2 passwords, JWT, RBAC, rate limit, vault keys
│   │   ├── db/                # SQLite schema + repositories
│   │   ├── models/            # pydantic schemas (engine vocabulary)
│   │   ├── prompts/           # prompt builders + research templates
│   │   ├── cli.py             # `autoflow` CLI   main.py  settings.py
│   └── tests/                 # pytest (offline, mock providers)
├── frontend/                  # Next.js 16 · TypeScript · Tailwind · shadcn/ui · pnpm
│   ├── app/                   # App Router pages (login, settings, admin, runs/[id]…)
│   ├── components/            # UI + run/report/settings/admin components
│   └── lib/                   # typed API client, SSE stream hook, types
└── docs/
    ├── API_CONTRACT.md        # the REST + SSE contract (source of truth)
    └── SECURITY.md            # security model & threat notes
```

## API

REST + SSE, all under **`/api/v1`** (single source of truth: `API_V1` in
`backend/app/api/__init__.py`). Full request/response and event shapes live in
**[`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md)**. Interactive docs at
`http://localhost:8000/docs` when the backend is running.

## CLI

The backend ships an `autoflow` CLI (`cd backend`, then `uv run autoflow <cmd>`):

| Command | What it does |
|---|---|
| `research "<goal>" [--template … --lang en\|th --no-approve]` | Run a research job and print the report |
| `serve [--host --port --reload]` | Run the HTTP API (uvicorn) |
| `gen-key` | Print a fresh base64 `AUTOFLOW_MASTER_KEY` |
| `about` | Authors, license, acknowledgements |

## Testing &amp; quality

```bash
# Backend — ruff + pytest (offline, mock providers)
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

# Frontend — eslint + type-check + production build + unit tests
cd frontend && pnpm exec eslint . && pnpm exec tsc --noEmit && pnpm build && pnpm test
```

CI (`.github/workflows/ci.yml`) runs the backend and frontend gates plus a
[gitleaks](https://github.com/gitleaks/gitleaks) secret scan on every push.

## Tech stack

**Backend:** Python · FastAPI · SQLite · LiteLLM · async · `uv`
**Frontend:** Next.js 16 · React 19 · TypeScript · Tailwind v4 · shadcn/ui · `pnpm`

## Authors

A product of **[Fosivo Labs Co., Ltd.](https://fosivo.com)**, built by
**Narenrit Hadsadintorn** ([@captainkie](https://github.com/captainkie)) together
with **Claude** (Anthropic) as an AI pair-builder. Both are credited in-app on the
**About / Credits** page and in the site footer.

## Acknowledgements

Inspired by [open_deep_research](https://github.com/langchain-ai/open_deep_research),
[deer-flow](https://github.com/bytedance/deer-flow),
[DeepResearch](https://github.com/Alibaba-NLP/DeepResearch), and
[autoresearch](https://github.com/karpathy/autoresearch).
See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for credits and licenses.

## Support

If this project is useful to you, consider supporting its development 💛

- ⭐ Star the repo
- 💖 [GitHub Sponsors](https://github.com/sponsors/captainkie)
- ☕ [Buy Me a Coffee](https://buymeacoffee.com/captainkiez)

## License

**AGPL-3.0** © 2026 **Fosivo Labs Co., Ltd.** — see [LICENSE](./LICENSE).

Also available under a separate **[commercial license](./COMMERCIAL-LICENSE.md)**
for use in closed-source products or hosted services without AGPL obligations.
