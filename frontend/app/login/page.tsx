"use client";

import Link from "next/link";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { useAuth } from "@/components/auth-provider";
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
import { loginSchema, type LoginValues } from "@/lib/schemas";
import { DEMO_ADMIN } from "@/lib/demo";
import { useDemoMode } from "@/lib/use-demo-mode";

export default function LoginPage() {
  const { login } = useAuth();
  const demo = useDemoMode();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    try {
      await login(values.email, values.password);
      // AuthProvider redirects to "/" on success.
    } catch (err) {
      toast.error("Sign in failed", {
        description:
          err instanceof Error ? err.message : "Check your email and password.",
      });
    }
  }

  async function loginAsDemoAdmin() {
    form.setValue("email", DEMO_ADMIN.email);
    form.setValue("password", DEMO_ADMIN.password);
    await form.handleSubmit(onSubmit)();
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your research desk"
      footer={
        <>
          No account?{" "}
          <Link
            href="/register"
            className="font-medium text-primary hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="space-y-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button
            type="submit"
            disabled={form.formState.isSubmitting}
            className="h-10 w-full gap-2"
          >
            {form.formState.isSubmitting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            Sign in
          </Button>
        </form>
      </Form>

      <GoogleSignInButton />

      {demo ? (
        // A shared, published admin-role login so demo visitors can explore the
        // admin panel + credentials screen. Safe: mock-only, rate-limited, and the
        // demo DB is reset on a schedule. See lib/demo.ts.
        <div className="mt-4 rounded-md bg-muted/50 p-3 text-sm ring-1 ring-inset ring-border">
          <p className="font-medium text-foreground">Explore as a demo admin</p>
          <p className="mt-1 text-muted-foreground">
            See the admin panel — users, audit log, and the credentials screen
            (key entry is disabled in the demo).
          </p>
          <p className="mt-2 font-mono text-xs break-all text-muted-foreground">
            {DEMO_ADMIN.email} · {DEMO_ADMIN.password}
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={loginAsDemoAdmin}
            disabled={form.formState.isSubmitting}
            className="mt-2 h-9 w-full"
          >
            Log in as demo admin
          </Button>
        </div>
      ) : null}
    </AuthShell>
  );
}
