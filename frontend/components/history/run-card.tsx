import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { StatusBadge } from "@/components/run/status-badge";
import type { RunSummary } from "@/lib/types";
import { formatRelative } from "@/lib/format";

export function RunCard({ run }: { run: RunSummary }) {
  const heading = run.title || run.query || "Untitled research";

  return (
    <Link
      href={`/runs/${run.run_id}`}
      className="group relative flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)] hover:ring-primary/30"
    >
      <div className="flex items-start justify-between gap-3">
        <StatusBadge status={run.status} />
        <ArrowUpRight className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>

      <h3 className="font-display text-[1.05rem] leading-snug font-semibold tracking-tight text-balance line-clamp-2">
        {heading}
      </h3>

      {run.title && run.query && run.title !== run.query && (
        <p className="-mt-1.5 line-clamp-1 text-xs text-muted-foreground">
          {run.query}
        </p>
      )}

      <div className="mt-auto flex items-center gap-2 pt-1 text-xs text-muted-foreground">
        {run.template && (
          <span className="rounded-full bg-secondary/50 px-2 py-0.5 font-medium capitalize">
            {run.template.replace(/_/g, " ")}
          </span>
        )}
        <span className="text-muted-foreground/40">·</span>
        <span>{formatRelative(run.created_at)}</span>
      </div>
    </Link>
  );
}
