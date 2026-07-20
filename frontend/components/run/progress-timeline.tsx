import { Search, Check, Lightbulb } from "lucide-react";

import type { SectionState } from "@/lib/useResearchStream";
import { SourceItem } from "@/components/run/source-item";
import { cn } from "@/lib/utils";

function SectionDot({ status }: { status: SectionState["status"] }) {
  return (
    <span
      className={cn(
        "absolute -left-[1.72rem] top-0.5 flex size-3.5 items-center justify-center rounded-full ring-4 ring-background",
        status === "done" && "bg-primary text-primary-foreground",
        status === "active" && "bg-signal pulse-dot",
        status === "pending" && "border border-border bg-card",
      )}
    >
      {status === "done" && <Check className="size-2" strokeWidth={4} />}
    </span>
  );
}

function SectionBlock({ section }: { section: SectionState }) {
  const hasActivity =
    section.searches.length > 0 ||
    section.sources.length > 0 ||
    section.notes.length > 0;

  return (
    <li className="relative animate-in fade-in slide-in-from-bottom-1 duration-500">
      <SectionDot status={section.status} />
      <div className="pb-1">
        <div className="flex items-baseline justify-between gap-2">
          <h3
            className={cn(
              "font-display text-[0.95rem] font-semibold leading-tight tracking-tight",
              section.status === "pending" && "text-muted-foreground",
            )}
          >
            {section.title || "Untitled section"}
          </h3>
          {section.sources.length > 0 && (
            <span className="shrink-0 text-[0.7rem] tabular-nums text-muted-foreground">
              {section.sources.length} src
            </span>
          )}
        </div>
        {section.goal && (
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {section.goal}
          </p>
        )}

        {section.searches.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {section.searches.map((q, i) => (
              <span
                key={`${q}-${i}`}
                className="inline-flex max-w-full items-center gap-1 rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 text-[0.72rem] text-muted-foreground animate-in fade-in duration-300"
              >
                <Search className="size-2.5 shrink-0 text-primary/70" />
                <span className="truncate">{q}</span>
              </span>
            ))}
          </div>
        )}

        {section.sources.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-1.5">
            {section.sources.map((src) => (
              <SourceItem key={src.id} source={src} compact />
            ))}
          </div>
        )}

        {section.notes.length > 0 && (
          <ul className="mt-2.5 flex flex-col gap-1.5">
            {section.notes.map((note, i) => (
              <li
                key={i}
                className="flex gap-1.5 text-xs leading-relaxed text-muted-foreground animate-in fade-in duration-300"
              >
                <Lightbulb className="mt-0.5 size-3 shrink-0 text-signal" />
                <span className="font-reading italic">{note}</span>
              </li>
            ))}
          </ul>
        )}

        {section.status === "active" && !hasActivity && (
          <div className="mt-2 flex flex-col gap-1.5">
            <div className="shimmer-line h-2.5 w-4/5 rounded-full" />
            <div className="shimmer-line h-2.5 w-2/3 rounded-full" />
          </div>
        )}

        {section.status === "done" && section.summary && (
          <p className="mt-2.5 border-l-2 border-primary/30 pl-2.5 text-xs leading-relaxed text-muted-foreground">
            {section.summary}
          </p>
        )}
      </div>
    </li>
  );
}

export function ProgressTimeline({ sections }: { sections: SectionState[] }) {
  if (sections.length === 0) {
    return (
      <div className="flex flex-col gap-3 py-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex gap-3">
            <span className="mt-1 size-3 shrink-0 rounded-full bg-muted" />
            <div className="flex-1 space-y-1.5">
              <div className="shimmer-line h-3 w-2/3 rounded-full" />
              <div className="shimmer-line h-2.5 w-1/2 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <ol className="relative ml-1 flex flex-col gap-5 border-l border-border/70 pl-6">
      {sections.map((section) => (
        <SectionBlock key={section.id} section={section} />
      ))}
    </ol>
  );
}
