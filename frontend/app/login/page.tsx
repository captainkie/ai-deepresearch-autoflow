"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleIcon } from "@/components/icons/google";
import { useAuth } from "@/components/auth-provider";
import { googleStartUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await login(email, password);
      // AuthProvider redirects to "/" on success.
    } catch (err) {
      setBusy(false);
      toast.error("Sign in failed", {
        description: err instanceof Error ? err.message : "Check your email and password.",
      });
    }
  }

  async function onGoogle() {
    try {
      window.location.href = await googleStartUrl();
    } catch {
      toast.error("Google sign-in unavailable", {
        description: "It isn't configured on this server.",
      });
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your research desk"
      footer={
        <>
          No account?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
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
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={busy} className="h-10 w-full gap-2">
          {busy ? <Loader2 className="size-4 animate-spin" /> : null}
          Sign in
        </Button>
      </form>

      <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>

      <Button
        type="button"
        variant="outline"
        onClick={onGoogle}
        className="h-10 w-full gap-2"
      >
        <GoogleIcon className="size-4" />
        Continue with Google
      </Button>
    </AuthShell>
  );
}
