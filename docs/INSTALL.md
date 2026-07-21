# Installation

Get **AI DeepResearch AutoFlow** running locally — the whole stack works
**offline on mock providers with no API keys**, so you can be up in minutes and
add real keys later.

This guide mirrors the README's *Quick start (Docker)* and *Manual setup*
sections. For every environment variable see
**[`CONFIGURATION.md`](./CONFIGURATION.md)**; for how the pieces fit together see
**[`ARCHITECTURE.md`](./ARCHITECTURE.md)**; for the security model see
**[`SECURITY.md`](./SECURITY.md)**.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| **Python** | **3.11 or 3.12** | Backend runtime. |
| **[uv](https://docs.astral.sh/uv/)** | latest | Python dependency & venv manager. |
| **Node.js** | **22+** | Frontend runtime. |
| **pnpm** | via `corepack enable` | Frontend package manager. |
| **Docker** | with the Compose plugin | Optional — only for the Docker path. |

Enable pnpm through Corepack (ships with Node):

```bash
corepack enable
```

---

## Clone

```bash
git clone https://github.com/captainkie/ai-deepresearch-autoflow.git
cd ai-deepresearch-autoflow
```

---

## Option A — Docker Compose (fastest)

Runs backend + frontend together with hot reload. You only need Docker with the
Compose plugin.

```bash
# 1) Create the backend env file (mock providers need NO keys)
cp backend/.env.example backend/.env

# 2) Bring the stack up
docker compose up --build
```

Then open **http://localhost:3000**.

- Frontend (Next.js dev): http://localhost:3000
- Backend (FastAPI): http://localhost:8000 — versioned under `/api/v1`, health at
  `/api/v1/health`, interactive docs at `/docs`
- SQLite persists to `./backend/data/` on the host (survives `docker compose down`).

Out of the box everything uses **mock** providers, so a full research run works
offline. Continue to the [first-run superadmin](#first-run-superadmin) step.

---

## Option B — Manual setup (without Docker)

### Backend

```bash
cd backend
cp .env.example .env            # mock providers need no keys
uv sync                         # install deps into .venv
uv run autoflow serve --reload  # → http://127.0.0.1:8000  (uvicorn, factory app)
```

The `autoflow` CLI ships a few more commands (run them from `backend/`):

| Command | What it does |
|---|---|
| `uv run autoflow research "<goal>" [--template … --lang en\|th --no-approve]` | Run a research job and print the report |
| `uv run autoflow serve [--host --port --reload]` | Run the HTTP API (uvicorn) |
| `uv run autoflow gen-key` | Print a fresh base64 `AUTOFLOW_MASTER_KEY` |
| `uv run autoflow about` | Authors, license, acknowledgements |

`autoflow research` runs the full pipeline offline (mock providers) and prints
the Markdown report — a quick way to sanity-check the engine without the frontend.

### Frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env.local      # NEXT_PUBLIC_API_BASE defaults to http://localhost:8000
pnpm install
pnpm dev                        # → http://localhost:3000
```

Then open **http://localhost:3000**.

---

## First-run superadmin

On a fresh install the `users` table is empty and the app is in **setup mode** —
the frontend routes everything to **`/setup`**:

1. Open **http://localhost:3000** (it redirects to `/setup`).
2. Register the initial **superadmin** — name, email, and password (with a
   strength check). This is the only way the first account is created; no
   superadmin credentials ever live in env or code.
3. You are signed in as `superadmin` and land in the app.

Under the hood: the frontend checks `GET /api/v1/setup/status` → `{ needs_setup }`,
and `POST /api/v1/setup` creates the first user as `superadmin`. It is guarded to
run **only when zero users exist** (returns `409` otherwise), so it can never be
replayed to seize a running instance. After setup, `/setup` redirects to `/login`.

Everything now runs on **mock** providers. To search the live web and use a real
LLM, add provider keys — either as env vars in `backend/.env` or in-app via
**Admin → Credentials** (stored encrypted in the vault) — then pick the provider
in **Settings**. See [`CONFIGURATION.md`](./CONFIGURATION.md#provider-api-keys).

---

## Running in production

Set `APP_ENV=production`. Two secrets are then **required** — the app fails fast at
startup if either is missing or malformed (in development a missing one is
generated ephemerally and will not survive a restart):

```bash
cd backend

# AUTOFLOW_MASTER_KEY — KEK for the AES-256-GCM credential vault (base64, 32 bytes)
uv run autoflow gen-key

# AUTOFLOW_JWT_SECRET — HS256 signing secret for access tokens (≥32 chars)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste each into `backend/.env`. Also review for a real deployment:

- **`AUTOFLOW_CORS_ORIGINS`** — set to your real frontend origin(s), comma-separated.
- **`NEXT_PUBLIC_API_BASE`** (frontend) — set to your real backend origin.
- **Google OAuth** (optional) — set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `GOOGLE_REDIRECT_URI`, and `AUTOFLOW_FRONTEND_URL` (see
  [`CONFIGURATION.md`](./CONFIGURATION.md#google-oauth-optional)).
- **Provider keys** for the LLM/search providers you intend to use.

Every variable is documented in **[`CONFIGURATION.md`](./CONFIGURATION.md)**.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| **Port already in use** (`3000` / `8000`) | Stop the other process, or run the backend on another port: `uv run autoflow serve --port 8010` and set the frontend's `NEXT_PUBLIC_API_BASE` to match. |
| **CORS errors in the browser** (blocked requests, failed SSE) | The frontend origin must be listed in the backend's `AUTOFLOW_CORS_ORIGINS`, and the frontend's `NEXT_PUBLIC_API_BASE` must point at the backend. Both default to `http://localhost:3000` / `http://localhost:8000`; if you change one, change the other. |
| **Runs finish instantly / results look canned** | You're on **mock** providers (the default). Add real provider keys and select the provider in **Settings** or **Admin → Credentials** to hit the live web and a real LLM. |
| **Real provider returns no results / auth errors** | Check the key is set (env var in `backend/.env` or an active vault credential) and that the provider is selected in **Settings**. `GET /api/v1/config` shows which providers are currently *available*. |
| **`AUTOFLOW_MASTER_KEY` / `AUTOFLOW_JWT_SECRET` fail-fast at startup** | Only enforced when `APP_ENV=production`. Generate them with the commands above, or run with `APP_ENV=development` for local work. |
| **Hosted demo (Render free tier) is slow on the first request** | The free tier cold-starts after idle — the first request can take a few seconds while the backend spins up, then it's responsive. |
| **Sessions drop on restart in dev** | Expected when `AUTOFLOW_JWT_SECRET` is unset (dev uses an ephemeral secret). Set a fixed one to persist sessions. |
