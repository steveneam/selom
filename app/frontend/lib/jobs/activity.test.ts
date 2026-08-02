import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  beginActivity,
  clearFinishedActivities,
  dismissActivity,
  finishActivity,
  getActivities,
  getActivitiesServerSnapshot,
  resetActivities,
  subscribeActivities,
  updateActivity,
} from "./activity";

beforeEach(resetActivities);

describe("activity store", () => {
  it("records a run as running from the moment it begins", () => {
    const id = beginActivity({ kind: "skill", label: "UMAP", context: "pbmc3k.h5ad" }, 1000);
    const [entry] = getActivities();
    expect(entry).toMatchObject({
      id,
      kind: "skill",
      label: "UMAP",
      context: "pbmc3k.h5ad",
      status: "running",
      startedAt: 1000,
      endedAt: null,
      serverId: null,
      background: false,
    });
  });

  it("KEEPS a finished entry so reaching a terminal state is visible", () => {
    const id = beginActivity({ kind: "skill", label: "DEG" }, 1000);
    finishActivity(id, { status: "succeeded" }, 4000);
    const [entry] = getActivities();
    expect(entry.status).toBe("succeeded");
    expect(entry.endedAt).toBe(4000);
    expect(getActivities()).toHaveLength(1);
  });

  it("carries the failure message onto the entry", () => {
    const id = beginActivity({ kind: "skill", label: "DEG" });
    finishActivity(id, { status: "failed", error: "no groups to compare" });
    expect(getActivities()[0]).toMatchObject({ status: "failed", error: "no groups to compare" });
  });

  it("adopts the server handle without disturbing the rest of the entry", () => {
    const id = beginActivity({ kind: "skill", label: "UMAP" });
    updateActivity(id, { serverId: "job-abc", status: "queued", background: true });
    expect(getActivities()[0]).toMatchObject({
      serverId: "job-abc",
      status: "queued",
      background: true,
      label: "UMAP",
    });
  });

  it("notifies subscribers and returns a referentially STABLE snapshot between changes", () => {
    const cb = vi.fn();
    const unsubscribe = subscribeActivities(cb);
    const id = beginActivity({ kind: "skill", label: "UMAP" });
    const first = getActivities();
    expect(getActivities()).toBe(first); // useSyncExternalStore would loop otherwise
    finishActivity(id, { status: "succeeded" });
    expect(getActivities()).not.toBe(first);
    expect(cb).toHaveBeenCalledTimes(2);
    unsubscribe();
    beginActivity({ kind: "skill", label: "GSEA" });
    expect(cb).toHaveBeenCalledTimes(2);
  });

  it("serves a constant empty snapshot for SSR", () => {
    beginActivity({ kind: "skill", label: "UMAP" });
    expect(getActivitiesServerSnapshot()).toEqual([]);
    expect(getActivitiesServerSnapshot()).toBe(getActivitiesServerSnapshot());
  });

  it("clears finished entries but leaves anything still running", () => {
    const done = beginActivity({ kind: "skill", label: "UMAP" });
    beginActivity({ kind: "reproduction", label: "Reproduce hani" });
    finishActivity(done, { status: "succeeded" });
    clearFinishedActivities();
    expect(getActivities().map((a) => a.label)).toEqual(["Reproduce hani"]);
  });

  it("dismisses one entry by id and ignores an unknown id", () => {
    const id = beginActivity({ kind: "skill", label: "UMAP" });
    dismissActivity("nope");
    expect(getActivities()).toHaveLength(1);
    dismissActivity(id);
    expect(getActivities()).toHaveLength(0);
    // A late update for a dismissed entry must not resurrect it.
    updateActivity(id, { status: "succeeded" });
    expect(getActivities()).toHaveLength(0);
  });

  it("prunes the oldest FINISHED entries past the cap, never a live one", () => {
    const live = beginActivity({ kind: "skill", label: "live" });
    for (let i = 0; i < 12; i += 1) {
      finishActivity(beginActivity({ kind: "skill", label: `done-${i}` }), { status: "succeeded" });
    }
    const labels = getActivities().map((a) => a.label);
    expect(labels).toContain("live");
    expect(labels).not.toContain("done-0");
    expect(labels).toContain("done-11");
    expect(getActivities().filter((a) => a.status === "succeeded")).toHaveLength(8);
  });
});
