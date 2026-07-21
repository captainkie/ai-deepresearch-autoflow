"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, Check, Target, Map, Telescope, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { getTemplates, createRun } from "@/lib/api";
import { FALLBACK_TEMPLATES, DEFAULT_TEMPLATE_ID } from "@/lib/templates";
import { composerSchema, type ComposerValues } from "@/lib/schemas";
import type { Template } from "@/lib/types";
import { cn } from "@/lib/utils";

const TEMPLATE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  competitor_brand: Target,
  market_landscape: Map,
  deep_research: Telescope,
};

const EXAMPLES = [
  "Competitive teardown of Notion vs. Coda for a productivity launch",
  "How is Liquid Death winning at brand marketing?",
  "Map the direct-to-consumer coffee market in 2026",
  "What is Figma's positioning and who are its real challengers?",
];

export function ResearchComposer() {
  const router = useRouter();
  const form = useForm<ComposerValues>({
    resolver: zodResolver(composerSchema),
    defaultValues: { query: "" },
  });
  const [templates, setTemplates] = React.useState<Template[]>(FALLBACK_TEMPLATES);
  const [loadingTemplates, setLoadingTemplates] = React.useState(true);
  const [selected, setSelected] = React.useState<string>(DEFAULT_TEMPLATE_ID);
  const [language, setLanguage] = React.useState<"en" | "th">("en");
  const [reviewPlan, setReviewPlan] = React.useState(true);
  const submitting = form.formState.isSubmitting;

  React.useEffect(() => {
    let active = true;
    getTemplates()
      .then((data) => {
        if (active && data.length) {
          setTemplates(data);
          setSelected((cur) =>
            data.some((t) => t.id === cur) ? cur : data[0].id,
          );
        }
      })
      .catch(() => {
        /* keep fallback templates */
      })
      .finally(() => {
        if (active) setLoadingTemplates(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const { run_id } = await createRun({
        query: values.query.trim(),
        template: selected,
        language,
        require_plan_approval: reviewPlan,
      });
      router.push(`/runs/${run_id}`);
    } catch (err) {
      toast.error("Couldn't start research", {
        description:
          err instanceof Error
            ? err.message
            : "The research service is unreachable. Check that the backend is running.",
      });
    }
  });

  function onKeyDown(e: React.KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={onSubmit}
        noValidate
        className="relative rounded-2xl bg-card p-2 shadow-[var(--shadow-soft)] ring-1 ring-foreground/10"
      >
        <div className="rounded-xl border border-border/60 bg-background/40 p-4 sm:p-5">
          <Label htmlFor="research-query" className="sr-only">
            What do you want to research?
          </Label>
          <FormField
            control={form.control}
            name="query"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <Textarea
                    id="research-query"
                    {...field}
                    onKeyDown={onKeyDown}
                    placeholder="What do you want to research? e.g. “A full competitive brand analysis of Oatly — positioning, messaging, audience, and weaknesses.”"
                    className="min-h-32 resize-none border-0 bg-transparent px-0 py-0 font-reading text-lg leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  form.setValue("query", ex, { shouldValidate: true });
                  form.setFocus("query");
                }}
                className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-secondary/40 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                <Sparkles className="size-3 text-primary/70" />
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* Template picker */}
        <div className="px-3 pt-4">
          <p className="eyebrow mb-2.5" id="approach-label">
            Choose an approach
          </p>
          <div
            role="radiogroup"
            aria-labelledby="approach-label"
            className="grid gap-2.5 sm:grid-cols-3"
          >
            {templates.map((t) => {
              const Icon = TEMPLATE_ICONS[t.id] ?? Telescope;
              const active = selected === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setSelected(t.id)}
                  className={cn(
                    "group relative flex flex-col gap-2 rounded-xl border p-3.5 text-left transition-all outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
                    active
                      ? "border-primary/50 bg-primary/[0.06] shadow-[var(--shadow-soft)]"
                      : "border-border/70 bg-card hover:border-primary/30 hover:bg-accent/40",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        "inline-flex size-8 items-center justify-center rounded-lg transition-colors",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground group-hover:text-foreground",
                      )}
                    >
                      <Icon className="size-4" />
                    </span>
                    <span
                      className={cn(
                        "flex size-[1.15rem] items-center justify-center rounded-full border transition-all",
                        active
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border",
                      )}
                    >
                      {active && <Check className="size-3" strokeWidth={3} />}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="font-display text-[0.95rem] font-semibold leading-tight tracking-tight">
                      {t.name}
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {t.description}
                    </p>
                  </div>
                  <span className="mt-auto pt-1 text-[0.68rem] font-medium uppercase tracking-wider text-muted-foreground/80">
                    {t.audience}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 px-3 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
            {/* Output language */}
            <div
              role="radiogroup"
              aria-label="Report language"
              className="inline-flex items-center rounded-lg border border-border/70 bg-card p-0.5"
            >
              {(
                [
                  { id: "en", label: "EN" },
                  { id: "th", label: "ไทย" },
                ] as const
              ).map((opt) => {
                const active = language === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setLanguage(opt.id)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      active
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>

            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1">
              <Switch
                checked={reviewPlan}
                onCheckedChange={setReviewPlan}
                aria-label="Review the plan before research starts"
              />
              <span className="text-sm">
                <span className="font-medium text-foreground">Review the plan first</span>
                <span className="ml-1.5 hidden text-muted-foreground sm:inline">
                  Approve or edit before searching begins
                </span>
              </span>
            </label>
          </div>

          <div className="flex items-center gap-3">
            <kbd className="hidden shrink-0 whitespace-nowrap rounded border border-border bg-muted px-1.5 py-0.5 text-[0.7rem] text-muted-foreground sm:inline-block">
              ⌘ + ↵
            </kbd>
            <Button
              type="submit"
              disabled={submitting}
              className="h-11 gap-2 px-6 text-[0.95rem]"
            >
              {submitting ? (
                <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
              ) : null}
              {submitting ? "Starting…" : "Start research"}
              {!submitting && <ArrowRight className="size-4" data-icon="inline-end" />}
            </Button>
          </div>
        </div>

        {loadingTemplates && (
          <div className="sr-only" aria-live="polite">
            Loading templates
          </div>
        )}
      </form>
    </Form>
  );
}
