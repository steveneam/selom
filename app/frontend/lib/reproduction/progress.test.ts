import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getActivities, resetActivities } from "@/lib/jobs/activity";
import {
  isReproductionTerminal,
  reproductionEventsUrl,
  reproductionStatusUrl,
  trackReproduction,
} from "./progress";

function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          i < frames.length
            ? { done: false, value: encoder.encode(frames[i++]) }
            : { done: true, value: undefined },
        cancel: async () => {},
      }),
    },
  } as unknown as Response;
}

beforeEach(resetActivities);
afterEach(() => vi.unstubAllGlobals());

describe("reproduction run urls", () => {
  it("point at the run's stream and its non-streaming sibling", () => {
    expect(reproductionEventsUrl("r1")).toBe("/api/reproduction-runs/r1/events");
    expect(reproductionStatusUrl("r1")).toBe("/api/reproduction-runs/r1");
  });
});

describe("isReproductionTerminal", () => {
  it("mirrors the backend's TERMINAL set", () => {
    expect(isReproductionTerminal({ run_id: "r", status: "running" })).toBe(false);
    expect(isReproductionTerminal({ run_id: "r", status: "succeeded" })).toBe(true);
    expect(isReproductionTerminal({ run_id: "r", status: "failed" })).toBe(true);
  });
});

describe("trackReproduction", () => {
  it("shows the run as running from BEFORE the POST resolves", () => {
    trackReproduction("Reproduce hani", "kim2023.pdf");
    expect(getActivities()[0]).toMatchObject({
      kind: "reproduction",
      label: "Reproduce hani",
      context: "kim2023.pdf",
      status: "running",
    });
  });

  it("settles immediately on an already-terminal inline run, without opening the stream", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const track = trackReproduction("Reproduce hani");
    const out = await track.follow({ run_id: "r1", status: "succeeded" as const, ledger: null });
    expect(out.status).toBe("succeeded");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(getActivities()[0]).toMatchObject({ status: "succeeded", serverId: "r1" });
  });

  it("streams the server's own progress line onto the entry, and never invents one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse([
          'data: {"run_id":"r1","status":"running","progress":"panel 2 of 6"}\n\n',
          'data: {"run_id":"r1","status":"succeeded","progress":"6 of 6 driven"}\n\n',
        ]),
      ),
    );
    const track = trackReproduction("Reproduce hani");
    const out = await track.follow({ run_id: "r1", status: "running" as const });
    expect(out.status).toBe("succeeded");
    expect(getActivities()[0]).toMatchObject({ status: "succeeded", detail: "6 of 6 driven" });
  });

  it("carries a failed run's error through to the entry AND the caller", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse(['data: {"run_id":"r1","status":"failed","error":"no golden panels"}\n\n']),
      ),
    );
    const track = trackReproduction("Reproduce hani");
    const out = await track.follow({ run_id: "r1", status: "running" as const });
    expect(out).toMatchObject({ status: "failed", error: "no golden panels" });
    expect(getActivities()[0]).toMatchObject({ status: "failed", error: "no golden panels" });
  });

  it("reports a run the server no longer knows about instead of hanging on it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sseResponse(['event: error\ndata: {"detail":"unknown run"}\n\n'])),
    );
    const track = trackReproduction("Reproduce hani");
    const out = await track.follow({ run_id: "gone", status: "running" as const });
    expect(out.status).toBe("failed");
    expect(getActivities()[0].error).toMatch(/no longer available/);
  });

  it("marks the entry failed when the POST never produced a run at all", () => {
    const track = trackReproduction("Reproduce hani");
    track.fail("Couldn't reach the reproduction service.");
    expect(getActivities()[0]).toMatchObject({
      status: "failed",
      error: "Couldn't reach the reproduction service.",
    });
  });
});
