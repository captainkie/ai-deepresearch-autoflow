# Milestone 1 — Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or
> superpowers:subagent-driven-development to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A provider-agnostic async deep-research engine that runs fully offline with mock
providers — `query → plan → parallel research loop → streamed report` — driven by a CLI and
covered by TDD tests. No HTTP/DB/auth yet (those are later milestones).

**Architecture:** Pure `core/` engine depends only on provider *interfaces* and an async event
sink. `providers/` supply LLM (LiteLLM + mock), search (Tavily/Serper/Exa/DuckDuckGo + mock),
and crawl (Jina/trafilatura + mock). A `SourceRegistry` gives stable citation ids. The mock
providers are deterministic so the whole pipeline is unit- and E2E-testable without API keys.

**Tech Stack:** Python 3.11–3.12, `uv`, pydantic v2, asyncio, httpx, litellm, tenacity, ddgs,
pytest + pytest-asyncio, ruff.

**Branch:** `feat/m1-engine-core` → PR into `main`.

---

## File Structure

```
backend/
├── pyproject.toml                       # deps (already created)
├── .env.example                         # documented env vars
├── app/
│  ├── __init__.py
│  ├── config.py                         # RunConfig defaults + settings helpers
│  ├── cli.py                            # `autoflow research ...`
│  ├── models/
│  │  ├── __init__.py
│  │  └── schemas.py                     # ALL pydantic models + enums (shared vocabulary)
│  ├── core/
│  │  ├── __init__.py
│  │  ├── events.py                      # Event, EventEmitter, sink type, ListSink
│  │  ├── sources.py                     # SourceRegistry
│  │  ├── planner.py                     # Planner
│  │  ├── researcher.py                  # Researcher (per-section loop)
│  │  ├── synthesizer.py                 # Synthesizer (streamed report)
│  │  └── engine.py                      # ResearchEngine orchestrator
│  ├── prompts/
│  │  ├── __init__.py
│  │  ├── templates.py                   # report templates + i18n language directive
│  │  ├── planner.py                     # build_planner_messages()
│  │  ├── researcher.py                  # summarize/reflect/compress message builders
│  │  └── synthesizer.py                 # build_report_messages()
│  ├── providers/
│  │  ├── __init__.py
│  │  ├── json_utils.py                  # tolerant JSON extraction + repair
│  │  ├── llm/{__init__,base,mock,litellm_provider,registry}.py
│  │  ├── search/{__init__,base,mock,tavily,serper,exa,duckduckgo,registry}.py
│  │  └── crawl/{__init__,base,mock,jina,trafilatura_provider,registry}.py
└── tests/
   ├── __init__.py
   ├── conftest.py                       # fixtures: mock providers, engine, config
   ├── test_schemas.py
   ├── test_json_utils.py
   ├── test_mock_providers.py
   ├── test_sources.py
   ├── test_planner.py
   ├── test_researcher.py
   ├── test_synthesizer.py
   └── test_engine_e2e.py
```

**Design boundaries**
- `core/*` NEVER imports `providers/*` concretes — only the `base` Protocols + `schemas`.
- Providers NEVER import `core`. Registries are the only place that reads config → concrete.
- `schemas.py` is the single source of truth for data shapes and mirrors `docs/API_CONTRACT.md`.

---

## Shared Vocabulary (implemented in Task 2, referenced everywhere)

```python
# app/models/schemas.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

class Language(str, Enum):
    th = "th"
    en = "en"

class RunStatus(str, Enum):
    queued = "queued"; planning = "planning"; awaiting_plan = "awaiting_plan"
    researching = "researching"; writing = "writing"; done = "done"
    error = "error"; cancelled = "cancelled"

class EventType(str, Enum):
    status = "status"; plan = "plan"; awaiting_plan = "awaiting_plan"
    section_start = "section_start"; search = "search"; source = "source"
    note = "note"; section_done = "section_done"
    report_delta = "report_delta"; report = "report"; error = "error"; done = "done"

class SearchResult(BaseModel):
    title: str; url: str; snippet: str = ""; score: float | None = None

class PageContent(BaseModel):
    url: str; title: str = ""; text: str = ""; ok: bool = True; error: str | None = None

class Source(BaseModel):
    id: int; title: str; url: str; snippet: str = ""; section_id: str | None = None

class PlanSection(BaseModel):
    id: str; title: str; goal: str; queries: list[str] = Field(default_factory=list)

class ResearchBrief(BaseModel):
    objective: str; audience: str = ""; key_questions: list[str] = Field(default_factory=list)

class Plan(BaseModel):
    brief: ResearchBrief; sections: list[PlanSection]

class Event(BaseModel):
    seq: int; run_id: str; ts: int; type: EventType; data: dict

class RunConfig(BaseModel):
    llm_provider: str = "mock"; llm_model: str = "mock-1"
    search_provider: str = "mock"; crawl_provider: str = "mock"
    language: Language = Language.en; template: str = "deep_research"
    require_plan_approval: bool = False
    max_sections: int = 6; max_iters_per_section: int = 2
    results_per_query: int = 6; fetch_per_query: int = 3
    section_concurrency: int = 3; fetch_concurrency: int = 6
```

## Provider Interfaces (Task 4) — the contract mocks + real adapters honor

```python
# app/providers/llm/base.py
from typing import Protocol, AsyncIterator
class LLMProvider(Protocol):
    async def complete(self, messages: list[dict], *, tag: str | None = None,
                       temperature: float = 0.3, max_tokens: int | None = None,
                       json: bool = False) -> str: ...
    def stream(self, messages: list[dict], *, tag: str | None = None,
               temperature: float = 0.3, max_tokens: int | None = None) -> AsyncIterator[str]: ...

# app/providers/search/base.py
class SearchProvider(Protocol):
    async def search(self, query: str, k: int = 6) -> list[SearchResult]: ...

# app/providers/crawl/base.py
class CrawlProvider(Protocol):
    async def fetch(self, url: str) -> PageContent: ...
```

`tag` values used by the engine: `"plan" | "summarize" | "reflect" | "compress" | "report"`.
Real providers ignore `tag`; the mock uses it to select a deterministic canned response.

---

## Tasks (TDD, bite-sized, commit after each)

### Task 1: Project bootstrap (venv + deps)
**Files:** Modify `backend/pyproject.toml` (done); create `backend/app/__init__.py`,
`backend/app/__about__.py`, `backend/tests/__init__.py`, `backend/.env.example`.
- [ ] Step 0: Create `app/__about__.py` — the single source of credit/metadata used by the CLI
  now and `GET /api/about` later:
  ```python
  APP_NAME = "AI DeepResearch AutoFlow"
  VERSION = "0.1.0"
  LICENSE = "MIT"
  AUTHORS = [
      {"name": "Narenrit Hadsadintorn", "handle": "captainkie", "role": "Author"},
      {"name": "Claude (Anthropic)", "handle": "anthropic", "role": "AI pair-builder"},
  ]
  ACKNOWLEDGEMENTS = [
      {"name": "open_deep_research", "url": "https://github.com/langchain-ai/open_deep_research", "license": "MIT"},
      {"name": "deer-flow", "url": "https://github.com/bytedance/deer-flow", "license": "MIT"},
      {"name": "DeepResearch", "url": "https://github.com/Alibaba-NLP/DeepResearch", "license": "Apache-2.0"},
      {"name": "autoresearch", "url": "https://github.com/karpathy/autoresearch", "license": "MIT"},
  ]
  ```
- [ ] Step 1: Create the package `__init__.py` files (empty) and `.env.example` documenting:
  `APP_ENV`, `AUTOFLOW_MASTER_KEY` (later), provider keys `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`, `EXA_API_KEY`,
  and `AUTOFLOW_*` provider selectors. Include a comment that mock providers need no keys.
- [ ] Step 2: `cd backend && uv python pin 3.12 && uv sync --extra dev` (creates `.venv`,
  resolves deps). Expected: lockfile + venv created, exit 0.
- [ ] Step 3: `uv run python -c "import fastapi, litellm, pydantic, httpx, ddgs; print('ok')"`
  Expected: `ok`.
- [ ] Step 4: Commit `chore(backend): scaffold package + pin python + deps`.

### Task 2: Schemas
**Files:** Create `app/models/schemas.py`, `app/models/__init__.py`; Test `tests/test_schemas.py`.
- [ ] Step 1: Write failing test asserting `RunConfig()` defaults (`llm_provider=="mock"`,
  `require_plan_approval is False`), `Plan` round-trips from dict, `EventType.report_delta`
  value `"report_delta"`.
- [ ] Step 2: `uv run pytest tests/test_schemas.py -q` → FAIL (module missing).
- [ ] Step 3: Implement `schemas.py` exactly as in "Shared Vocabulary" above.
- [ ] Step 4: `uv run pytest tests/test_schemas.py -q` → PASS.
- [ ] Step 5: Commit `feat(schemas): core data models and enums`.

### Task 3: Tolerant JSON utils
**Files:** Create `app/providers/json_utils.py`; Test `tests/test_json_utils.py`.
- [ ] Step 1: Failing tests: `extract_json('prefix {"a":1} suffix') == {"a":1}`;
  handles ```json fenced blocks; returns `{}` (or raises `JSONParseError`) on garbage;
  strips trailing commas.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement `extract_json(text) -> dict`: find first `{`…matching `}` (brace
  counting, ignore braces inside strings), strip ```json fences, `json.loads`, on failure
  remove trailing commas and retry; raise `JSONParseError` if still invalid.
- [ ] Step 4: Run → PASS.
- [ ] Step 5: Commit `feat(providers): tolerant JSON extraction`.

### Task 4: Provider base Protocols
**Files:** Create `app/providers/llm/base.py`, `search/base.py`, `crawl/base.py` (+ `__init__.py`s).
- [ ] Step 1: Implement the three Protocols exactly as in "Provider Interfaces" above.
- [ ] Step 2: `uv run python -c "from app.providers.llm.base import LLMProvider; print('ok')"` → ok.
- [ ] Step 3: Commit `feat(providers): provider interfaces (llm/search/crawl)`.

### Task 5: Mock providers (deterministic)
**Files:** Create `app/providers/llm/mock.py`, `search/mock.py`, `crawl/mock.py`;
Test `tests/test_mock_providers.py`.
- [ ] Step 1: Failing tests:
  - `MockSearchProvider().search("brand X", 5)` → 5 results, urls stable/deterministic,
    each `SearchResult`.
  - `MockCrawlProvider().fetch("https://example.com/a")` → `PageContent.ok`, non-empty `text`
    containing the URL (deterministic).
  - `await MockLLMProvider().complete(msgs, tag="plan", json=True)` → JSON string that
    `extract_json` parses into a dict with `brief` + `sections` (≥1).
  - `MockLLMProvider().stream(msgs, tag="report")` → yields ≥1 chunk; joined text contains
    `# ` heading and `## Sources`.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement mocks:
  - Search: `for i in range(k): url=f"https://example.com/{slug(query)}/{i}"`, title/snippet
    reference the query.
  - Crawl: return deterministic paragraph text embedding the url + a few sentences.
  - LLM: switch on `tag`:
    - `plan` → `json.dumps({"brief":{"objective":<from last user msg>,"key_questions":[...]},
      "sections":[{"id":"s1","title":...,"goal":...,"queries":[...]}, {"id":"s2",...}]})`
    - `summarize` → `"Summary: <first 160 chars of page text>"`
    - `reflect` → `json.dumps({"need_more": false, "queries": []})`
    - `compress` → `"### <goal>\n- key point [1]\n- key point [2]"`
    - `report` (`complete`) → a full markdown doc; `stream` yields it in ~40-char chunks.
- [ ] Step 4: Run → PASS.
- [ ] Step 5: Commit `feat(providers): deterministic mock llm/search/crawl`.

### Task 6: SourceRegistry
**Files:** Create `app/core/sources.py`, `app/core/__init__.py`; Test `tests/test_sources.py`.
- [ ] Step 1: Failing tests: `add()` returns `Source` with incrementing `id` starting at 1;
  adding the same URL twice returns the **same** id (dedup); `all()` returns list in id order.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement `SourceRegistry` with an internal `dict[url,int]` + `list[Source]`,
  thread-safe enough for asyncio (use `asyncio.Lock` around `add`).
- [ ] Step 4: Run → PASS.
- [ ] Step 5: Commit `feat(core): source registry with stable citation ids`.

### Task 7: Events
**Files:** Create `app/core/events.py`; Test include in `tests/test_engine_e2e.py` later.
- [ ] Step 1: Implement `Sink = Callable[[Event], Awaitable[None]]`; `ListSink` (collects to a
  list); `EventEmitter(run_id, sink)` with `async emit(type, data)` assigning monotonic `seq`
  from 0 and `ts` via `time.time()*1000`. Provide `now_ms()` helper.
- [ ] Step 2: Quick test: emit two events via `ListSink`, assert `seq` 0 then 1.
- [ ] Step 3: Run → PASS. Commit `feat(core): event emitter + sinks`.

### Task 8: Prompts
**Files:** Create `app/prompts/templates.py`, `planner.py`, `researcher.py`, `synthesizer.py`,
`__init__.py`.
- [ ] Step 1: `templates.py`: `TEMPLATES: dict[str, Template]` for `deep_research`,
  `competitor_brand`, `market_landscape` (id/name/description/audience + a `report_outline`
  string). `language_directive(lang)` → `"Write the report in Thai."` / `"...in English."`.
- [ ] Step 2: `planner.py`: `build_planner_messages(query, config, template)` → system+user
  messages instructing a JSON plan (brief + 3–6 sections, each with goal + 2–4 queries),
  honoring `max_sections` and the template outline.
- [ ] Step 3: `researcher.py`: `summarize_messages(goal, page)`, `reflect_messages(goal, notes)`
  (asks for JSON `{need_more, queries}`), `compress_messages(goal, notes)`.
- [ ] Step 4: `synthesizer.py`: `build_report_messages(brief, sections, sources, config)` →
  instruct a detailed Markdown report with `#` title, `##` sections per outline, inline
  citations `[n]`, and a final `## Sources` list; include the language directive.
- [ ] Step 5: Smoke test: each builder returns a non-empty `list[dict]` with roles.
  Commit `feat(prompts): planner/researcher/synthesizer/templates with i18n`.

### Task 9: Planner
**Files:** Create `app/core/planner.py`; Test `tests/test_planner.py`.
- [ ] Step 1: Failing test: `Planner(mock_llm).plan("Analyze brand X", RunConfig())` returns a
  `Plan` with ≥2 `PlanSection`s, each with non-empty `goal` and ≥1 query; section ids unique.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement: build messages → `llm.complete(tag="plan", json=True)` →
  `extract_json` → validate into `Plan`; on validation error, one repair retry with an
  "output valid JSON only" nudge; clamp to `config.max_sections`; assign `s1..sn` ids if missing.
- [ ] Step 4: Run → PASS. Commit `feat(core): planner`.

### Task 10: Researcher
**Files:** Create `app/core/researcher.py`; Test `tests/test_researcher.py`.
- [ ] Step 1: Failing test: run `Researcher.research(section, deps...)` with mocks + a
  `ListSink`; assert events include `section_start`, ≥1 `search`, ≥1 `source`, ≥1 `note`,
  ending `section_done`; returned summary non-empty; sources registered.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement the bounded loop described in the spec (search → fetch top
  `fetch_per_query` concurrently under `fetch_concurrency` semaphore → summarize each vs goal →
  note with `[id]` → reflect (stop unless `need_more` and new queries) up to
  `max_iters_per_section` → compress). Emit events at each step. Dedup sources via registry.
- [ ] Step 4: Run → PASS. Commit `feat(core): per-section research loop`.

### Task 11: Synthesizer
**Files:** Create `app/core/synthesizer.py`; Test `tests/test_synthesizer.py`.
- [ ] Step 1: Failing test: `synthesize(brief, sections, sources, mock_llm, emit)` streams ≥1
  `report_delta`, returns `(markdown, title)`; markdown contains `## Sources` and every source
  id; title non-empty.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement: stream `llm.stream(tag="report")` emitting `report_delta`; join;
  `ensure_sources_section(md, sources)` appends a `## Sources` list `[n] title — url` if absent
  or missing ids; `extract_title(md)` from first `# ` line else `brief.objective`.
- [ ] Step 4: Run → PASS. Commit `feat(core): streamed report synthesizer`.

### Task 12: Engine orchestrator
**Files:** Create `app/core/engine.py`; Test `tests/test_engine_e2e.py`.
- [ ] Step 1: Failing E2E test: build `ResearchEngine` with all mocks; run with a `ListSink`;
  assert event order first `status(planning)` → `plan` → (no `awaiting_plan` when auto) →
  per-section `section_start..section_done` → `status(writing)` → ≥1 `report_delta` → `report`
  → `done`; final `report` markdown non-empty; `done.data["source_count"] >= 1`; all events
  have increasing `seq`.
- [ ] Step 2: Run → FAIL.
- [ ] Step 3: Implement `ResearchEngine.run(run_id, query, config, sink, approval=None)`:
  emit statuses; plan; if `require_plan_approval` and `approval` given, emit `awaiting_plan`
  and `sections = await approval(plan)`; else use plan sections; research sections in parallel
  under `section_concurrency`; synthesize; emit `report` + `done`; wrap in try/except emitting
  `error`. Shared `SourceRegistry`, shared `EventEmitter`.
- [ ] Step 4: Run → PASS.
- [ ] Step 5: `uv run pytest -q` (all) → PASS. Commit `feat(core): research engine orchestrator`.

### Task 13: Config + CLI
**Files:** Create `app/config.py`, `app/cli.py`; Test `tests/test_engine_e2e.py` (add CLI smoke).
- [ ] Step 1: `config.py`: `load_run_config(**overrides) -> RunConfig` merging env
  (`AUTOFLOW_LLM_PROVIDER`, etc.) + overrides.
- [ ] Step 2: `cli.py`: `argparse` subcommand `research "<query>" [--template --lang --llm
  --search --crawl --approve/--no-approve --json-events]`; builds config; runs engine with a
  sink that pretty-prints events (and dumps JSON lines if `--json-events`); prints the final
  report; exit 0. `main()` wires `asyncio.run`. Print a footer credit line from `__about__`
  (`APP_NAME vVERSION · MIT · by Narenrit (captainkie) & Claude`). Add an `about` subcommand
  that prints `AUTHORS`/`LICENSE`/`ACKNOWLEDGEMENTS`.
- [ ] Step 3: Failing test: invoke CLI via `subprocess`/`runpy` with `--llm mock --search mock
  --crawl mock` on a sample query; assert exit 0 and stdout contains `## Sources`.
- [ ] Step 4: Run → PASS. Manual check:
  `uv run autoflow research "Analyze competitor brand: ExampleCo" --lang en` → prints report.
- [ ] Step 5: Commit `feat(cli): run research end-to-end with mock providers`.

### Task 14: Real provider adapters (thin; unit-light)
**Files:** Create `llm/litellm_provider.py`, `llm/registry.py`, `search/{tavily,serper,exa,
duckduckgo}.py`, `search/registry.py`, `crawl/{jina,trafilatura_provider}.py`, `crawl/registry.py`.
- [ ] Step 1: `litellm_provider.py`: wrap `litellm.acompletion` (map provider+model+key →
  litellm model string; `stream=True` path yields `chunk.choices[0].delta.content`). Reads key
  from an injected callable `get_key(provider)` (vault comes later; for now env).
- [ ] Step 2: Search adapters via `httpx.AsyncClient` (shared): Tavily `POST
  https://api.tavily.com/search`; Serper `POST https://google.serper.dev/search`; Exa `POST
  https://api.exa.ai/search`; DuckDuckGo via `ddgs` (`DDGS().text(query, max_results=k)`,
  keyless). Each maps to `list[SearchResult]`.
- [ ] Step 3: Crawl: Jina `GET https://r.jina.ai/<url>` → markdown text; trafilatura optional
  (`trafilatura.extract`) behind a try-import guard that raises a clear error if the extra
  isn't installed.
- [ ] Step 4: Registries: `get_llm_provider(config, get_key)`, `get_search_provider(...)`,
  `get_crawl_provider(...)` returning `mock` or the named adapter; unknown name → `ValueError`.
- [ ] Step 5: Tests: registry returns correct type for `"mock"`; each adapter maps a **canned
  JSON payload** (monkeypatched httpx transport) to `SearchResult`s — no live network. Commit
  `feat(providers): real llm/search/crawl adapters + registries`.

### Task 15: Lint, types, docs, README (backend), open PR
**Files:** `backend/README.md`; ensure `ruff`/tests pass.
- [ ] Step 1: `uv run ruff check . && uv run ruff format --check .` → clean (fix issues).
- [ ] Step 2: `uv run pytest -q` → all pass; note count.
- [ ] Step 3: Write `backend/README.md`: what the engine is, how to install (`uv sync`), run
  tests, and the CLI quickstart (mock mode) + how to point at real providers via env.
- [ ] Step 4: Update root `docs/` if any interface drifted from `API_CONTRACT.md`.
- [ ] Step 5: Commit `docs(backend): engine README + quickstart`; push branch;
  `gh pr create` with a summary + test evidence; request review (self-review via
  code-reviewer agent before merge).

---

## Self-Review (done before execution)

- **Spec coverage:** Engine loop (§4), providers incl. mocks (§5), i18n directive (§4/§8),
  concurrency caps (§4), CLI (§11 build order #1), offline E2E (success criteria) — all mapped
  to tasks 5–14. Security/DB/API/auth/frontend are explicitly out of M1 (later milestones).
- **Placeholder scan:** none — each task names exact files, interfaces, and test assertions.
- **Type consistency:** `LLMProvider.complete(tag=…, json=…)`, `SearchProvider.search(query,k)`,
  `CrawlProvider.fetch(url)`, `EventEmitter.emit(type,data)`, `SourceRegistry.add(...)`,
  `Planner.plan`, `Researcher.research`, `Synthesizer.synthesize`, `ResearchEngine.run` are
  used consistently across tasks 4–14.
```
