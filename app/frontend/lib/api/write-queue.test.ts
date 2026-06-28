import { describe, expect, it, vi } from "vitest";
import { WriteQueue } from "./write-queue";

const flush = () => new Promise<void>((r) => setTimeout(r, 0));

describe("WriteQueue", () => {
  it("runs an enqueued op and returns to idle", async () => {
    const q = new WriteQueue();
    const run = vi.fn().mockResolvedValue(undefined);
    q.enqueue({ run });
    await flush();
    expect(run).toHaveBeenCalledTimes(1);
    expect(q.getStatus()).toBe("idle");
    expect(q.pending).toBe(0);
  });

  it("coalesces edits arriving during an in-flight save (the figure-spec edit storm)", async () => {
    const q = new WriteQueue();
    let resolveFirst!: () => void;
    const first = vi.fn(() => new Promise<void>((r) => { resolveFirst = r; }));
    const second = vi.fn().mockResolvedValue(undefined);
    const third = vi.fn().mockResolvedValue(undefined);
    q.enqueue({ coalesceKey: "spec:f1", run: first }); // starts immediately → in-flight
    await flush();
    q.enqueue({ coalesceKey: "spec:f1", run: second }); // pending behind the in-flight op
    q.enqueue({ coalesceKey: "spec:f1", run: third }); // collapses onto it — latest wins
    resolveFirst();
    await flush();
    expect(first).toHaveBeenCalledTimes(1); // already in-flight, ran
    expect(second).not.toHaveBeenCalled(); // replaced by third before it started
    expect(third).toHaveBeenCalledTimes(1); // the single trailing save
  });

  it("rolls back on a permanent (4xx) failure", async () => {
    const q = new WriteQueue();
    const onPermanentFail = vi.fn();
    q.enqueue({ run: () => Promise.reject({ permanent: true }), onPermanentFail });
    await flush();
    expect(onPermanentFail).toHaveBeenCalledTimes(1);
    expect(q.getStatus()).toBe("error");
  });

  it("retries a transient failure with backoff, then succeeds", async () => {
    vi.useFakeTimers();
    try {
      const q = new WriteQueue();
      let calls = 0;
      const run = vi.fn(() => {
        calls += 1;
        return calls < 2 ? Promise.reject({ permanent: false }) : Promise.resolve();
      });
      q.enqueue({ run });
      await vi.advanceTimersByTimeAsync(2000); // past the first backoff (~1000ms)
      expect(run).toHaveBeenCalledTimes(2);
      expect(q.getStatus()).toBe("idle");
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancel() drops a grace-delayed op before it runs (Undo within the window)", async () => {
    vi.useFakeTimers();
    try {
      const q = new WriteQueue();
      const run = vi.fn().mockResolvedValue(undefined);
      q.enqueue({ key: "del:figure:f1", graceMs: 5000, run });
      expect(q.cancel("del:figure:f1")).toBe(true);
      await vi.advanceTimersByTimeAsync(6000);
      expect(run).not.toHaveBeenCalled();
      expect(q.pending).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("runs a grace-delayed op after the window elapses (Undo not taken)", async () => {
    vi.useFakeTimers();
    try {
      const q = new WriteQueue();
      const run = vi.fn().mockResolvedValue(undefined);
      q.enqueue({ key: "del:figure:f1", graceMs: 5000, run });
      await vi.advanceTimersByTimeAsync(6000);
      expect(run).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
