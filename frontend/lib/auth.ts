/**
 * Client-side session state.
 *
 * The access token lives in memory only (never localStorage) — it's short-lived
 * and re-minted from the httpOnly refresh cookie via `POST /api/v1/auth/refresh`.
 * `refreshAccessToken` is single-flight so a burst of 401s triggers one refresh.
 */
import { API_BASE } from "./api";

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let unauthenticatedHandler: (() => void) | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Registered by the AuthProvider so a hard 401 can bounce the user to /login. */
export function setUnauthenticatedHandler(handler: (() => void) | null): void {
  unauthenticatedHandler = handler;
}

export function notifyUnauthenticated(): void {
  accessToken = null;
  unauthenticatedHandler?.();
}

export function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const run = (async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });
      if (!res.ok) {
        accessToken = null;
        return false;
      }
      const data = (await res.json()) as { access_token?: string };
      accessToken = data.access_token ?? null;
      return accessToken !== null;
    } catch {
      accessToken = null;
      return false;
    }
  })();
  refreshInFlight = run;
  void run.finally(() => {
    if (refreshInFlight === run) refreshInFlight = null;
  });
  return run;
}
