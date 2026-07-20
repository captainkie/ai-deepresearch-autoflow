# AutoFlow Research — API Contract

Shared contract between the Python (FastAPI) backend and the Next.js frontend.
Base URL (dev): `http://localhost:8000`. All JSON. SSE endpoints use `text/event-stream`.

## Concepts

- **Run** — one research job: `query` + `template` + provider `config`, moving through
  stages `queued → planning → awaiting_plan → researching → writing → done` (or `error`).
- **Plan** — a research brief plus an ordered list of **sections** to investigate. When
  `require_plan_approval` is set, the run pauses at `awaiting_plan` until the user approves
  or edits the plan (human-in-the-loop, deer-flow style).
- **Report** — the final Markdown document with inline citations `[n]` and a Sources list.

## REST endpoints

### `GET /api/health`
`200 → { "status": "ok", "version": "..." }`

### `GET /api/templates`
List research templates. `200 → { "templates": Template[] }`
```ts
type Template = {
  id: string; name: string; description: string; audience: string;
  // Engine v2 (additive, optional — list view needs only the fields above):
  entity_mode?: boolean;                                          // template compares entities (e.g. brands)
  entity_schema?: { key: string; label: string; type: "text" | "list" }[];
  verification_level?: "off" | "light" | "strict";
}
```

### `GET /api/config`
Current provider config + which providers are available (have credentials).
```ts
type ConfigResponse = {
  llm: { provider: string; model: string; available: string[] };
  search: { provider: string; available: string[] };
  require_plan_approval: boolean;
}
```

### `POST /api/config`
Update runtime config (does not persist secrets to disk; keys come from env).
Body: `Partial<{ llm_provider, llm_model, search_provider, require_plan_approval }>` → `ConfigResponse`.

### `POST /api/runs`
Create a run. Body:
```ts
type CreateRun = {
  query: string;
  template?: string;               // default "deep_research"
  require_plan_approval?: boolean; // default from config
  config?: { llm_provider?: string; llm_model?: string; search_provider?: string };
}
```
`201 → { "run_id": string }`

### `GET /api/runs`
`200 → { "runs": RunSummary[] }` (newest first)
```ts
type RunSummary = { run_id: string; query: string; template: string; status: string; created_at: string; title?: string }
```

### `GET /api/runs/{run_id}`
`200 → RunDetail` — full run incl. `plan`, `sections`, `report` (Markdown), `sources`, `status`.

### `POST /api/runs/{run_id}/plan`
Approve or replace the plan (only valid while `awaiting_plan`).
Body: `{ "sections": PlanSection[] }` (edited) or `{ "approve": true }` to accept as-is.
`200 → { "ok": true }` — resumes the run; new events flow on the open SSE stream.

### `POST /api/runs/{run_id}/cancel`
`200 → { "ok": true }`

## SSE endpoint

### `GET /api/runs/{run_id}/stream`  (`text/event-stream`)
Opens the live event stream for a run. The server starts (or resumes) execution and emits
events until `done` or `error`. If the client reconnects, the server replays buffered events
first (each event has a monotonic `seq`), so the UI can rebuild state.

Each SSE `data:` line is one JSON `Event`:
```ts
type Event = {
  seq: number;
  run_id: string;
  ts: number;              // epoch ms
  type: EventType;
  data: unknown;           // shape depends on type (below)
}

type EventType =
  | "status"        // { stage: string; message: string }
  | "plan"          // { brief: string; sections: PlanSection[] }
  | "awaiting_plan" // {} — paused for human approval
  | "search"        // { section_id: string; query: string }
  | "source"        // { section_id: string; source: Source }
  | "claim"         // { claim_id: string; section_id: string; text: string; entity?: string; attribute?: string; source_ids: number[]; quote?: string }  (Engine v2)
  | "verification"  // { claim_id: string; verdict: "supported"|"partial"|"unsupported"|"contradicted"; confidence: number; rationale?: string }  (Engine v2)
  | "contradiction" // { id: string; entity?: string; attribute?: string; claim_ids: [string, string]; note?: string }  (Engine v2)
  | "note"          // { section_id: string; content: string }  (a compressed finding / reflection)
  | "section_start" // { section_id: string; title: string }
  | "section_done"  // { section_id: string; summary: string; source_count: number }
  | "report_delta"  // { text: string }  (streamed final-report tokens)
  | "report"        // { markdown: string; title: string; confidence_summary?: ConfidenceSummary }  (full final report)
  | "error"         // { message: string }
  | "done"          // { title: string; source_count: number; confidence_summary?: ConfidenceSummary }

type ConfidenceSummary = { high: number; medium: number; low: number; contradictions: number }  // Engine v2

type PlanSection = { id: string; title: string; goal: string; queries: string[] }
type Source = { id: number; title: string; url: string; snippet: string; section_id?: string }
```

### Event ordering (happy path)
```
status(planning) → plan → [awaiting_plan → (POST /plan)] →
  for each section: section_start → search* → source* → claim* → verification* → (contradiction*) → note* → section_done
status(writing) → report_delta* → report → done

(Engine v2 adds the claim/verification/contradiction events; on older/`verification_level:off`
runs they simply don't appear, and clients de-dupe by `seq` as before.)
```
