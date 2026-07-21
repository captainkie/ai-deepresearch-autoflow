"use client";

import * as React from "react";
import { ShieldCheck, TriangleAlert } from "lucide-react";

import type { ConfidenceSummary, ContradictionData } from "@/lib/types";
import type { ClaimState } from "@/lib/useResearchStream";
import { cn } from "@/lib/utils";

/** Backend-matching projection of the claim graph into {high, medium, low}. */
export function deriveConfidenceSummary(
  claims: ClaimState[],
  contradictions: ContradictionData[],
): ConfidenceSummary {
  let high = 0;
  let medium = 0;
  let low = 0;
  for (const c of claims) {
    if (c.verdict === "supported") {
      if ((c.source_ids?.length ?? 0) >= 2) high++;
      else medium++;
    } else {
      // unsupported / contradicted / partial / not-yet-verified → low, matching
      // the backend's summarize_confidence.
      low++;
    }
  }
  return { high, medium, low, contradictions: contradictions.length };
}

const LEVELS = [
  {
    key: "high" as const,
    label: "High",
    dot: "bg-emerald-500",
    text: "text-emerald-700 dark:text-emerald-300",
    ring: "ring-emerald-500/25",
  },
  {
    key: "medium" as const,
    label: "Medium",
    dot: "bg-amber-500",
    text: "text-amber-700 dark:text-amber-300",
    ring: "ring-amber-500/25",
  },
  {
    key: "low" as const,
    label: "Low",
    dot: "bg-rose-500",
    text: "text-rose-700 dark:text-rose-300",
    ring: "ring-rose-500/25",
  },
];

/**
 * The trust bar: how many claims the verifier landed at each confidence level,
 * plus a contradiction flag. Rendered above the report so a reader sees how
 * grounded it is before reading it.
 */
export function ConfidenceSummaryBar({
  summary,
  className,
}: {
  summary: ConfidenceSummary;
  className?: string;
}) {
  const total = summary.high + summary.medium + summary.low;
  if (total === 0 && summary.contradictions === 0) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-lg border border-border/70 bg-card/50 px-3 py-2",
        className,
      )}
    >
      <span className="eyebrow inline-flex items-center gap-1.5">
        <ShieldCheck className="size-3.5" />
        Verification
      </span>
      <span className="h-3.5 w-px bg-border" aria-hidden />
      {LEVELS.map((lv) => (
        <span
          key={lv.key}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
            lv.text,
            lv.ring,
          )}
          title={`${summary[lv.key]} ${lv.label.toLowerCase()}-confidence claim(s)`}
        >
          <span className={cn("size-1.5 rounded-full", lv.dot)} aria-hidden />
          {lv.label}
          <span className="tabular-nums">{summary[lv.key]}</span>
        </span>
      ))}
      {summary.contradictions > 0 && (
        <span
          className="inline-flex items-center gap-1.5 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive ring-1 ring-inset ring-destructive/25"
          title={`${summary.contradictions} unresolved contradiction(s) across sources`}
        >
          <TriangleAlert className="size-3" aria-hidden />
          {summary.contradictions}{" "}
          {summary.contradictions === 1 ? "contradiction" : "contradictions"}
        </span>
      )}
    </div>
  );
}
