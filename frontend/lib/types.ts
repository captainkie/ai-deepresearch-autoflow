/**
 * AutoFlow Research — shared types.
 *
 * Mirrors `docs/API_CONTRACT.md` verbatim. Keep this file in lock-step with the
 * backend contract; it is the single source of truth for the typed API client
 * and the SSE stream hook.
 */

// ---------------------------------------------------------------------------
// Templates & config
// ---------------------------------------------------------------------------

export type Template = {
  id: string;
  name: string;
  description: string;
  audience: string;
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type Role = "superadmin" | "admin" | "member" | "viewer";

export type User = {
  id: string;
  email: string;
  name: string;
  role: Role;
  disabled: boolean;
  created_at: string;
};

export type SetupStatus = { needs_setup: boolean };

export type Session = { user: User; access_token: string };

// ---------------------------------------------------------------------------
// Admin — credentials, audit, about
// ---------------------------------------------------------------------------

export type Credential = {
  id: string;
  provider: string;
  label: string;
  masked_hint: string;
  status: "active" | "revoked";
  key_version: number;
  created_by: string | null;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
};

export type AuditEntry = {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  meta_json: string | null;
  created_at: string;
};

export type Author = { name: string; handle?: string; role?: string };
export type Acknowledgement = {
  name: string;
  url?: string;
  license?: string;
  description?: string;
};
export type About = {
  app: string;
  version: string;
  license: string;
  authors: Author[];
  acknowledgements: Acknowledgement[];
};

export type ConfigResponse = {
  llm: { provider: string; model: string; available: string[] };
  search: { provider: string; available: string[] };
  require_plan_approval: boolean;
};

export type ConfigUpdate = Partial<{
  llm_provider: string;
  llm_model: string;
  search_provider: string;
  require_plan_approval: boolean;
}>;

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export type CreateRun = {
  query: string;
  template?: string; // default "deep_research"
  language?: string; // "en" | "th" — default from server config
  require_plan_approval?: boolean; // default from config
  config?: {
    llm_provider?: string;
    llm_model?: string;
    search_provider?: string;
  };
};

export type RunStatus =
  | "queued"
  | "planning"
  | "awaiting_plan"
  | "researching"
  | "writing"
  | "done"
  | "error"
  | "cancelled"
  | string;

export type RunSummary = {
  run_id: string;
  query: string;
  template: string;
  status: RunStatus;
  created_at: string;
  title?: string;
};

export type PlanSection = {
  id: string;
  title: string;
  goal: string;
  queries: string[];
};

export type Source = {
  id: number;
  title: string;
  url: string;
  snippet: string;
  section_id?: string;
};

export type Plan = {
  brief: string;
  sections: PlanSection[];
};

export type RunDetail = {
  run_id: string;
  query: string;
  template: string;
  status: RunStatus;
  title?: string;
  created_at?: string;
  plan?: Plan | null;
  sections?: PlanSection[];
  report?: string; // Markdown
  sources?: Source[];
};

// ---------------------------------------------------------------------------
// SSE events
// ---------------------------------------------------------------------------

export type EventType =
  | "status"
  | "plan"
  | "awaiting_plan"
  | "search"
  | "source"
  | "note"
  | "section_start"
  | "section_done"
  | "report_delta"
  | "report"
  | "error"
  | "done";

export type ResearchEvent = {
  seq: number;
  run_id: string;
  ts: number; // epoch ms
  type: EventType;
  data: unknown; // shape depends on type — narrowed below
};

// Per-type payload shapes (from the contract). Used to narrow `event.data`.
export type StatusData = { stage: RunStatus; message: string };
export type PlanData = { brief: string; sections: PlanSection[] };
export type AwaitingPlanData = Record<string, never>;
export type SearchData = { section_id: string; query: string };
export type SourceData = { section_id: string; source: Source };
export type NoteData = { section_id: string; content: string };
export type SectionStartData = { section_id: string; title: string };
export type SectionDoneData = {
  section_id: string;
  summary: string;
  source_count: number;
};
export type ReportDeltaData = { text: string };
export type ReportData = { markdown: string; title: string };
export type ErrorData = { message: string };
export type DoneData = { title: string; source_count: number };
