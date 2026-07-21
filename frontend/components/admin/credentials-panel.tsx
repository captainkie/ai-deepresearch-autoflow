"use client";

import * as React from "react";
import { toast } from "sonner";
import { KeyRound, Plus, RefreshCw, FlaskConical } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import {
  createCredential,
  getHealth,
  listCredentials,
  revokeCredential,
  rotateMasterKey,
} from "@/lib/api";
import type { Credential } from "@/lib/types";
import { credentialSchema, type CredentialValues } from "@/lib/schemas";
import { providerLabel } from "@/lib/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { PanelLoading, StatusPill, Td, Th } from "./primitives";

const PROVIDERS = [
  "anthropic",
  "openai",
  "gemini",
  "zai",
  "moonshot",
  "tavily",
  "serper",
  "exa",
  "jina",
];

function generateMasterKey(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}

export function CredentialsPanel() {
  const [creds, setCreds] = React.useState<Credential[] | null>(null);
  const [pendingKey, setPendingKey] = React.useState<string | null>(null);
  const [rotating, setRotating] = React.useState(false);
  const [demo, setDemo] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    getHealth()
      .then((h) => {
        if (active) setDemo(!!h.demo_mode);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const form = useForm<CredentialValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: { provider: PROVIDERS[0], label: "", secret: "", expiresOn: "" },
  });

  const load = React.useCallback(async () => {
    try {
      setCreds(await listCredentials());
    } catch (err) {
      toast.error("Couldn't load credentials", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }, []);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const onAdd = form.handleSubmit(async (values) => {
    try {
      // A <input type="date"> yields "YYYY-MM-DD". Treat it as end-of-day in the
      // admin's *local* time (so the date shown back matches what they picked),
      // then serialize to an aware UTC ISO string the backend can compare safely.
      const expires_at = values.expiresOn
        ? new Date(`${values.expiresOn}T23:59:59`).toISOString()
        : null;
      await createCredential({
        provider: values.provider,
        label: values.label?.trim() || values.provider,
        secret: values.secret,
        expires_at,
      });
      form.reset({ provider: values.provider, label: "", secret: "", expiresOn: "" });
      toast.success("Credential added");
      await load();
    } catch (err) {
      toast.error("Couldn't add credential", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  });

  async function revoke(id: string) {
    try {
      await revokeCredential(id);
      toast.success("Credential revoked");
      await load();
    } catch (err) {
      toast.error("Couldn't revoke", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }

  async function confirmRotate() {
    if (!pendingKey || rotating) return;
    setRotating(true);
    try {
      const result = await rotateMasterKey(pendingKey);
      toast.success(`Master key rotated (key version ${result.key_version})`);
      setPendingKey(null);
      await load();
    } catch (err) {
      toast.error("Rotation failed", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setRotating(false);
    }
  }

  if (!creds) return <PanelLoading />;

  return (
    <div className="space-y-6">
      <Form {...form}>
        <form
          onSubmit={onAdd}
          noValidate
          className="rounded-xl border border-border/70 bg-card/40 p-4"
        >
          <p className="mb-3 flex items-center gap-1.5 text-sm font-medium">
            <Plus className="size-4 text-primary" /> Add a provider key
          </p>
          {demo && (
            <div className="mb-3 flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/[0.06] px-3 py-2 text-xs text-muted-foreground">
              <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-amber-600" />
              <span>
                Adding keys is disabled in the demo. Don&apos;t paste a real API
                key here — the demo runs entirely on mock providers.
              </span>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-[8rem_9rem_minmax(0,1fr)_9.5rem_auto] sm:items-start">
            <FormField
              control={form.control}
              name="provider"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">Provider</FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      disabled={demo}
                      className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm disabled:opacity-50"
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p} value={p}>
                          {providerLabel(p)}
                        </option>
                      ))}
                    </select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="label"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">Label</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. prod" disabled={demo} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="secret"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">Secret</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="sk-…"
                      autoComplete="off"
                      disabled={demo}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="expiresOn"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    Expires{" "}
                    <span className="text-muted-foreground">(optional)</span>
                  </FormLabel>
                  <FormControl>
                    <Input type="date" className="h-8" disabled={demo} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex flex-col gap-1.5">
              <span className="hidden text-xs sm:block" aria-hidden>
                &nbsp;
              </span>
              <Button
                type="submit"
                disabled={form.formState.isSubmitting || demo}
                className="h-8"
              >
                Add
              </Button>
            </div>
          </div>
        </form>
      </Form>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <KeyRound className="mt-0.5 size-4 text-amber-600" />
            <div className="text-sm">
              <p className="font-medium">Rotate the master key</p>
              <p className="text-xs text-muted-foreground">
                Re-encrypts every credential under a new key. Save the new key to{" "}
                <code className="rounded bg-muted px-1">AUTOFLOW_MASTER_KEY</code>.
              </p>
            </div>
          </div>
          {!pendingKey ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              disabled={demo}
              onClick={() => setPendingKey(generateMasterKey())}
            >
              <RefreshCw className="size-3.5" /> Rotate
            </Button>
          ) : null}
        </div>
        {pendingKey ? (
          <div className="mt-3 space-y-2 rounded-lg border border-border bg-background p-3">
            <p className="text-xs font-medium text-destructive">
              Save this key now — set it as AUTOFLOW_MASTER_KEY or credentials become unreadable
              after a restart.
            </p>
            <code className="block break-all rounded bg-muted px-2 py-1.5 text-xs">
              {pendingKey}
            </code>
            <div className="flex gap-2">
              <Button size="sm" className="h-8" onClick={confirmRotate} disabled={rotating}>
                {rotating ? "Rotating…" : "I saved it — rotate now"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-8"
                onClick={() => setPendingKey(null)}
                disabled={rotating}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/70">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <Th>Provider</Th>
              <Th>Label</Th>
              <Th>Key</Th>
              <Th>Status</Th>
              <Th>Expires</Th>
              <Th>Last used</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {creds.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                  No credentials yet.
                </td>
              </tr>
            ) : null}
            {creds.map((c) => (
              <tr key={c.id} className="hover:bg-muted/20">
                <Td className="font-medium">{providerLabel(c.provider)}</Td>
                <Td>{c.label}</Td>
                <Td>
                  <code className="text-xs text-muted-foreground">{c.masked_hint}</code>
                </Td>
                <Td>
                  <StatusPill ok={c.status === "active"} labels={["Active", "Revoked"]} />
                </Td>
                <Td className="text-xs">
                  {!c.expires_at ? (
                    <span className="text-muted-foreground">—</span>
                  ) : new Date(c.expires_at) < new Date() ? (
                    <span className="font-medium text-destructive">
                      {new Date(c.expires_at).toLocaleDateString()} · expired
                    </span>
                  ) : (
                    <span className="text-muted-foreground">
                      {new Date(c.expires_at).toLocaleDateString()}
                    </span>
                  )}
                </Td>
                <Td className="text-xs text-muted-foreground">
                  {c.last_used_at ? new Date(c.last_used_at).toLocaleString() : "—"}
                </Td>
                <Td className="text-right">
                  {c.status === "active" ? (
                    <button
                      type="button"
                      onClick={() => revoke(c.id)}
                      className="text-xs font-medium text-destructive hover:underline"
                    >
                      Revoke
                    </button>
                  ) : null}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
