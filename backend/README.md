# AutoFlow Research — Backend

A provider-agnostic, fully-async **deep-research engine**. Given a query it runs
`plan → parallel per-section research → streamed, cited Markdown report`. The engine
is pure — it depends only on provider *interfaces* and an async event sink — so it
runs entirely offline with deterministic **mock** providers (no API keys) and is
covered end-to-end by tests. **Milestone 2** wraps the engine in a **FastAPI** app
with **SQLite** persistence and live **SSE** streaming (with reconnect replay and
human-in-the-loop plan approval), matching [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).
Auth, the secrets vault, and first-run setup arrive in Milestone 3.

## Architecture

```
app/
├── models/schemas.py     pydantic models + enums (single source of data shapes)
├── core/                 pure engine
│   ├── events.py         Event emitter + sinks (monotonic seq, ts)
│   ├── sources.py        SourceRegistry (stable citation ids, dedup)
│   ├── planner.py        query -> validated Plan
│   ├── researcher.py     per-section bounded research loop
│   ├── synthesizer.py    streamed report + guaranteed "## Sources"
│   └── engine.py         ResearchEngine orchestrator
├── prompts/              planner / researcher / synthesizer / templates (i18n)
├── providers/
│   ├── llm/              base Protocol · mock · litellm · registry
│   ├── search/           base · mock · tavily/serper/exa/duckduckgo · registry
│   └── crawl/            base · mock · jina/trafilatura · registry
├── db/                   SQLite: database.py · schema.sql · repositories.py
├── services/             provider_keys · config_service · run_service (RunHub/SSE)
├── api/                  FastAPI routers: health · config · runs (+ deps/schemas)
├── settings.py           AppSettings (AUTOFLOW_* env): db path, CORS, defaults
├── main.py               create_app() factory — lifespan, CORS, routers
├── config.py             load_run_config() — env (AUTOFLOW_*) + overrides
└── cli.py                `autoflow research ...` / `autoflow serve` / `autoflow about`
```

**Design boundaries:** `core/` never imports provider concretes (only the `base`
Protocols + `schemas`); providers never import `core`; the **registries** are the only
place that maps config → a concrete provider. Data shapes mirror
[`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).

## Requirements

- [`uv`](https://docs.astral.sh/uv/) (manages Python + deps)
- Python **3.12** (pinned via `.python-version`; the system Python may be newer and
  lack wheels for some deps — always use `uv`)

## Install

```bash
cd backend
uv python pin 3.12      # already pinned; safe to re-run
uv sync --extra dev     # creates .venv and installs deps + dev tools
```

Optional extra for the `trafilatura` crawl adapter:

```bash
uv sync --extra dev --extra crawl
```

## Run the tests

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## CLI quickstart (offline, mock providers)

No API keys needed — the mock providers are deterministic:

```bash
uv run autoflow research "Analyze competitor brand: ExampleCo" \
  --lang en --llm mock --search mock --crawl mock
```

This prints live progress (to stderr) and the final Markdown report ending with a
`## Sources` list (to stdout). Useful flags:

- `--template deep_research|competitor_brand|market_landscape`
- `--lang en|th`
- `--approve` / `--no-approve` — pause for plan approval (HITL); the CLI auto-approves
- `--json-events` — emit raw JSON event lines instead of pretty output

Show authors / license / acknowledgements:

```bash
uv run autoflow about
```

## Run the API (Milestone 2)

Start the FastAPI app (uvicorn) — it opens the SQLite DB, mounts the routers, and
serves the SSE stream. **Demo-first: no auth yet** (every endpoint is open; auth,
the vault, and first-run setup arrive in M3):

```bash
uv run autoflow serve                 # http://127.0.0.1:8000  (--host/--port/--reload)
```

The DB lives at `AUTOFLOW_DB_PATH` (default `./data/autoflow.db`; parent dir is
auto-created). Allowed browser origins come from `AUTOFLOW_CORS_ORIGINS`
(comma-separated, default `http://localhost:3000`). Mock providers still need no
keys, so the whole flow runs offline.

### Endpoints (see [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md))

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness + version |
| `GET` | `/api/about` | Authors, license, acknowledgements |
| `GET` | `/api/templates` | Research templates |
| `GET` / `POST` | `/api/config` | Read / update runtime provider config |
| `POST` | `/api/runs` | Create a run → `{ run_id }` |
| `GET` | `/api/runs` | List runs (newest first) |
| `GET` | `/api/runs/{id}` | Full run detail (plan, sections, sources, report) |
| `GET` | `/api/runs/{id}/stream` | **SSE** event stream (starts/resumes the run; replays by `seq`) |
| `POST` | `/api/runs/{id}/plan` | Approve/edit the plan: `{ "approve": true }` or `{ "sections": [...] }` |
| `POST` | `/api/runs/{id}/cancel` | Cancel a run |

A run executes in a background task and keeps going if the SSE client disconnects;
reconnecting **replays** the persisted event history first (each event has a
monotonic `seq`), so replay/live overlap is safe — the frontend de-dupes by `seq`.

Create a run and follow it with `curl` (mock providers, no keys):

```bash
RUN=$(curl -sf -X POST http://127.0.0.1:8000/api/runs \
  -H 'content-type: application/json' \
  -d '{"query":"Analyze competitor brand: ExampleCo","require_plan_approval":false,
       "config":{"llm_provider":"mock","search_provider":"mock"}}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["run_id"])')
curl -sN http://127.0.0.1:8000/api/runs/$RUN/stream   # streams status → plan → … → report → done
```

## Point at real providers (env vars)

Copy `.env.example` to `.env` and set the selectors + keys, or pass the flags. The CLI
resolves keys from the environment at call time.

| Family | Providers | Selector | Keys |
| --- | --- | --- | --- |
| LLM | `mock`, `anthropic`, `openai`, `gemini`, `litellm` | `AUTOFLOW_LLM_PROVIDER` / `--llm` | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` |
| Search | `mock`, `tavily`, `serper`, `exa`, `duckduckgo` | `AUTOFLOW_SEARCH_PROVIDER` / `--search` | `TAVILY_API_KEY`, `SERPER_API_KEY`, `EXA_API_KEY` (DuckDuckGo is keyless) |
| Crawl | `mock`, `jina`, `trafilatura` | `AUTOFLOW_CRAWL_PROVIDER` / `--crawl` | `JINA_API_KEY` (optional) |

Example with real providers:

```bash
export AUTOFLOW_LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-...
export AUTOFLOW_SEARCH_PROVIDER=duckduckgo   # keyless
uv run autoflow research "Market landscape for EV charging in Thailand" --lang th
```

## Credits

**AI DeepResearch AutoFlow** — MIT. Built by **Narenrit Hadsadintorn (captainkie)** and
**Claude (Anthropic)** as AI pair-builder. Inspired by `open_deep_research`,
`deer-flow`, `DeepResearch`, and `autoresearch` (see `app/__about__.py`).
