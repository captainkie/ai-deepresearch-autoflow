"use client";

/**
 * Client auth state + route guarding.
 *
 * On mount it bootstraps: check first-run setup → try to refresh a session from
 * the httpOnly cookie → load the current user. It then keeps the URL in sync with
 * the auth status (setup mode, unauthenticated, authenticated).
 */
import * as React from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  getMe,
  getSetupStatus,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  runSetup as apiRunSetup,
} from "@/lib/api";
import { refreshAccessToken, setUnauthenticatedHandler } from "@/lib/auth";
import type { User } from "@/lib/types";

export type AuthStatus = "loading" | "setup" | "unauthenticated" | "authenticated";

type Credentials = { email: string; name: string; password: string };

type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (body: Credentials) => Promise<void>;
  completeSetup: (body: Credentials) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export const PUBLIC_ROUTES = ["/login", "/register", "/setup"];
// Reachable in any auth state (no redirect, no guard) — e.g. the credits page.
export const ALWAYS_PUBLIC = ["/about"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = React.useState<AuthStatus>("loading");
  const [user, setUser] = React.useState<User | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  const bootstrap = React.useCallback(async () => {
    try {
      const s = await getSetupStatus();
      if (s.needs_setup) {
        setUser(null);
        setStatus("setup");
        return;
      }
    } catch {
      // Backend unreachable — land on /login; it surfaces the error on submit.
      setUser(null);
      setStatus("unauthenticated");
      return;
    }
    if (await refreshAccessToken()) {
      try {
        setUser(await getMe());
        setStatus("authenticated");
        return;
      } catch {
        /* fall through to unauthenticated */
      }
    }
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  React.useEffect(() => {
    setUnauthenticatedHandler(() => {
      setUser(null);
      setStatus("unauthenticated");
    });
    // Mount-time session bootstrap: every setState below runs after an `await`,
    // not synchronously, so the cascading-render concern doesn't apply here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void bootstrap();
    return () => setUnauthenticatedHandler(null);
  }, [bootstrap]);

  React.useEffect(() => {
    if (status === "loading" || ALWAYS_PUBLIC.includes(pathname)) return;
    const onPublic = PUBLIC_ROUTES.includes(pathname);
    if (status === "setup" && pathname !== "/setup") router.replace("/setup");
    else if (status === "unauthenticated" && !onPublic) router.replace("/login");
    else if (status === "authenticated" && onPublic) router.replace("/");
    else if (status !== "setup" && pathname === "/setup") router.replace("/login");
  }, [status, pathname, router]);

  const login = React.useCallback(async (email: string, password: string) => {
    const session = await apiLogin(email, password);
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const register = React.useCallback(async (body: Credentials) => {
    const session = await apiRegister(body);
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const completeSetup = React.useCallback(async (body: Credentials) => {
    const session = await apiRunSetup(body);
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const logout = React.useCallback(async () => {
    await apiLogout();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = React.useMemo<AuthContextValue>(
    () => ({ status, user, login, register, completeSetup, logout }),
    [status, user, login, register, completeSetup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
