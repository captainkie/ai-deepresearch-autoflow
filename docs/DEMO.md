# Running a safe public demo + Google sign-in

This covers three things: turning the stack into a **safe demo**, testing
**"Continue with Google"**, and putting the demo on a public URL
(`autoflow-research.fosivo.com`). The live demo runs **permanently** on
**Vercel** (frontend) + **Render** (backend); a local **Cloudflare Tunnel** is
kept as a throwaway alternative for testing from your own machine.

> **Live:** frontend `https://autoflow-research.fosivo.com` (Vercel) · API
> `https://api.autoflow-research.fosivo.com` (Render, demo mode).

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

## 3. Public demo at `autoflow-research.fosivo.com`

Two split origins (frontend + API) rather than one, chosen so the refresh
cookie stays `SameSite=Lax`: the API lives at `api.autoflow-research.fosivo.com`,
a **subdomain of the frontend's** `autoflow-research.fosivo.com`, so they share
the `fosivo.com` registrable domain and count as **same-site**. The backend
whitelists the frontend origin in `AUTOFLOW_CORS_ORIGINS`, so cross-origin
`fetch` works with credentials.

### Option A — permanent hosted demo (Vercel + Render) — **live**

No machine of yours has to stay up.

**Backend → Render** (Docker, free plan, Singapore) via [`render.yaml`](../render.yaml):

1. Render dashboard → **New → Blueprint** → pick this repo → it reads
   `render.yaml` (service `autoflow-demo-api`, demo mode, `/api/v1/health`
   health check).
2. Set the `sync:false` secrets in the dashboard: `AUTOFLOW_DEMO_ADMIN_PASSWORD`
   (seeds the demo superadmin each boot), `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`.
3. Add the custom domain `api.autoflow-research.fosivo.com` (Render → Settings →
   Custom Domains); create the matching `CNAME → <svc>.onrender.com` in
   Cloudflare **DNS-only** (grey cloud) so Render can issue the cert.

**Frontend → Vercel** (Next.js production build):

```bash
cd frontend
vercel deploy --prod --yes --scope <team> \
  --build-env NEXT_PUBLIC_API_BASE=https://api.autoflow-research.fosivo.com \
  --env       NEXT_PUBLIC_API_BASE=https://api.autoflow-research.fosivo.com
vercel domains add autoflow-research.fosivo.com --scope <team>
```

Then point `autoflow-research.fosivo.com` at Vercel with a Cloudflare
**`CNAME → cname.vercel-dns.com`, DNS-only** (grey cloud — Vercel manages the
TLS cert). `NEXT_PUBLIC_API_BASE` is inlined at build time, so the frontend
calls the Render API directly.

> The container prod-build "two Reacts" prerender bug that blocked a local
> Docker frontend doesn't occur on Vercel — it builds Next.js natively.

### Option B — throwaway local tunnel (Cloudflare Tunnel)

Handy for a quick share from your own machine. One tunnel serves **both** the
frontend and the API on a **single** origin (`/api/*` → backend, everything else
→ frontend), so there's no CORS to manage.

```bash
cloudflared tunnel login                                   # authorize the zone (once)
cloudflared tunnel create autoflow-demo
cloudflared tunnel route dns autoflow-demo autoflow-research.fosivo.com
```

`cloudflared/config.yml` (single-origin path routing):

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

Serve the **backend (demo mode) in Docker** + the **frontend as a host
production build** (`next dev`'s HMR websocket can't tunnel):

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml \
               -f docker-compose.tunnel.yml up -d backend
cd frontend
NEXT_PUBLIC_API_BASE=https://autoflow-research.fosivo.com pnpm exec next build
NEXT_PUBLIC_API_BASE=https://autoflow-research.fosivo.com pnpm exec next start -p 3000 &
cd .. && cloudflared tunnel --config cloudflared/config.yml run autoflow-demo
```

Switching between A and B is just a Cloudflare DNS flip on
`autoflow-research.fosivo.com` (Vercel CNAME ⇆ the tunnel's `*.cfargotunnel.com`,
proxied).

### Google OAuth (both options)

Add the API's callback as an **Authorized redirect URI** on your Google OAuth
client and set `GOOGLE_REDIRECT_URI` to match:

- Option A: `https://api.autoflow-research.fosivo.com/api/v1/auth/google/callback`
- Option B: `https://autoflow-research.fosivo.com/api/v1/auth/google/callback`

Set `AUTOFLOW_FRONTEND_URL` to `https://autoflow-research.fosivo.com` either way.

---

## Notes

- **Availability:** Option A is always-on (Vercel + Render free tiers; Render's
  free instance cold-starts after idle, so the first request may take a few
  seconds). Option B is live only while your machine + `cloudflared tunnel run`
  are up.
- **Resetting demo data:** Render's free disk is ephemeral, so the demo DB
  resets on redeploy and the `AUTOFLOW_DEMO_ADMIN_*` seed recreates the admin.
  Locally, swap in a fresh DB (`backend/data/`) or wire a scheduled reset.
- **Why split origins on Vercel/Render but single-origin on the tunnel?** The
  tunnel can path-route one hostname to two local ports, dodging CORS. Two
  independent hosts can't, so we use the `api.` subdomain to stay same-site for
  the cookie and whitelist the frontend origin for CORS.
