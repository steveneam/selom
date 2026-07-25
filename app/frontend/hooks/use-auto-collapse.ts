"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { shouldAutoCollapse } from "@/lib/ui/editor-room";

/**
 * A rail's collapsed state, defaulted from the viewport width and then owned by the user (`W-2`,
 * `docs/editor-room/spec.md` R4).
 *
 * The rule it enforces is the one that makes auto-collapse tolerable rather than annoying: the
 * viewport decides the STARTING state and keeps deciding while the user is indifferent, but **the
 * first time the user toggles the rail themselves, the viewport stops having an opinion for the rest
 * of the session.** Without that latch, a user who opens the inspector at 1280 would watch it slam
 * shut again on the next resize, which reads as the app fighting them.
 *
 * `enabled` gates the whole behaviour — a rail that is not part of the editor's room budget passes
 * `false` and simply keeps manual state.
 */
export function useAutoCollapse(enabled: boolean): [boolean, (next: boolean) => void] {
  // Starts expanded on the server and on the first client paint: `window` is not readable during
  // render, and a rail that flashes open→closed is better than one that renders closed on a wide
  // screen because the width was unknown.
  const [collapsed, setCollapsed] = useState(false);
  const userDecided = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    const apply = () => {
      if (userDecided.current) return;
      setCollapsed(shouldAutoCollapse(window.innerWidth));
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [enabled]);

  const set = useCallback((next: boolean) => {
    userDecided.current = true;
    setCollapsed(next);
  }, []);

  return [collapsed, set];
}
