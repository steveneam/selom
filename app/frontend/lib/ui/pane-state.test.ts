import { describe, expect, it } from "vitest";

import { hasData, isDegraded, isPending, type PaneState } from "./pane-state";

/** The pane state machine (Task B3): the predicates that drive <PaneShell>'s stable-shape rendering. */
describe("PaneState predicates", () => {
  const ready: PaneState<number[]> = { status: "ready", data: [1, 2] };
  const partial: PaneState<number[]> = { status: "partial", data: [1], note: "incomplete" };
  const stale: PaneState<number[]> = { status: "stale", data: [1], note: "upstream changed" };
  const idle: PaneState = { status: "idle" };
  const loading: PaneState = { status: "loading", label: "Loading…" };
  const empty: PaneState = { status: "empty", message: "nothing" };
  const error: PaneState = { status: "error", message: "boom" };

  it("hasData narrows to the content states and exposes data", () => {
    for (const s of [ready, partial, stale]) {
      expect(hasData(s)).toBe(true);
      if (hasData(s)) expect(Array.isArray(s.data)).toBe(true); // type-narrowed: .data is reachable
    }
    for (const s of [idle, loading, empty, error]) expect(hasData(s)).toBe(false);
  });

  it("isPending is true only for idle/loading (show a skeleton, never data)", () => {
    expect(isPending(idle)).toBe(true);
    expect(isPending(loading)).toBe(true);
    for (const s of [ready, partial, stale, empty, error]) expect(isPending(s)).toBe(false);
  });

  it("isDegraded marks the usable-but-flagged content states (partial/stale)", () => {
    expect(isDegraded(partial)).toBe(true);
    expect(isDegraded(stale)).toBe(true);
    for (const s of [ready, idle, loading, empty, error]) expect(isDegraded(s)).toBe(false);
  });

  it("the seven statuses are mutually exclusive (exactly one bucket per state)", () => {
    const all: PaneState<number[]>[] = [idle, loading, empty, partial, stale, error, ready];
    for (const s of all) {
      const buckets = [isPending(s), s.status === "empty", isDegraded(s), s.status === "error", s.status === "ready"];
      expect(buckets.filter(Boolean).length).toBe(1);
    }
  });
});
