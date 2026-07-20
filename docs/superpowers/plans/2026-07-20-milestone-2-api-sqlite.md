# Milestone 2 — API + SQLite + SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or
> superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Expose the M1 engine over HTTP with SQLite persistence and live SSE streaming, exactly
matching `docs/API_CONTRACT.md`, so the existing Next.js frontend works end-to-end. **Demo-first:
no auth yet** — every endpoint is open; auth/RBAC/vault/first-run-setup wrap this in M3.

**Architecture:** FastAPI app. A `RunService` owns per-run `RunHub`s: each hub runs the engine in
a background `asyncio.Task`, persists every event to SQLite, and fans events out to connected SSE
subscribers. Runs start lazily on first stream connect and keep running if the client disconnects;
reconnects replay persisted events by `seq`. Human-in-the-loop plan approval resolves an
`asyncio.Future` from `POST /api/runs/{id}/plan`. Provider API keys come from env for now
(the encrypted vault replaces `provider_keys.get_key` in M3).

**Tech Stack:** FastAPI, `aiosqlite`, `sse-starlette` (already a dep), httpx `ASGITransport` for
tests. Python 3.11–3.12 via `uv`.

**Branch:** `feat/m2-api-sqlite` → PR into `main`.

---

## File Structure

```
backend/app/
├── main.py                # create_app(): FastAPI, CORS, lifespan(db init), mount routers
├── settings.py            # AppSettings (pydantic-settings): DB path, CORS origins, provider env, defaults
├── db/
│  ├── database.py         # Database: aiosqlite connect, init (exec schema.sql), helpers
│  ├── schema.sql          # DDL: runs, sections, sources, events, settings (+ indexes)
│  └── repositories.py     # RunRepo, EventRepo, SettingsRepo (async)
├── services/
│  ├── provider_keys.py    # get_key(provider) -> str|None from env (vault in M3)
│  ├── config_service.py   # current + available providers; read/write settings
│  └── run_service.py      # RunService + RunHub: start/stream/approve/cancel + persist-&-fanout sink
├── api/
│  ├── deps.py             # DI providers (get_db, get_run_service, get_config_service)
│  ├── schemas_api.py      # CreateRun, RunSummary, RunDetail, ConfigResponse, ConfigUpdate, AboutResponse, PlanSubmit
│  ├── health.py           # GET /api/health, GET /api/about
│  ├── config.py           # GET/POST /api/config, GET /api/templates
│  └── runs.py             # POST/GET /api/runs, GET /api/runs/{id}, SSE stream, POST plan, POST cancel
└── cli.py                 # add `serve` subcommand (uvicorn app.main:create_app --factory)
tests/
├── test_db.py
├── test_api_health_about.py
├── test_api_config_templates.py
├── test_api_runs_flow.py
├── test_api_plan_approval.py
└── test_api_reconnect_replay.py
```

**Boundary:** `services/` + `api/` may import `core/`, `providers/`, `db/`. `core/` stays pure
(unchanged from M1). `db/` knows nothing about HTTP.

## Data model — `db/schema.sql`

```sql
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, query TEXT NOT NULL, template TEXT NOT NULL, language TEXT NOT NULL,
  require_plan_approval INTEGER NOT NULL DEFAULT 0,
  llm_provider TEXT, llm_model TEXT, search_provider TEXT, crawl_provider TEXT,
  status TEXT NOT NULL, title TEXT, report_markdown TEXT, error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
  run_id TEXT NOT NULL, id TEXT NOT NULL, idx INTEGER NOT NULL,
  title TEXT, goal TEXT, queries_json TEXT, summary TEXT, status TEXT,
  PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS sources (
  run_id TEXT NOT NULL, ref_num INTEGER NOT NULL, section_id TEXT,
  title TEXT, url TEXT, snippet TEXT, PRIMARY KEY (run_id, ref_num)
);
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL,
  data_json TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq);
```

## Key design — `services/run_service.py`

`RunHub` (one per active run):
- `run_id`, `task: asyncio.Task | None`, `subscribers: set[asyncio.Queue]`, `finished: asyncio.Event`,
  `approval: asyncio.Future[list[PlanSection]] | None`, `cancelled: bool`.

`RunService`:
- `__init__(db, config_service)`; `_hubs: dict[str, RunHub]`.
- `async create(create: CreateRun) -> str`: new uuid, insert `runs` row (status `queued`), return id.
- `async ensure_started(run_id)`: if hub has no task, build a hub, resolve `RunConfig` from the row +
  settings, build providers via registries `(config, get_key)`, then
  `hub.task = asyncio.create_task(self._run(run_id, config, hub))`.
- `async _run(run_id, config, hub)`: build `EventEmitter`? No — engine builds its own emitter from the
  sink. Call `ResearchEngine(llm, search, crawl).run(run_id, query, config, sink=self._make_sink(run_id, hub), approval=self._make_approval(config, hub))`. On completion/exception, set `hub.finished`, push a `None` sentinel to each subscriber queue. Engine already emits `error` + re-raises; catch to avoid crashing the task (log).
- `_make_sink(run_id, hub)`: returns async `sink(event)` that awaits `self._persist(run_id, event)`
  then puts `event` on every subscriber queue (`put_nowait`; drop to unbounded/large queue). Persist
  writes the `events` row and, by `event.type`, upserts derived tables:
  `plan`→insert sections rows; `source`→insert into sources; `section_done`→update section summary;
  `report`→update runs.report_markdown+title; `status`/`done`/`error`→update runs.status(+error).
- `_make_approval(config, hub)`: if not `config.require_plan_approval` → `None`. Else return
  `async def approval(plan)`: create `hub.approval = loop.create_future()`; `return await hub.approval`.
- `async submit_plan(run_id, sections|approve)`: `hub.approval.set_result(sections or plan_sections)`.
  If approve-as-is, resolve with the plan's own sections (read from the emitted `plan` event / sections table).
- `async cancel(run_id)`: `hub.cancelled=True`; `hub.task.cancel()`; set runs.status=`cancelled`.
- `async subscribe(run_id) -> AsyncIterator[Event]`: register a queue in `hub.subscribers`; **first**
  replay all persisted events (seq order) from the `events` table; then loop reading the queue until a
  `None` sentinel or a `done`/`error` event is emitted. The frontend de-dupes by `seq`, so replay/live
  overlap is safe. Always `ensure_started` before subscribing.

## API surface (matches `docs/API_CONTRACT.md`)

`GET /api/health` · `GET /api/about` (from `app.__about__`) · `GET /api/templates` ·
`GET /api/config` · `POST /api/config` · `POST /api/runs` · `GET /api/runs` · `GET /api/runs/{id}` ·
`GET /api/runs/{id}/stream` (SSE via `sse_starlette.EventSourceResponse`) ·
`POST /api/runs/{id}/plan` · `POST /api/runs/{id}/cancel`.

---

## Tasks (TDD, commit after each)

### Task 1: Deps + settings
- [ ] Add `aiosqlite>=0.20` to `pyproject.toml` dependencies; `uv sync --extra dev`; import-check.
- [ ] `app/settings.py`: `AppSettings(BaseSettings)` with `db_path="./data/autoflow.db"`,
  `cors_origins=["http://localhost:3000"]`, `default_language="en"`,
  `default_require_plan_approval=True`, env prefix `AUTOFLOW_`. `get_settings()` cached.
- [ ] Commit `chore(backend): add aiosqlite + app settings`.

### Task 2: Database + schema
**Test:** `tests/test_db.py`
- [ ] Failing test: `Database(":memory:")` after `init()` has tables `runs/sections/sources/events/settings`
  (query `sqlite_master`).
- [ ] Implement `db/schema.sql` (above) + `db/database.py`: `Database` wrapping an `aiosqlite`
  connection; `async init()` runs `executescript(schema.sql)`; `execute/executemany/fetchall/fetchone`
  helpers with `row_factory = aiosqlite.Row`; `async close()`. Ensure parent dir of a file DB exists.
- [ ] Test → PASS. Commit `feat(db): sqlite database + schema`.

### Task 3: Repositories
**Test:** extend `tests/test_db.py`
- [ ] Failing tests: `RunRepo.create/get/list/update_status/set_report`; `EventRepo.append/list_by_run`
  (ordered by seq); `SettingsRepo.get/set/all` round-trip JSON.
- [ ] Implement `db/repositories.py` with those async methods (parameterized SQL; JSON via `json` module;
  timestamps passed in by caller — do NOT call time in the repo).
- [ ] Test → PASS. Commit `feat(db): run/event/settings repositories`.

### Task 4: provider_keys + config_service
**Test:** `tests/test_api_config_templates.py` (partial)
- [ ] `services/provider_keys.py`: `get_key(provider)` maps `anthropic→ANTHROPIC_API_KEY`,
  `openai→OPENAI_API_KEY`, `gemini→GEMINI_API_KEY`, `tavily→TAVILY_API_KEY`, `serper→SERPER_API_KEY`,
  `exa→EXA_API_KEY` via `os.environ`; returns `None` if absent.
- [ ] `services/config_service.py`: `available_llm()` = `["mock"]` + providers with a key;
  `available_search()` = `["mock","duckduckgo"]` + keyed ones; `available_crawl()` = `["mock","jina"]`
  (+`trafilatura` if importable). `current()` reads settings (default `mock`/`mock`), `update(patch)`
  writes settings. Return shape matches `ConfigResponse`.
- [ ] Failing test asserts `available_llm()` contains `"mock"`; after `monkeypatch.setenv` +
  key present, contains that provider. Test → PASS.
- [ ] Commit `feat(services): provider key resolution + config service`.

### Task 5: FastAPI app + health/about/templates/config
**Test:** `tests/test_api_health_about.py`, `tests/test_api_config_templates.py`
- [ ] `app/api/schemas_api.py`: response/request models (`AboutResponse`, `ConfigResponse`,
  `ConfigUpdate`, `TemplateOut`, `CreateRun`, `RunSummary`, `RunDetail`, `PlanSubmit`).
- [ ] `app/api/deps.py`: app-state singletons (`Database`, `ConfigService`, `RunService`) via
  `request.app.state`.
- [ ] `app/api/health.py`: `GET /api/health` → `{status:"ok", version}`; `GET /api/about` →
  `{app, version, license, authors, acknowledgements}` from `app.__about__`.
- [ ] `app/api/config.py`: `GET /api/templates` (from `prompts.templates.TEMPLATES`); `GET /api/config`;
  `POST /api/config`.
- [ ] `app/main.py`: `create_app()` builds `AppSettings`, opens `Database` + services in a `lifespan`,
  adds `CORSMiddleware(cors_origins)`, mounts routers under `/api`.
- [ ] Failing tests via `httpx.AsyncClient(transport=ASGITransport(app), base_url="http://t")`:
  `GET /api/health`→200 ok; `GET /api/about`→authors include "Claude" and "captainkie", license MIT;
  `GET /api/templates`→≥3; `GET /api/config`→has `llm.available` containing "mock". Tests → PASS.
- [ ] Commit `feat(api): app factory + health/about/templates/config`.

### Task 6: RunService (create + run + persist + fan-out) — no HITL yet
**Test:** `tests/test_api_runs_flow.py`
- [ ] `services/run_service.py` per the design above, with `require_plan_approval` path stubbed
  (auto-run). Sink persists events + updates derived tables + fans out.
- [ ] `app/api/runs.py`: `POST /api/runs` (validate CreateRun, default template `deep_research`,
  language from body/config; force provider fields to mock if unset in dev) → `201 {run_id}`;
  `GET /api/runs` → list; `GET /api/runs/{id}` → RunDetail (join sections/sources/report);
  `GET /api/runs/{id}/stream` → `EventSourceResponse` over `run_service.subscribe(id)` yielding
  `event.model_dump_json()`; `POST /api/runs/{id}/cancel`.
- [ ] Failing test: `POST /api/runs {query, config:{llm_provider:"mock",search_provider:"mock",
  crawl_provider:"mock"}}` → 201; open the SSE stream, read frames, assert the ordered types
  `status(planning) → plan → status(researching) → section_start…section_done → status(writing) →
  report_delta… → report → done`; assert final `report` markdown contains `## Sources`; then
  `GET /api/runs/{id}` shows `status=="done"`, non-empty `report`, sources ≥1.
- [ ] Test → PASS. Commit `feat(api): run service + runs endpoints + SSE (auto mode)`.

### Task 7: Human-in-the-loop plan approval
**Test:** `tests/test_api_plan_approval.py`
- [ ] Implement `_make_approval` + `submit_plan`; `POST /api/runs/{id}/plan` accepts
  `{approve:true}` or `{sections:[...]}` and resolves the future.
- [ ] Failing test: create a run with `require_plan_approval:true` (mock providers); stream until an
  `awaiting_plan` event; `POST /api/runs/{id}/plan {approve:true}`; stream continues to `done`;
  edited-sections variant replaces section titles and they appear in later `section_start` events.
- [ ] Test → PASS. Commit `feat(api): human-in-the-loop plan approval`.

### Task 8: Reconnect replay
**Test:** `tests/test_api_reconnect_replay.py`
- [ ] Failing test: run a job to completion; open a **fresh** stream afterward; assert it replays the
  full event history (seq 0..N, monotonic, ends `done`) from the `events` table.
- [ ] Ensure `subscribe` replays persisted events before/around live; already designed — verify + fix.
- [ ] Test → PASS. Commit `feat(api): event replay on (re)connect`.

### Task 9: CLI serve + wallclock/llm-call guards
- [ ] `cli.py`: add `serve [--host --port --reload]` running uvicorn on `app.main:create_app`
  (factory). Manual: `uv run autoflow serve` boots on :8000.
- [ ] Add engine guards deferred from M1: `RunConfig.max_llm_calls` (default e.g. 60) enforced via a
  counter wrapper on the LLM provider, and a per-run wallclock `timeout_s` (default e.g. 900) via
  `asyncio.timeout` in `_run` → emits `error` on breach. Add a unit test for the llm-call cap.
- [ ] Commit `feat(cli,engine): serve command + run guards`.

### Task 10: Lint, types, docs, PR
- [ ] `uv run ruff check . && uv run ruff format --check .` clean; `uv run pytest -q` all pass.
- [ ] Update `backend/README.md`: add "Run the API" (`uv run autoflow serve`) + endpoint list; update
  root `docs/API_CONTRACT.md` if any shape drifted (e.g. note `POST /api/runs/{id}/plan` body).
- [ ] Add `backend/.env.example` entries for `AUTOFLOW_DB_PATH`, `AUTOFLOW_CORS_ORIGINS`.
- [ ] Commit `docs(backend): API quickstart`; push; open PR. Lead verifies + reviews + merges.

---

## Self-Review
- **Spec coverage:** API groups (spec §8 minus auth/admin — deferred to M3), SSE + replay (contract),
  SQLite tables `runs/sections/sources/events/settings` (spec §7), HITL approval (spec §4/§6a-independent),
  `/api/about` (credits), run guards (spec §4). Auth/vault/setup explicitly M3.
- **Placeholders:** none — each task has exact files, the schema, the RunHub design, and test assertions.
- **Type consistency:** `RunService.create/ensure_started/subscribe/submit_plan/cancel`,
  `RunHub` fields, `EventRepo.append/list_by_run`, engine `run(..., sink, approval)` (unchanged M1 signature),
  `EventSourceResponse` frames = `Event.model_dump_json()` used consistently across tasks 6–9.
```
