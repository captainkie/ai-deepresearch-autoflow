"use client";

import { toast } from "sonner";

import { GoogleIcon } from "@/components/icons/google";
import { googleStartUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";

/** "or" divider + Google OAuth button, shared by the login and register pages. */
export function GoogleSignInButton({
  label = "Continue with Google",
}: {
  label?: string;
}) {
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
    <>
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
        {label}
      </Button>
    </>
  );
}
