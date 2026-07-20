/**
 * AutoFlow Research — typed REST client.
 *
 * Implements the endpoints from `docs/API_CONTRACT.md`. Every call is a thin,
 * typed wrapper around `fetch`. Callers are expected to try/catch so the UI can
 * degrade gracefully when the backend is offline (empty/skeleton states).
 */
import type {
  ConfigResponse,
  ConfigUpdate,
  CreateRun,
  RunDetail,
  RunSummary,
  Template,
} from "./types";

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = RequestInit & { parseJson?: boolean };

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { parseJson = true, headers, ...rest } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    // Research data is always live; never serve a cached run.
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    ...rest,
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") message = body.detail;
      else if (body && typeof body.message === "string") message = body.message;
    } catch {
      // non-JSON error body — keep the default message
    }
    throw new ApiError(message, res.status);
  }

  if (!parseJson) return undefined as T;
  return (await res.json()) as T;
}

// --- Health -------------------------------------------------------------
export function getHealth() {
  return request<{ status: string; version: string }>("/api/health");
}

// --- Templates ----------------------------------------------------------
export async function getTemplates(): Promise<Template[]> {
  const data = await request<{ templates: Template[] }>("/api/templates");
  return data.templates ?? [];
}

// --- Config -------------------------------------------------------------
export function getConfig(): Promise<ConfigResponse> {
  return request<ConfigResponse>("/api/config");
}

export function updateConfig(body: ConfigUpdate): Promise<ConfigResponse> {
  return request<ConfigResponse>("/api/config", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- Runs ---------------------------------------------------------------
export function createRun(body: CreateRun): Promise<{ run_id: string }> {
  return request<{ run_id: string }>("/api/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listRuns(): Promise<RunSummary[]> {
  const data = await request<{ runs: RunSummary[] }>("/api/runs");
  return data.runs ?? [];
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`);
}

export function submitPlan(
  runId: string,
  body: { sections: import("./types").PlanSection[] } | { approve: true },
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/runs/${encodeURIComponent(runId)}/plan`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function cancelRun(runId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
}

// --- SSE ----------------------------------------------------------------
export function streamUrl(runId: string): string {
  return `${API_BASE}/api/runs/${encodeURIComponent(runId)}/stream`;
}
