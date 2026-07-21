# Running a safe public demo + Google sign-in

This covers three things: turning the stack into a **safe demo**, testing
**"Continue with Google"**, and putting the demo on a public URL
(`autoflow-research.fosivo.com`). The live demo runs **permanently** on
**Vercel** (frontend) + **Render** (backend) — no machine of yours has to stay up.

> **Live:** frontend `https://autoflow-research.fosivo.com` (Vercel) · API
> `https://api.autoflow-research.fosivo.com` (Render, demo mode).

---

## 1. Demo mode (safety)

`AUTOFLOW_DEMO_MODE=true` makes the backend:

- **force mock providers** on every run (no real LLM/search calls → no cost, no
  keys needed — the whole pipeline runs deterministically offline);
- **refuse** credential creation, master-key rotation, and provider config
  changes (HTTP 403);
- **refuse email/password sign-up** (HTTP 403) — the demo is **Google-only**, so
  bots can't create throwaway accounts;
- report `demo_mode: true` on `GET /api/v1/health`.

The frontend then shows a sticky **"Live demo — mock data, don't enter real API
keys"** banner, makes Settings read-only, disables the Admin credential form,
replaces the register form with the Google button, and surfaces a one-click
**demo admin** login on the sign-in page.

**Accounts seeded on an empty demo DB:**

| Account | Role | Credentials | For |
|---|---|---|---|
| Private superadmin | `superadmin` | `AUTOFLOW_DEMO_ADMIN_*` (kept by the operator) | full control |
| Published demo admin | `admin` | `AUTOFLOW_DEMO_PUBLIC_ADMIN_*` (shown on the login page) | visitors exploring the admin panel |

The published admin can browse users / audit / the credentials screen but **can't**
save keys (403) or touch the superadmin. Its blast radius is bounded by mock-only
providers, per-client rate limits, and the scheduled reset below.

Run the demo stack locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
# → http://localhost:3000 with the demo banner
```

Back to normal (full features): `docker compose up -d`.

---

## 2. Test "Continue with Google" (locally, on `localhost`)

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

**Backend → Render** (Docker, free plan, Singapore) via [`render.yaml`](../render.yaml):

1. Render dashboard → **New → Blueprint** → pick this repo → it reads
   `render.yaml` (service `autoflow-demo-api`, demo mode, `/api/v1/health`
   health check).
2. Set the `sync:false` secrets in the dashboard: `AUTOFLOW_DEMO_ADMIN_PASSWORD`
   (seeds the private superadmin each boot), `AUTOFLOW_DEMO_RESET_TOKEN` (shared
   secret for the scheduled reset), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
   The published demo-admin login (`AUTOFLOW_DEMO_PUBLIC_ADMIN_*`) ships as plain
   `value:` in `render.yaml` — it's public on purpose.
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

### Google OAuth for the hosted demo

Add the API's callback as an **Authorized redirect URI** on your Google OAuth
client (Google Cloud Console → *Credentials* → your OAuth client):

```
https://api.autoflow-research.fosivo.com/api/v1/auth/google/callback
```

and set the matching env vars on the Render service:

```env
GOOGLE_REDIRECT_URI=https://api.autoflow-research.fosivo.com/api/v1/auth/google/callback
AUTOFLOW_FRONTEND_URL=https://autoflow-research.fosivo.com
```

Keep the `http://localhost:8000/...` redirect URI from §2 on the **same** client
so local dev and the hosted demo both work.

---

## Notes

- **Availability:** always-on (Vercel + Render free tiers). Render's free
  instance cold-starts after idle, so the first request may take a few seconds.
- **Resetting demo data:** the demo DB resets on redeploy (ephemeral disk), and a
  scheduled **GitHub Actions** job
  ([`.github/workflows/demo-reset.yml`](../.github/workflows/demo-reset.yml), weekly)
  POSTs to the token-guarded `POST /api/v1/demo/reset`, which wipes all data
  and re-seeds the demo accounts. Set repo secret `DEMO_RESET_TOKEN` to match
  `AUTOFLOW_DEMO_RESET_TOKEN` on Render. `schedule` only fires on the **default
  branch**, so the cron activates once merged to `main` (run it by hand from the
  Actions tab meanwhile).
- **Anti-abuse:** the API sits behind **Cloudflare** (proxied — DDoS protection,
  hidden origin, trustworthy client IP for rate-limit keying); auth **and** run
  creation are **rate-limited per client**; email sign-up is disabled (Google-only);
  and the DB is wiped on a schedule. Mock-only providers mean abuse can't run up any
  provider cost.
- **Why split origins (frontend + `api.` subdomain)?** Two independent hosts
  can't share a cookie unless they're same-site, so the API lives on the `api.`
  subdomain of the frontend — same registrable domain → the refresh cookie stays
  `SameSite=Lax` — and the backend whitelists the frontend origin for CORS.
