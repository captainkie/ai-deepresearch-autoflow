"use client";

import * as React from "react";
import {
  Check,
  Plus,
  X,
  RotateCcw,
  Loader2,
  Pencil,
  ClipboardList,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { PlanSection } from "@/lib/types";

type EditableSection = {
  id: string;
  title: string;
  goal: string;
  queries: string[];
};

function clone(sections: PlanSection[]): EditableSection[] {
  return sections.map((s) => ({
    id: s.id,
    title: s.title ?? "",
    goal: s.goal ?? "",
    queries: [...(s.queries ?? [])],
  }));
}

export function PlanReviewCard({
  brief,
  sections,
  approving,
  onApprove,
}: {
  brief?: string;
  sections: PlanSection[];
  approving: boolean;
  onApprove: (sections?: PlanSection[]) => void | Promise<void>;
}) {
  const initial = React.useMemo(() => clone(sections), [sections]);
  const [draft, setDraft] = React.useState<EditableSection[]>(initial);

  // Re-seed if the incoming plan changes and the user hasn't edited yet.
  const signature = React.useMemo(() => JSON.stringify(initial), [initial]);
  const dirty = React.useMemo(
    () => JSON.stringify(draft) !== signature,
    [draft, signature],
  );
  const seededFor = React.useRef(signature);
  React.useEffect(() => {
    if (seededFor.current !== signature) {
      seededFor.current = signature;
      setDraft(clone(sections));
    }
  }, [signature, sections]);

  function updateSection(id: string, patch: Partial<EditableSection>) {
    setDraft((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    );
  }
  function updateQuery(id: string, idx: number, value: string) {
    setDraft((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, queries: s.queries.map((q, i) => (i === idx ? value : q)) }
          : s,
      ),
    );
  }
  function addQuery(id: string) {
    setDraft((prev) =>
      prev.map((s) => (s.id === id ? { ...s, queries: [...s.queries, ""] } : s)),
    );
  }
  function removeQuery(id: string, idx: number) {
    setDraft((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, queries: s.queries.filter((_, i) => i !== idx) }
          : s,
      ),
    );
  }
  function removeSection(id: string) {
    setDraft((prev) => prev.filter((s) => s.id !== id));
  }
  function addSection() {
    setDraft((prev) => [
      ...prev,
      {
        id: `custom-${Date.now().toString(36)}-${prev.length}`,
        title: "",
        goal: "",
        queries: [""],
      },
    ]);
  }

  function handleApprove() {
    if (approving) return;
    if (!dirty) {
      onApprove();
      return;
    }
    const cleaned: PlanSection[] = draft
      .filter((s) => s.title.trim())
      .map((s) => ({
        id: s.id,
        title: s.title.trim(),
        goal: s.goal.trim(),
        queries: s.queries.map((q) => q.trim()).filter(Boolean),
      }));
    onApprove(cleaned);
  }

  return (
    <section className="overflow-hidden rounded-2xl bg-card shadow-[var(--shadow-soft)] ring-1 ring-primary/20">
      <div className="rule-accent h-1 w-full" />
      <div className="p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <ClipboardList className="size-[1.15rem]" />
          </span>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-display text-xl font-semibold tracking-tight">
                Review the research plan
              </h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-signal/15 px-2 py-0.5 text-[0.7rem] font-medium text-[color-mix(in_oklch,var(--signal),var(--foreground)_45%)]">
                <Pencil className="size-2.5" /> Editable
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Tune the sections and search queries below, or approve as-is.
              Research starts as soon as you confirm.
            </p>
          </div>
        </div>

        {brief && (
          <div className="mt-4 rounded-xl border border-border/70 bg-background/50 p-3.5">
            <p className="eyebrow mb-1">Brief</p>
            <p className="font-reading text-[0.95rem] leading-relaxed text-foreground/90">
              {brief}
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3">
          {draft.map((section, i) => (
            <div
              key={section.id}
              className="group/section rounded-xl border border-border/70 bg-background/40 p-3.5 transition-colors focus-within:border-primary/40"
            >
              <div className="flex items-start gap-2.5">
                <span className="mt-1 font-display text-lg font-semibold tabular-nums text-muted-foreground/50">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="flex-1 space-y-2">
                  <Input
                    aria-label={`Section ${i + 1} title`}
                    value={section.title}
                    onChange={(e) =>
                      updateSection(section.id, { title: e.target.value })
                    }
                    placeholder="Section title"
                    className="h-8 border-0 bg-transparent px-0 font-display text-base font-semibold tracking-tight shadow-none focus-visible:ring-0 dark:bg-transparent"
                  />
                  <Textarea
                    aria-label={`Section ${i + 1} goal`}
                    value={section.goal}
                    onChange={(e) =>
                      updateSection(section.id, { goal: e.target.value })
                    }
                    placeholder="What should this section find out?"
                    className="min-h-0 resize-none border-0 bg-transparent px-0 py-0 text-sm text-muted-foreground shadow-none focus-visible:ring-0 dark:bg-transparent field-sizing-content"
                  />

                  <div className="flex flex-col gap-1.5 pt-1">
                    {section.queries.map((q, qi) => (
                      <div key={qi} className="flex items-center gap-1.5">
                        <span className="text-muted-foreground/50">
                          <SearchGlyph />
                        </span>
                        <Input
                          aria-label={`Section ${i + 1} query ${qi + 1}`}
                          value={q}
                          onChange={(e) =>
                            updateQuery(section.id, qi, e.target.value)
                          }
                          placeholder="Search query"
                          className="h-7 rounded-md border-border/70 bg-card px-2 text-[0.8rem]"
                        />
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          type="button"
                          aria-label="Remove query"
                          onClick={() => removeQuery(section.id, qi)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <X className="size-3.5" />
                        </Button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => addQuery(section.id)}
                      className="inline-flex w-fit items-center gap-1 rounded-md px-1 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
                    >
                      <Plus className="size-3" /> Add query
                    </button>
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="icon-sm"
                  type="button"
                  aria-label={`Remove section ${i + 1}`}
                  onClick={() => removeSection(section.id)}
                  className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-focus-within/section:opacity-100 group-hover/section:opacity-100"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </div>
          ))}

          <button
            type="button"
            onClick={addSection}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-dashed border-border py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            <Plus className="size-4" /> Add a section
          </button>
        </div>
      </div>

      <div className="flex flex-col-reverse items-stretch gap-2.5 border-t border-border bg-muted/40 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {dirty ? (
            <>
              <button
                type="button"
                onClick={() => setDraft(clone(sections))}
                className="inline-flex items-center gap-1 font-medium text-foreground transition-colors hover:text-primary"
              >
                <RotateCcw className="size-3" /> Reset changes
              </button>
              <span className="text-muted-foreground/60">·</span>
              <span>{draft.length} sections</span>
            </>
          ) : (
            <span>{draft.length} sections planned</span>
          )}
        </div>

        <Button
          onClick={handleApprove}
          disabled={approving || draft.length === 0}
          className="h-10 gap-2 px-5"
        >
          {approving ? (
            <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
          ) : (
            <Check className="size-4" data-icon="inline-start" />
          )}
          {dirty ? "Save & start research" : "Approve & start research"}
        </Button>
      </div>
    </section>
  );
}

function SearchGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-3"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
