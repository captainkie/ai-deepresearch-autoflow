"use client";

import * as React from "react";
import {
  Cpu,
  Search,
  Workflow,
  KeyRound,
  Loader2,
  Check,
  RefreshCw,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
  FieldContent,
} from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty";
import { getConfig, updateConfig } from "@/lib/api";
import type { ConfigResponse, ConfigUpdate } from "@/lib/types";
import { cn } from "@/lib/utils";

type FormState = {
  llm_provider: string;
  llm_model: string;
  search_provider: string;
  require_plan_approval: boolean;
};

function toForm(c: ConfigResponse): FormState {
  return {
    llm_provider: c.llm.provider ?? "",
    llm_model: c.llm.model ?? "",
    search_provider: c.search.provider ?? "",
    require_plan_approval: c.require_plan_approval,
  };
}

function uniq(values: (string | undefined)[]): string[] {
  return Array.from(new Set(values.filter((v): v is string => !!v)));
}

export function SettingsForm() {
  const [config, setConfig] = React.useState<ConfigResponse | null>(null);
  const [form, setForm] = React.useState<FormState | null>(null);
  const [state, setState] = React.useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    setState("loading");
    try {
      const c = await getConfig();
      setConfig(c);
      setForm(toForm(c));
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  // Initial load — setState happens in the async callback (initial state is
  // already "loading"), avoiding a synchronous setState in the effect body.
  React.useEffect(() => {
    let active = true;
    getConfig()
      .then((c) => {
        if (active) {
          setConfig(c);
          setForm(toForm(c));
          setState("ready");
        }
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  const dirty = React.useMemo(() => {
    if (!config || !form) return false;
    const base = toForm(config);
    return (Object.keys(base) as (keyof FormState)[]).some(
      (k) => base[k] !== form[k],
    );
  }, [config, form]);

  async function handleSave() {
    if (!config || !form || !dirty || saving) return;
    const base = toForm(config);
    const payload: ConfigUpdate = {};
    if (form.llm_provider !== base.llm_provider)
      payload.llm_provider = form.llm_provider;
    if (form.llm_model !== base.llm_model) payload.llm_model = form.llm_model;
    if (form.search_provider !== base.search_provider)
      payload.search_provider = form.search_provider;
    if (form.require_plan_approval !== base.require_plan_approval)
      payload.require_plan_approval = form.require_plan_approval;

    setSaving(true);
    try {
      const updated = await updateConfig(payload);
      setConfig(updated);
      setForm(toForm(updated));
      toast.success("Settings saved");
    } catch (err) {
      toast.error("Couldn't save settings", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  if (state === "loading") {
    return (
      <div className="flex flex-col gap-5">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="rounded-xl bg-card p-6 ring-1 ring-foreground/10"
          >
            <Skeleton className="h-5 w-40" />
            <Skeleton className="mt-2 h-4 w-64" />
            <Skeleton className="mt-5 h-9 w-full" />
            <Skeleton className="mt-3 h-9 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (state === "error" || !config || !form) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <WifiOff />
          </EmptyMedia>
          <EmptyTitle>Settings unavailable</EmptyTitle>
          <EmptyDescription>
            We couldn&apos;t load the configuration. Make sure the research
            backend is running, then try again.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button variant="outline" size="sm" onClick={load} className="gap-1.5">
            <RefreshCw className="size-3.5" data-icon="inline-start" />
            Retry
          </Button>
        </EmptyContent>
      </Empty>
    );
  }

  const llmProviders = uniq([...config.llm.available, config.llm.provider]);
  const searchProviders = uniq([...config.search.available, config.search.provider]);

  return (
    <div className="flex flex-col gap-5">
      {/* Models & providers */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Cpu className="size-4" />
            </span>
            <div>
              <CardTitle>Models &amp; providers</CardTitle>
              <CardDescription>
                Which language and search providers power new research runs.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field orientation="responsive">
              <FieldContent>
                <FieldLabel htmlFor="llm-provider">
                  Language model provider
                </FieldLabel>
                <FieldDescription>
                  Generates the plan, reflections, and final report.
                </FieldDescription>
              </FieldContent>
              <Select
                value={form.llm_provider}
                onValueChange={(v) =>
                  setForm({ ...form, llm_provider: v })
                }
              >
                <SelectTrigger id="llm-provider" className="sm:w-56">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {llmProviders.length === 0 && (
                      <SelectItem value={form.llm_provider || "none"} disabled>
                        No providers available
                      </SelectItem>
                    )}
                    {llmProviders.map((p) => (
                      <SelectItem key={p} value={p} className="capitalize">
                        {p}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>

            <Field orientation="responsive">
              <FieldContent>
                <FieldLabel htmlFor="llm-model">Model</FieldLabel>
                <FieldDescription>
                  The specific model id for the selected provider.
                </FieldDescription>
              </FieldContent>
              <Input
                id="llm-model"
                value={form.llm_model}
                onChange={(e) =>
                  setForm({ ...form, llm_model: e.target.value })
                }
                placeholder="e.g. gpt-4o-mini"
                className="font-mono text-sm sm:w-56"
              />
            </Field>

            <Field orientation="responsive">
              <FieldContent>
                <FieldLabel htmlFor="search-provider">
                  Search provider
                </FieldLabel>
                <FieldDescription>
                  Runs the live web searches for each section.
                </FieldDescription>
              </FieldContent>
              <Select
                value={form.search_provider}
                onValueChange={(v) =>
                  setForm({ ...form, search_provider: v })
                }
              >
                <SelectTrigger id="search-provider" className="sm:w-56">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {searchProviders.length === 0 && (
                      <SelectItem
                        value={form.search_provider || "none"}
                        disabled
                      >
                        No providers available
                      </SelectItem>
                    )}
                    {searchProviders.map((p) => (
                      <SelectItem key={p} value={p} className="capitalize">
                        {p}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>

      {/* Workflow */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Workflow className="size-4" />
            </span>
            <div>
              <CardTitle>Workflow</CardTitle>
              <CardDescription>
                How much control your team keeps over each run.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Field orientation="horizontal">
            <FieldContent>
              <FieldLabel htmlFor="plan-approval">
                Require plan approval
              </FieldLabel>
              <FieldDescription>
                Pause after planning so someone can review or edit the sections
                before research begins. Recommended.
              </FieldDescription>
            </FieldContent>
            <Switch
              id="plan-approval"
              checked={form.require_plan_approval}
              onCheckedChange={(v) =>
                setForm({ ...form, require_plan_approval: v })
              }
            />
          </Field>
        </CardContent>
      </Card>

      {/* Available providers (read-only) */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <KeyRound className="size-4" />
            </span>
            <div>
              <CardTitle>Available providers</CardTitle>
              <CardDescription>
                Detected from the credentials configured in the backend
                environment. API keys are never entered here.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <ProviderRow
            icon={<Cpu className="size-3.5" />}
            label="Language models"
            available={config.llm.available}
            active={config.llm.provider}
          />
          <ProviderRow
            icon={<Search className="size-3.5" />}
            label="Search"
            available={config.search.available}
            active={config.search.provider}
          />
        </CardContent>
      </Card>

      {/* Save bar */}
      <div className="sticky bottom-4 z-10 flex items-center justify-between gap-3 rounded-xl border border-border bg-background/85 p-3 pl-4 shadow-[var(--shadow-soft)] backdrop-blur-md">
        <span className="text-sm text-muted-foreground">
          {dirty ? "You have unsaved changes." : "Everything is up to date."}
        </span>
        <Button
          onClick={handleSave}
          disabled={!dirty || saving}
          className="gap-1.5"
        >
          {saving ? (
            <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
          ) : (
            <Check className="size-4" data-icon="inline-start" />
          )}
          Save changes
        </Button>
      </div>
    </div>
  );
}

function ProviderRow({
  icon,
  label,
  available,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  available: string[];
  active?: string;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <span className="flex items-center gap-2 text-sm font-medium">
        <span className="text-muted-foreground">{icon}</span>
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {available.length === 0 && (
          <span className="rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive">
            None configured
          </span>
        )}
        {available.map((p) => {
          const isActive = p === active;
          return (
            <span
              key={p}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                isActive
                  ? "bg-primary/12 text-primary"
                  : "bg-secondary/60 text-muted-foreground",
              )}
            >
              {isActive && <span className="size-1.5 rounded-full bg-primary" />}
              {p}
            </span>
          );
        })}
      </div>
    </div>
  );
}
