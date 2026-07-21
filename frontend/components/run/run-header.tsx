"use client";

import Link from "next/link";
import { ArrowLeft, X, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/run/status-badge";
import { StageStepper } from "@/components/run/stage-stepper";
import type { RunStatus } from "@/lib/types";
import { statusMeta, formatDateTime } from "@/lib/format";
import { templateLabel } from "@/lib/templates";

export function RunHeader({
  query,
  title,
  template,
  status,
  createdAt,
  sourceCount,
  canceling,
  onCancel,
}: {
  query?: string;
  title?: string;
  template?: string;
  status: RunStatus;
  createdAt?: string;
  sourceCount?: number;
  canceling: boolean;
  onCancel: () => void;
}) {
  const live = statusMeta(status).live || status === "awaiting_plan";
  const heading = title || query || "Research run";
  const showQuerySub = !!title && !!query && title !== query;

  return (
    <div className="border-b border-border/70 pb-5">
      <Link
        href="/history"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        All research
      </Link>

      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
        {template && <span className="eyebrow">{templateLabel(template)}</span>}
        {createdAt && (
          <>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-xs text-muted-foreground">
              {formatDateTime(createdAt)}
            </span>
          </>
        )}
      </div>

      <h1 className="mt-1.5 font-display text-2xl font-semibold tracking-tight text-balance sm:text-[1.75rem]">
        {heading}
      </h1>
      {showQuerySub && (
        <p className="mt-1 text-sm text-muted-foreground">{query}</p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <StatusBadge status={status} />
        <div className="hidden h-4 w-px bg-border sm:block" />
        <StageStepper status={status} />
        <div className="ml-auto flex items-center gap-3">
          {typeof sourceCount === "number" && sourceCount > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileText className="size-3.5" />
              {sourceCount} sources
            </span>
          )}
          {live && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={canceling}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="size-3.5" data-icon="inline-start" />
              {canceling ? "Cancelling…" : "Cancel"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
