# Running a safe public demo + Google sign-in

This covers three things: turning the stack into a **safe demo**, testing
**"Continue with Google"**, and putting the demo on a public URL
(`autoflow-research.fosivo.com`) via **Cloudflare Tunnel**.

---

## 1. Demo mode (safety)

`AUTOFLOW_DEMO_MODE=true` makes the backend:

- **force mock providers** on every run (no real LLM/search calls → no cost, no
  keys needed — the whole pipeline runs deterministically offline);
- **refuse** credential creation, master-key rotation, and provider config
  changes (HTTP 403);
- report `demo_mode: true` on `GET /api/v1/health`.

The frontend then shows a sticky **"Live demo — mock data, don't enter real API
keys"** banner, makes Settings read-only, and disables the Admin credential form.

Run the demo stack locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
# → http://localhost:3000 with the demo banner
```

Back to normal (full features): `docker compose up -d`.

---

## 2. Test "Continue with Google" (locally — no tunnel needed)

Google allows `http://localhost` redirect URIs for development, so you can test
sign-in without deploying anything.

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) →
   **Create Credentials → OAuth client ID → Web application**.
2. **Authorized redirect URIs**: `http://localhost:8000/api/v1/auth/google/callback`
3. Put the values in `backend/.env`:
   ```env
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
   AUTOFLOW_FRONTEND_URL=http://localhost:3000
   ```
4. Restart the backend (`docker compose restart backend`). "Continue with
   Google" now lights up. (On the OAuth **consent screen**, add your email under
   *Test users*, or publish the app.)

> OAuth never creates a superadmin — a new Google user joins as `member`.

---

## 3. Public demo at `autoflow-research.fosivo.com` (Cloudflare Tunnel)

One tunnel serves **both** the frontend and the API on a single origin
(`/api/*` → backend, everything else → frontend), so there's no CORS to manage.

**Prereqs:** `cloudflared` installed (✓), `fosivo.com` on Cloudflare.

```bash
# 3a. One-time: authorize cloudflared for the fosivo.com zone (opens a browser)
cloudflared tunnel login

# 3b. Create the tunnel + DNS record
cloudflared tunnel create autoflow-demo
cloudflared tunnel route dns autoflow-demo autoflow-research.fosivo.com
```

**3c.** Create `~/.cloudflared/config.yml` (single-origin path routing):

```yaml
tunnel: autoflow-demo
ingress:
  - hostname: autoflow-research.fosivo.com
    path: ^/api/.*
    service: http://localhost:8000
  - hostname: autoflow-research.fosivo.com
    service: http://localhost:3000
  - service: http_status:404
```

**3d.** Point the app at the public origin — in `docker-compose.demo.yml`,
uncomment the tunnel lines so:

- backend: `AUTOFLOW_CORS_ORIGINS` + `AUTOFLOW_FRONTEND_URL` = `https://autoflow-research.fosivo.com`
- frontend: `NEXT_PUBLIC_API_BASE` = `https://autoflow-research.fosivo.com`

Then restart the demo stack and run the tunnel:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
cloudflared tunnel run autoflow-demo      # → https://autoflow-research.fosivo.com is live
```

**3e.** Add the production redirect URI to your Google OAuth client:
`https://autoflow-research.fosivo.com/api/v1/auth/google/callback`, and set
`GOOGLE_REDIRECT_URI` + `AUTOFLOW_FRONTEND_URL` to the public origin.

---

## Notes

- **Availability:** the tunnel is live only while your machine + `cloudflared
  tunnel run` are up. For always-on, run it under a service (`cloudflared
  service install`) on a small always-on box, or move to a hosted backend.
- **Resetting demo data:** stop the stack and swap in a fresh DB
  (`backend/data/`), or wire a scheduled reset — accumulated demo runs/accounts
  otherwise pile up.
- **Why not Cloudflare Pages for everything?** Pages/Workers can host the
  Next.js frontend but not the FastAPI backend (long-running, SSE, SQLite). The
  tunnel keeps the real backend on your machine; a persistent alternative is
  frontend → Pages + backend → a container host (Fly.io/Railway/Render).
