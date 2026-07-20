import type { RunStatus } from "./types";

/** Extract a bare hostname (no www.) from a URL, tolerant of bad input. */
export function domainFromUrl(url: string): string {
  try {
    const host = new URL(url).hostname;
    return host.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] ?? url;
  }
}

/** Favicon endpoint for a source URL (DuckDuckGo icon proxy). */
export function faviconUrl(url: string): string | null {
  const domain = domainFromUrl(url);
  if (!domain) return null;
  return `https://icons.duckduckgo.com/ip3/${domain}.ico`;
}

/** Human, absolute date — e.g. "20 Jul 2026, 14:32". */
export function formatDateTime(value?: string | number): string {
  if (value === undefined || value === null || value === "") return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Compact relative time — e.g. "3h ago", "just now". */
export function formatRelative(value?: string | number): string {
  if (value === undefined || value === null || value === "") return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const diff = Date.now() - d.getTime();
  const abs = Math.abs(diff);
  const mins = Math.round(abs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDateTime(value);
}

/** URL-safe slug for anchoring report headings. */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export type StatusTone = "neutral" | "active" | "success" | "danger" | "pending";

export type StatusMeta = {
  label: string;
  tone: StatusTone;
  /** True while the run is actively doing work (drives the live pulse). */
  live: boolean;
};

const STATUS_MAP: Record<string, StatusMeta> = {
  queued: { label: "Queued", tone: "pending", live: true },
  planning: { label: "Planning", tone: "active", live: true },
  awaiting_plan: { label: "Awaiting approval", tone: "pending", live: false },
  researching: { label: "Researching", tone: "active", live: true },
  writing: { label: "Writing report", tone: "active", live: true },
  done: { label: "Complete", tone: "success", live: false },
  error: { label: "Error", tone: "danger", live: false },
};

export function statusMeta(status: RunStatus): StatusMeta {
  return (
    STATUS_MAP[status] ?? {
      label: status ? String(status) : "Unknown",
      tone: "neutral",
      live: false,
    }
  );
}

/** Ordered pipeline used by the stage indicator. */
export const STAGE_ORDER = [
  "queued",
  "planning",
  "awaiting_plan",
  "researching",
  "writing",
  "done",
] as const;
