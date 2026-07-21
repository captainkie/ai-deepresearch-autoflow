/**
 * AutoFlow Research — typed REST client.
 *
 * Implements the endpoints from `docs/API_CONTRACT.md`. Requests carry the
 * in-memory access token as `Authorization: Bearer` and always include cookies
 * (for the refresh flow). On a 401 the client transparently refreshes the access
 * token once and retries; if that fails it notifies the AuthProvider.
 */
import {
  getAccessToken,
  notifyUnauthenticated,
  refreshAccessToken,
  setAccessToken,
} from "./auth";
import type {
  About,
  AuditEntry,
  ConfigResponse,
  ConfigUpdate,
  CreateRun,
  Credential,
  Role,
  RunDetail,
  RunSummary,
  Session,
  SetupStatus,
  Template,
  User,
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

// Paths that manage auth themselves — never try to refresh-and-retry on their 401.
function isAuthPath(path: string): boolean {
  return path.startsWith("/api/v1/auth/") || path.startsWith("/api/v1/setup");
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { parseJson = true, headers, ...rest } = opts;

  const send = () => {
    const token = getAccessToken();
    return fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      ...rest,
    });
  };

  let res = await send();

  if (res.status === 401 && !isAuthPath(path)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      res = await send();
    } else {
      notifyUnauthenticated();
    }
  }

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
  return request<{ status: string; version: string }>("/api/v1/health");
}

// --- Auth & setup -------------------------------------------------------
export function getSetupStatus(): Promise<SetupStatus> {
  return request<SetupStatus>("/api/v1/setup/status");
}

export async function runSetup(body: {
  email: string;
  name: string;
  password: string;
}): Promise<Session> {
  const data = await request<Session>("/api/v1/setup", {
    method: "POST",
    body: JSON.stringify(body),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function login(email: string, password: string): Promise<Session> {
  const data = await request<Session>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function register(body: {
  email: string;
  name: string;
  password: string;
}): Promise<Session> {
  const data = await request<Session>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await request<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

export function getMe(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

export async function googleStartUrl(): Promise<string> {
  const data = await request<{ auth_url: string }>("/api/v1/auth/google/start");
  return data.auth_url;
}

// --- Templates ----------------------------------------------------------
export async function getTemplates(): Promise<Template[]> {
  const data = await request<{ templates: Template[] }>("/api/v1/templates");
  return data.templates ?? [];
}

// --- Config -------------------------------------------------------------
export function getConfig(): Promise<ConfigResponse> {
  return request<ConfigResponse>("/api/v1/config");
}

export function updateConfig(body: ConfigUpdate): Promise<ConfigResponse> {
  return request<ConfigResponse>("/api/v1/config", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- Runs ---------------------------------------------------------------
export function createRun(body: CreateRun): Promise<{ run_id: string }> {
  return request<{ run_id: string }>("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listRuns(): Promise<RunSummary[]> {
  const data = await request<{ runs: RunSummary[] }>("/api/v1/runs");
  return data.runs ?? [];
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export function submitPlan(
  runId: string,
  body: { sections: import("./types").PlanSection[] } | { approve: true },
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/runs/${encodeURIComponent(runId)}/plan`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function cancelRun(runId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
}

// --- Admin: users -------------------------------------------------------
export async function listUsers(): Promise<User[]> {
  const data = await request<{ users: User[] }>("/api/v1/admin/users");
  return data.users ?? [];
}

export function updateUser(
  userId: string,
  body: { role?: Role; disabled?: boolean },
): Promise<User> {
  return request<User>(`/api/v1/admin/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// --- Admin: credentials -------------------------------------------------
export async function listCredentials(): Promise<Credential[]> {
  const data = await request<{ credentials: Credential[] }>("/api/v1/admin/credentials");
  return data.credentials ?? [];
}

export function createCredential(body: {
  provider: string;
  label: string;
  secret: string;
  expires_at?: string | null;
}): Promise<Credential> {
  return request<Credential>("/api/v1/admin/credentials", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function revokeCredential(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/admin/credentials/${encodeURIComponent(id)}/revoke`,
    { method: "POST" },
  );
}

export function rotateMasterKey(
  newMasterKey: string,
): Promise<{ ok: boolean; key_version: number }> {
  return request<{ ok: boolean; key_version: number }>("/api/v1/admin/credentials/rotate", {
    method: "POST",
    body: JSON.stringify({ new_master_key: newMasterKey }),
  });
}

// --- Admin: audit -------------------------------------------------------
export async function listAudit(limit = 100): Promise<AuditEntry[]> {
  const data = await request<{ audit: AuditEntry[] }>(`/api/v1/admin/audit?limit=${limit}`);
  return data.audit ?? [];
}

// --- About --------------------------------------------------------------
export function getAbout(): Promise<About> {
  return request<About>("/api/v1/about");
}

// --- SSE ----------------------------------------------------------------
export function streamUrl(runId: string): string {
  return `${API_BASE}/api/v1/runs/${encodeURIComponent(runId)}/stream`;
}
