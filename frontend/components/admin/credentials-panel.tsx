"use client";

import * as React from "react";
import { toast } from "sonner";
import { KeyRound, Plus, RefreshCw } from "lucide-react";

import {
  createCredential,
  listCredentials,
  revokeCredential,
  rotateMasterKey,
} from "@/lib/api";
import type { Credential } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  const [provider, setProvider] = React.useState(PROVIDERS[0]);
  const [label, setLabel] = React.useState("");
  const [secret, setSecret] = React.useState("");
  const [adding, setAdding] = React.useState(false);
  const [pendingKey, setPendingKey] = React.useState<string | null>(null);
  const [rotating, setRotating] = React.useState(false);

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

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!secret.trim() || adding) return;
    setAdding(true);
    try {
      await createCredential({ provider, label: label.trim() || provider, secret });
      setSecret("");
      setLabel("");
      toast.success("Credential added");
      await load();
    } catch (err) {
      toast.error("Couldn't add credential", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setAdding(false);
    }
  }

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
      <form onSubmit={add} className="rounded-xl border border-border/70 bg-card/40 p-4">
        <p className="mb-3 flex items-center gap-1.5 text-sm font-medium">
          <Plus className="size-4 text-primary" /> Add a provider key
        </p>
        <div className="grid gap-3 sm:grid-cols-[10rem_12rem_1fr_auto] sm:items-end">
          <div className="space-y-1">
            <Label htmlFor="cred-provider" className="text-xs">
              Provider
            </Label>
            <select
              id="cred-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="cred-label" className="text-xs">
              Label
            </Label>
            <Input
              id="cred-label"
              placeholder="e.g. prod"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cred-secret" className="text-xs">
              Secret
            </Label>
            <Input
              id="cred-secret"
              type="password"
              placeholder="sk-…"
              autoComplete="off"
              required
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={adding || !secret.trim()} className="h-8">
            Add
          </Button>
        </div>
      </form>

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
              <Th>Last used</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {creds.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                  No credentials yet.
                </td>
              </tr>
            ) : null}
            {creds.map((c) => (
              <tr key={c.id} className="hover:bg-muted/20">
                <Td className="font-medium">{c.provider}</Td>
                <Td>{c.label}</Td>
                <Td>
                  <code className="text-xs text-muted-foreground">{c.masked_hint}</code>
                </Td>
                <Td>
                  <StatusPill ok={c.status === "active"} labels={["Active", "Revoked"]} />
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
