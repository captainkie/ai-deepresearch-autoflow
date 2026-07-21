"use client";

/**
 * Renders page content only when the current route is valid for the auth status;
 * otherwise shows a spinner while the AuthProvider redirects. Prevents a flash of
 * protected content (or a login form to an already-signed-in user).
 */
import { usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";

import { ALWAYS_PUBLIC, PUBLIC_ROUTES, useAuth } from "@/components/auth-provider";

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const pathname = usePathname();
  const onPublic = PUBLIC_ROUTES.includes(pathname);

  const allowed = ALWAYS_PUBLIC.includes(pathname)
    ? true
    : status === "authenticated"
      ? !onPublic
      : status === "setup"
        ? pathname === "/setup"
        : status === "unauthenticated"
          ? onPublic
          : false;

  if (allowed) return <>{children}</>;

  return (
    <div className="flex min-h-[60vh] items-center justify-center" aria-busy="true">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  );
}
