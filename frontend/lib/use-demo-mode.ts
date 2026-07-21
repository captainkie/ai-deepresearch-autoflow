"use client";

import * as React from "react";

import { getHealth } from "@/lib/api";

// One shared health probe for all consumers (banner, auth pages) so we don't hit
// /health once per component. A transient failure clears the cache so it can retry.
let cached: Promise<boolean> | null = null;

function probeDemo(): Promise<boolean> {
  if (!cached) {
    cached = getHealth()
      .then((h) => !!h.demo_mode)
      .catch(() => {
        cached = null;
        return false;
      });
  }
  return cached;
}

/**
 * Whether the backend reports demo mode. `null` while the probe is in flight, so
 * callers can avoid flashing demo-only UI before the answer is known.
 */
export function useDemoMode(): boolean | null {
  const [demo, setDemo] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    let active = true;
    probeDemo().then((value) => {
      if (active) setDemo(value);
    });
    return () => {
      active = false;
    };
  }, []);

  return demo;
}
