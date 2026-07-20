# AI DeepResearch AutoFlow — Design Spec

**Date:** 2026-07-20 · **Status:** Draft for review · **Owner:** captainkie (Narenrit)
**Repo (planned):** `github.com/captainkie/ai-deepresearch-autoflow` (public, MIT)

> **Amended by `2026-07-20-engine-v2-trust-templates.md`** (Engine v2: claim-level
> verification, contradiction detection, confidence scoring, adaptive stopping, and structured
> marketing templates). That addendum supersedes parts of §1, §4, §5, §7, §8, §11, §13 below;
> read it alongside this document. Positioning north star:
> *"Deep research your team can trust — self-hosted, secure, every claim cited and verified."*

## 1. Problem & Goal

The office marketing team needs to research topics (especially **competitor brands** and
**market landscapes**) and get a **detailed, cited report** without doing the legwork or
writing code. Today this is manual and slow.

**Goal:** a polished web app where a non-technical user types a research goal, optionally
reviews an AI-generated plan, watches the research happen live, and receives a thorough
Markdown report with citations — in Thai or English. The system is a secure, multi-user
platform with swappable LLM/search providers whose API keys are managed by an admin.

**Non-goals (v1):** scheduled/recurring research, team workspaces/orgs, billing, mobile app,
fine-tuning or self-hosted models, browser-agent (clicking) research.

## 2. Success Criteria

- A user can run "Analyze competitor brand X" end-to-end and get a structured, cited report.
- The full pipeline runs offline with **mock** providers (no API keys) for tests/demos.
- Providers (LLM + search) are swappable via config; keys live **encrypted** in the vault,
  are **never** returned in plaintext by any API, and can be **revoked/expired/rotated**.
- Auth + RBAC gate every sensitive action; there is an audit trail for credential actions.
- Quality gates (lint, types, tests, secret-scan) pass in CI on every PR.
- Reasonable performance: sections research concurrently; report streams live.

## 3. Architecture Overview

Monorepo, two deployables + shared docs:

```
ai-deepresearch-autoflow/
├── backend/          Python 3.11–3.12, FastAPI, SQLite (async engine + REST/SSE API)
│  └── app/
│     ├── core/       research engine: orchestrator, planner, researcher, synthesizer, events
│     ├── providers/  llm/ · search/ · crawl/  (each: base + adapters + mock + registry)
│     ├── security/   crypto (AES-256-GCM vault), password hashing, jwt, rbac
│     ├── db/         SQLite models, migrations, repositories
│     ├── api/        routers: auth, runs, config, admin (users, credentials, audit)
│     ├── prompts/    planner / researcher / synthesizer / templates (i18n)
│     └── main.py     app factory, middleware, DI wiring
├── frontend/         Next.js 15 App Router + TS + Tailwind + shadcn/ui
├── docs/             API_CONTRACT.md, this spec, THIRD_PARTY_NOTICES.md
└── .github/workflows/ CI (lint, typecheck, test, secret-scan)
```

**Layering rule:** `core/` (the engine) is pure — it depends on provider *interfaces* and an
event sink, never on FastAPI, the DB, or HTTP. This keeps it unit-testable and reusable
(CLI, tests, future workers). The API layer wires DB + vault + providers into the engine.

## 4. Research Engine (the core loop)

Custom async orchestrator (no LangGraph); borrows LangGraph's *patterns*.

> **Engine v2 (see addendum):** stages 3–4 below evolve so that a **claim** is the atomic unit:
> research *extracts claims* (each with a source quote), a separate **verifier** role checks each
> claim against its source text, contradictions across sources are surfaced, findings carry a
> **confidence** label, and the final report is a *projection of verified claims* (unsupported ones
> go to an "Unverified" appendix). Stopping becomes **adaptive** (diminishing returns / confidence /
> budget), not iteration-count-driven. New event/data shapes in the addendum §6–§7.

**Stages**
1. **Plan** — `planner.py`: LLM turns the query + template + target language into a
   `ResearchBrief` and an ordered list of `PlanSection`s, each with `title`, `goal`, and
   2–4 seed `queries`. Structured output via tolerant JSON parsing (+ one repair retry).
2. **Plan review (optional, HITL)** — if `require_plan_approval`, the run pauses at
   `awaiting_plan`; the user edits/approves; the engine resumes with the approved sections.
3. **Research (parallel, capped)** — `researcher.py`: for each section, a bounded ReAct loop:
   `search(query) → pick top-K results → crawl pages → LLM-summarize each page against the
   section goal → reflect: "enough, or what's missing?" → optionally issue a follow-up query
   (max N iterations) → compress into section notes with citations [n]`.
   A global **source registry** assigns stable numeric ids used across the whole report.
4. **Synthesize** — `synthesizer.py`: brief + all section notes + sources → final Markdown
   report, **streamed** token-by-token (`report_delta`), ending with a `## Sources` list.

**Events** — the engine emits typed events to an `EventSink` (see API contract). The API
implementation of the sink writes each event to SQLite (for replay) and to a live
`asyncio.Queue` (for SSE). Event types: `status, plan, awaiting_plan, section_start, search,
source, note, section_done, report_delta, report, error, done`.

**Concurrency & performance** — `asyncio` throughout; a shared pooled `httpx.AsyncClient`;
semaphores cap concurrent sections and concurrent page-fetches; `tenacity` backoff on
provider/network errors; per-run (and optional cross-run) URL→content cache to avoid
refetching; cancellation via `asyncio.Task` + a cancel flag.

**Loop limits (config, defaults):** `max_sections=6`, `max_iters_per_section=2`,
`results_per_query=6`, `section_concurrency=3`, `fetch_concurrency=6`. A `max_llm_calls`/run
guard and a per-run wallclock timeout are added in M2 (when runs become long-lived over HTTP).

## 5. Providers (swappable)

Each provider family: an interface (`base.py`), concrete adapters, a **mock**, and a
`registry` that instantiates from config + vault-resolved credentials.

- **LLM** — via **LiteLLM** (one call surface for Anthropic/OpenAI/Gemini/OpenAI-compatible).
  Interface: `complete(messages, …) -> str` and `stream(messages, …) -> AsyncIterator[str]`.
  Mock returns deterministic canned plans/notes/reports for offline E2E tests.
  *(Engine v2)* the **verifier** runs on a separately-configurable cheap/fast model
  (`verifier_provider`/`verifier_model`, e.g. Haiku / GLM / Kimi) — this is the concrete payoff of
  the provider abstraction, not a demo feature.
- **Search** — adapters: **Tavily, Serper, Exa, DuckDuckGo** (keyless) + mock.
  Interface: `search(query, k) -> list[SearchResult]`.
- **Crawl** — adapters: **Jina reader** (`r.jina.ai`, clean markdown), **trafilatura**
  (optional extra) + mock. Interface: `fetch(url) -> PageContent`.

Credentials are resolved **at call time** from the vault (decrypt → use → never persist
plaintext), and the used credential's `last_used_at` + audit entry are recorded.

## 6. Security Design (high bar)

**Passwords** — Argon2id (`argon2-cffi`).

**Sessions** — JWT access token (short TTL, ~15 min) + rotating **refresh token** stored
(hashed) in DB and revocable; delivered as httpOnly, Secure, SameSite=Lax cookies.
**Google OAuth** (Authorization Code + PKCE) as an additional sign-in; links to a user by
verified email. The **first** user is created via the first-run setup flow (§6a), not env.

**RBAC** — roles `superadmin | admin | member | viewer`, enforced by FastAPI dependencies:
- superadmin: everything, incl. system-owner actions — manage admins, rotate the master key,
  system settings. Created once by first-run setup; there is always ≥1 superadmin.
- admin: manage members/viewers, providers/credentials, view audit log, access all runs.
- member: create runs, view/manage own runs, view shared reports.
- viewer: read shared reports only.

### 6a. First-run Setup (Strapi-style)

On a fresh install the `users` table is empty and the app is in **setup mode**:
- `GET /api/setup/status → { needs_setup: bool }` (true iff no users exist).
- The frontend, when `needs_setup`, routes everything to **`/setup`** — a one-time onboarding
  page to register the **superadmin** (name, email, password, with a strength check).
- `POST /api/setup` creates the first user with role `superadmin`, then marks
  `settings.setup_completed = true`. It is **guarded to run only when zero users exist**
  (returns `409` otherwise), so it can never be replayed to seize the instance.
- After setup, `/setup` 404s/redirects to `/login`. No superadmin credentials ever live in
  env or code — the operator sets them through the browser on first launch.
- A separate env checklist (master key, OAuth client, provider base URLs) is validated at
  startup and surfaced on the setup page as readiness indicators.

**Secret Vault (API keys)** — table `provider_credentials`:
`id, provider, label, ciphertext, nonce, key_version, masked_hint, created_by, created_at,
expires_at, status(active|revoked), last_used_at`.
- **AES-256-GCM**; KEK from env `AUTOFLOW_MASTER_KEY` (base64, 32 bytes); random 96-bit
  nonce per secret; ciphertext holds the GCM tag.
- **Write-only via API**: create accepts plaintext; reads return only `masked_hint` + metadata.
  Decryption happens **only** inside the provider layer at call time.
- **Revoke** (status) and **expire** (`expires_at`) — the vault refuses non-active creds.
- **Master-key rotation**: admin endpoint re-encrypts all secrets under a new KEK and bumps
  `key_version`.
- **Audit log** table records credential create/revoke/rotate/use with actor + timestamp.
- **Guardrails**: `APP_ENV=production` requires a real master key (fail-fast if missing);
  dev generates an ephemeral key with a loud warning; `.env`, `*.db`, secrets are gitignored;
  CI runs **gitleaks**. No key value is ever logged.

## 7. Data Model (SQLite)

`users(id, email, name, password_hash?, google_sub?, role, created_at, disabled)` ·
`refresh_tokens(id, user_id, token_hash, expires_at, revoked_at, user_agent)` ·
`provider_credentials(… see §6)` ·
`audit_log(id, actor_id, action, target_type, target_id, meta_json, created_at)` ·
`settings(key, value_json)` — runtime config (`setup_completed`, active providers/models,
default language, require_plan_approval) ·
`runs(id, owner_id, query, template, language, status, title, created_at, updated_at,
error?)` · `sections(id, run_id, idx, title, goal, queries_json, summary?, status)` ·
`sources(id, run_id, ref_num, section_id?, title, url, snippet)` ·
`events(id, run_id, seq, type, data_json, ts)`.

Access via small repository modules; a lightweight migration runner creates/updates schema
at startup.

*(Engine v2, see addendum §6)* adds `claims`, `claim_sources` (m2m to `sources.ref_num`),
`verifications`, and `contradictions` for the verified-claim model; `sources` stays the global
numbered registry.

## 8. API

Full contract in `docs/API_CONTRACT.md`. Summary of groups:
- **Setup** — `GET /api/setup/status`, `POST /api/setup` (one-time superadmin; §6a).
- **Auth** — `POST /api/auth/register`, `/login`, `/logout`, `/refresh`, `GET /api/auth/me`,
  Google: `GET /api/auth/google/start`, `GET /api/auth/google/callback`.
- **Runs** — `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}`,
  `GET /api/runs/{id}/stream` (SSE), `POST /api/runs/{id}/plan`, `POST /api/runs/{id}/cancel`.
- **Config/Templates** — `GET/POST /api/config`, `GET /api/templates`, `GET /api/about`
  (authors, license, acknowledgements — powers the in-app credits page/footer).
- **Admin** — `GET/POST/PATCH /api/admin/users`, `GET/POST/DELETE /api/admin/credentials`
  (+ `/revoke`, `/rotate`), `GET /api/admin/audit`.

All mutating admin/credential routes require `admin`; run routes require ownership or role.
The API contract doc will be extended with the auth/admin shapes before those milestones.

## 9. Frontend (Next.js)

Screens: **Setup** (first-run superadmin onboarding, Strapi-style; §6a) · **Login/Register**
(email + "Continue with Google") · **Home** (query + template + language) · **Run** (live
timeline, plan-review card, streamed report with TOC + copy/download) · **History** ·
**Settings** (providers/models/language/HITL toggle) · **Admin** (users, credentials
add/revoke/expire/rotate, audit log) · **About / Credits** (authors, license, third-party
acknowledgements). Nav is role-gated; setup mode overrides all routes.
Polished, editorial, premium look (frontend-design + shadcn), light/dark, excellent report
typography. Talks to the backend via the typed client from the API contract.

**In-app credits (required):** a persistent **footer** and an **About / Credits** page credit
the authors — **Narenrit Hadsadintorn (captainkie)** and **Claude (Anthropic)** as AI
pair-builder — show the **MIT license**, and link the four inspiration projects with their
licenses (from `THIRD_PARTY_NOTICES.md`). Backend exposes `GET /api/about` returning
`{ app, version, license: "MIT", authors: [...], acknowledgements: [...] }` so the page is
data-driven and stays in sync.

## 10. Quality Gates & CI

- **Backend:** `ruff` (lint+format), `mypy` (typed), `pytest` (unit + offline E2E with mocks;
  crypto/auth have focused tests incl. "plaintext never serialized").
- **Frontend:** `eslint`, `tsc --noEmit`, `pnpm build`.
- **CI (GitHub Actions):** on PR → run all of the above + **gitleaks** secret scan.
- **pre-commit** mirrors the fast checks locally.
- Definition of done per PR: gates green, no secrets, docs updated.

## 10a. Documentation (a first-class deliverable)

Docs must let a newcomer **understand, install, and run** the project unaided:
- **README.md** — front door: what/why, feature highlights, **product screenshots**, a
  copy-paste **Quickstart** (offline mock mode → real providers), architecture diagram,
  links to deeper docs.
- **Product screenshots/GIF** — captured with **Playwright** driving the finished app in
  **mock mode** (deterministic seed data → stable, safe images with no real keys/PII). Stored
  under `docs/screenshots/` and embedded in the README + relevant docs. This runs in
  milestone 6, **after** the UI is complete; a small capture script makes them reproducible.
- **docs/INSTALL.md** — prerequisites (Python/uv, Node/pnpm), clone, backend + frontend setup,
  `.env` files, **first-run superadmin** walkthrough, dev + prod run commands, troubleshooting.
- **docs/CONFIGURATION.md** — every env var (incl. `AUTOFLOW_MASTER_KEY`, Google OAuth,
  provider base URLs), how to generate the master key, choosing providers, language defaults.
- **docs/SECURITY.md** — vault design, threat model, key rotation, reporting vulnerabilities.
- **docs/ARCHITECTURE.md** — engine loop, layering, data flow, extension points (add a provider).
- **backend/.env.example** + **frontend/.env.example** — all vars documented, no real secrets.
- Inline: concise docstrings on public modules; the API contract stays authoritative for shapes.
- Docs are updated in the same PR as the code they describe (enforced by DoD above).

## 11. Build Order (milestone PRs, GitHub flow)

Each is a branch → PR → merge into `main`:
1. **Scaffold + engine core + providers + mocks + CLI + tests** — E2E works offline.
2. **API + SQLite + SSE + config/templates** — engine reachable over HTTP with persistence.
3. **Security: vault (AES-256-GCM), auth (pwd+JWT+refresh), RBAC, audit, first-run setup
   (§6a); Google OAuth.**
4. **Engine v2 (addendum):** claim extraction + verifier role/model routing + contradiction
   detection + confidence scoring + adaptive stopping + structured templates & comparison-table
   synthesis (new tables/events). *Comes before the research-UX frontend so the UI is built once
   against the final report/event shape.*
5. **Frontend: setup + auth + research UX + streaming + report** — incl. confidence badges,
   contradiction flags, and the comparison table.
6. **Frontend: admin panel (users, credentials, audit) + settings** (+ verifier model / verification level).
7. **CI, full docs (§10a), README (hero rewrite per addendum §1), THIRD_PARTY_NOTICES, polish, hardening.**

Docs land incrementally with each milestone; the final milestone completes and polishes them.

## 12. Open Source / Attribution

License **MIT**. `THIRD_PARTY_NOTICES.md` + README "Acknowledgements" credit the four
inspirations with links and licenses: Alibaba-NLP/DeepResearch (Apache-2.0),
langchain-ai/open_deep_research (MIT), bytedance/deer-flow (MIT), karpathy/autoresearch
(MIT). We write original code inspired by their patterns; no files are copied verbatim.

## 13. Key Risks

- **Key leakage** — mitigated by write-only vault, encryption at rest, no plaintext in
  logs/responses, gitleaks, gitignored secrets. Highest-priority test coverage.
- **Provider cost/latency/rate limits** — concurrency caps, backoff, caching, loop limits.
- **Report quality / hallucination** — *(Engine v2)* claim-level grounding + a separate verifier +
  confidence + contradiction surfacing; the report body renders only verified claims (unsupported →
  appendix). Cost/latency mitigated by batching, candidate-only verification, a cheap verifier model,
  and `verification_level` (default `light`). Mock-based tests assert structure incl.
  "body contains no unverified claims"; real providers assert end-to-end shape.
- **Scope size** — controlled by strict milestone PRs; each milestone is independently useful.
