"use client";

import { useEffect, useState } from "react";

import { apiMockingEnabled as MOCKING_ENABLED } from "@/lib/config/env";

/**
 * Starts the MSW browser worker before rendering children, but ONLY when
 * NEXT_PUBLIC_API_MOCKING === "enabled" (the `dev:mock` script). In every other
 * run it's a transparent passthrough, so the real backend proxy is untouched.
 *
 * We gate render on the worker being ready (when mocking) so no fetch can race
 * the interceptor. The cost is a brief blank frame in dev — acceptable, and it
 * never happens in normal `dev`/prod because we short-circuit below.
 */
export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(!MOCKING_ENABLED);

  useEffect(() => {
    if (!MOCKING_ENABLED) return;
    let active = true;
    (async () => {
      const { worker } = await import("../mocks/browser");
      await worker.start({ onUnhandledRequest: "bypass" });
      if (active) setReady(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
