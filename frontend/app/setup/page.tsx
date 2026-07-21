"use client";

import * as React from "react";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";

import { AuthShell } from "@/components/auth/auth-shell";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SetupPage() {
  const { completeSetup } = useAuth();
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await completeSetup({ name, email, password });
    } catch (err) {
      setBusy(false);
      toast.error("Setup failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      });
    }
  }

  return (
    <AuthShell
      title="Set up AutoFlow"
      subtitle="Create the first administrator. This happens once."
    >
      <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/[0.05] px-3 py-2.5 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
        <span>
          This account is the <span className="font-medium text-foreground">superadmin</span> — it
          manages users and the encrypted provider-key vault.
        </span>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        </div>
        <Button type="submit" disabled={busy} className="h-10 w-full gap-2">
          {busy ? <Loader2 className="size-4 animate-spin" /> : null}
          Create superadmin & continue
        </Button>
      </form>
    </AuthShell>
  );
}
