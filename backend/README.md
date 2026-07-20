# AutoFlow Research — Backend

A provider-agnostic, fully-async **deep-research engine**. Given a query it runs
`plan → parallel per-section research → streamed, cited Markdown report`. The engine
is pure — it depends only on provider *interfaces* and an async event sink — so it
runs entirely offline with deterministic **mock** providers (no API keys) and is
covered end-to-end by tests. This is **Milestone 1**: the engine, providers, mocks,
and a CLI. HTTP/SSE API, SQLite persistence, auth, and the vault arrive in later
milestones.

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
├── config.py             load_run_config() — env (AUTOFLOW_*) + overrides
└── cli.py                `autoflow research ...` / `autoflow about`
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
