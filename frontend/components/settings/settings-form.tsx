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
import type {
  ConfigResponse,
  ConfigUpdate,
  VerificationLevel,
} from "@/lib/types";
import {
  LLM_PROVIDERS,
  SEARCH_PROVIDERS,
  PROVIDER_MODELS,
  providerLabel,
  defaultModelFor,
} from "@/lib/providers";
import { cn } from "@/lib/utils";

const CUSTOM_MODEL = "__custom__";

/** All known providers ∪ whatever the backend reports, each tagged available. */
function providerOptions(
  known: readonly string[],
  available: string[],
  current?: string,
): { id: string; available: boolean }[] {
  const ids = uniq([...known, ...available, current]);
  return ids.map((id) => ({ id, available: available.includes(id) }));
}

type FormState = {
  llm_provider: string;
  llm_model: string;
  search_provider: string;
  require_plan_approval: boolean;
  verification_level: VerificationLevel;
};

function toForm(c: ConfigResponse): FormState {
  return {
    llm_provider: c.llm.provider ?? "",
    llm_model: c.llm.model ?? "",
    search_provider: c.search.provider ?? "",
    require_plan_approval: c.require_plan_approval,
    verification_level: c.verification_level ?? "light",
  };
}

const VERIFICATION_LEVELS: {
  value: VerificationLevel;
  label: string;
  hint: string;
}[] = [
  { value: "off", label: "Off", hint: "Legacy — summarize sources, no claim checks" },
  { value: "light", label: "Light", hint: "Extract & verify claims (recommended)" },
  { value: "strict", label: "Strict", hint: "Verify claims and probe harder" },
];

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
    if (form.verification_level !== base.verification_level)
      payload.verification_level = form.verification_level;

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

  const llmOptions = providerOptions(
    LLM_PROVIDERS,
    config.llm.available,
    config.llm.provider,
  );
  const searchOptions = providerOptions(
    SEARCH_PROVIDERS,
    config.search.available,
    config.search.provider,
  );
  const modelSuggestions = PROVIDER_MODELS[form.llm_provider] ?? [];
  const modelIsCustom =
    modelSuggestions.length === 0 || !modelSuggestions.includes(form.llm_model);

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
                  setForm({
                    ...form,
                    llm_provider: v,
                    llm_model: defaultModelFor(v) ?? form.llm_model,
                  })
                }
              >
                <SelectTrigger id="llm-provider" className="sm:w-56">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {llmOptions.map(({ id, available }) => (
                      <SelectItem key={id} value={id} disabled={!available}>
                        {providerLabel(id)}
                        {!available ? " · needs key" : ""}
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
              {modelSuggestions.length > 0 ? (
                <div className="flex flex-col gap-2 sm:w-56">
                  <Select
                    value={modelIsCustom ? CUSTOM_MODEL : form.llm_model}
                    onValueChange={(v) =>
                      setForm({
                        ...form,
                        llm_model: v === CUSTOM_MODEL ? "" : v,
                      })
                    }
                  >
                    <SelectTrigger id="llm-model" className="font-mono text-sm">
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {modelSuggestions.map((m) => (
                          <SelectItem key={m} value={m} className="font-mono text-sm">
                            {m}
                          </SelectItem>
                        ))}
                        <SelectItem value={CUSTOM_MODEL}>Custom…</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  {modelIsCustom ? (
                    <Input
                      value={form.llm_model}
                      onChange={(e) =>
                        setForm({ ...form, llm_model: e.target.value })
                      }
                      placeholder="Custom model id"
                      aria-label="Custom model id"
                      className="font-mono text-sm"
                    />
                  ) : null}
                </div>
              ) : (
                <Input
                  id="llm-model"
                  value={form.llm_model}
                  onChange={(e) =>
                    setForm({ ...form, llm_model: e.target.value })
                  }
                  placeholder="e.g. gpt-4o-mini"
                  className="font-mono text-sm sm:w-56"
                />
              )}
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
                    {searchOptions.map(({ id, available }) => (
                      <SelectItem key={id} value={id} disabled={!available}>
                        {providerLabel(id)}
                        {!available ? " · needs key" : ""}
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

          <Field orientation="responsive" className="border-t pt-5">
            <FieldContent>
              <FieldLabel htmlFor="verification-level">
                Claim verification
              </FieldLabel>
              <FieldDescription>
                How rigorously the engine grounds and checks each claim before it
                reaches the report. Off falls back to plain summarization.
              </FieldDescription>
            </FieldContent>
            <Select
              value={form.verification_level}
              onValueChange={(v) =>
                setForm({ ...form, verification_level: v as VerificationLevel })
              }
            >
              <SelectTrigger id="verification-level" className="sm:w-56">
                <SelectValue placeholder="Select a level" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {VERIFICATION_LEVELS.map((lv) => (
                    <SelectItem key={lv.value} value={lv.value}>
                      {lv.label}
                      <span className="text-muted-foreground"> · {lv.hint}</span>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
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
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                isActive
                  ? "bg-primary/12 text-primary"
                  : "bg-secondary/60 text-muted-foreground",
              )}
            >
              {isActive && <span className="size-1.5 rounded-full bg-primary" />}
              {providerLabel(p)}
            </span>
          );
        })}
      </div>
    </div>
  );
}
