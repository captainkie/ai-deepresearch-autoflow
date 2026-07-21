"use client";

import { FlaskConical } from "lucide-react";

import { useDemoMode } from "@/lib/use-demo-mode";

/**
 * A sticky warning shown only when the backend reports `demo_mode`. It tells
 * visitors the demo uses mock data and not to paste real API keys — the backend
 * also forces mock providers and blocks credential entry, so this is the visible
 * half of that safety contract.
 */
export function DemoBanner() {
  const demo = useDemoMode();

  if (!demo) return null;

  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-amber-500/15 px-4 py-1.5 text-center text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-500/25 backdrop-blur dark:text-amber-200">
      <FlaskConical className="size-3.5 shrink-0" />
      <span>
        Live demo — research runs on <strong>mock data</strong>. Please don&apos;t
        enter real API keys or anything sensitive.
      </span>
    </div>
  );
}
