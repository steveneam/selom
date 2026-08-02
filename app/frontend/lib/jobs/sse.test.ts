import { describe, expect, it, vi } from "vitest";

import { drainSseBuffer, followRun, parseSseFrame, RunGoneError } from "./sse";

/** A Response whose body streams `chunks` — the shape `followRun` reads. */
function streamResponse(chunks: string[], ok = true): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const body = {
    getReader() {
      return {
        read: async () =>
          i < chunks.length
            ? { done: false, value: encoder.encode(chunks[i++]) }
            : { done: true, value: undefined },
        cancel: async () => {},
      };
    },
  };
  return { ok, status: ok ? 200 : 500, body } as unknown as Response;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => payload } as unknown as Response;
}

interface State {
  status: string;
}
const isTerminal = (s: State) => s.status === "succeeded" || s.status === "failed";
const noSleep = async () => {};

describe("parseSseFrame", () => {
  it("reads the default `message` event and strips one leading space from data", () => {
    expect(parseSseFrame('data: {"status":"running"}')).toEqual({
      event: "message",
      data: '{"status":"running"}',
    });
  });

  it("reads a named event", () => {
    expect(parseSseFrame('event: error\ndata: {"detail":"unknown job"}')).toEqual({
      event: "error",
      data: '{"detail":"unknown job"}',
    });
  });

  it("joins multi-line data and ignores comments/keep-alives", () => {
    expect(parseSseFrame("data: a\ndata: b")).toEqual({ event: "message", data: "a\nb" });
    expect(parseSseFrame(": keep-alive")).toBeNull();
  });
});

describe("drainSseBuffer", () => {
  it("yields only COMPLETE frames and keeps the partial tail", () => {
    const { frames, rest } = drainSseBuffer('data: {"a":1}\n\ndata: {"b"');
    expect(frames).toEqual([{ event: "message", data: '{"a":1}' }]);
    expect(rest).toBe('data: {"b"');
  });

  it("normalises CRLF line endings", () => {
    const { frames } = drainSseBuffer("data: x\r\n\r\n");
    expect(frames).toEqual([{ event: "message", data: "x" }]);
  });
});

describe("followRun", () => {
  it("resolves from the stream as soon as a terminal state arrives", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async () =>
      streamResponse([
        'data: {"status":"running"}\n\n',
        'data: {"status":"succeeded"}\n\n',
      ]),
    );
    const res = await followRun<State>({
      streamUrl: "/api/jobs/j1/events",
      pollUrl: "/api/jobs/j1",
      isTerminal,
      onState: (s) => seen.push(s.status),
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleep: noSleep,
    });
    expect(res).toEqual({ state: { status: "succeeded" }, terminal: true });
    expect(seen).toEqual(["running", "succeeded"]);
    // Terminal on the stream ⇒ the poll floor is never touched.
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("handles a state split across two network chunks", async () => {
    const fetchImpl = vi.fn(async () =>
      streamResponse(['data: {"status":"suc', 'ceeded"}\n\n']),
    );
    const res = await followRun<State>({
      streamUrl: "/s",
      pollUrl: "/p",
      isTerminal,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleep: noSleep,
    });
    expect(res.terminal).toBe(true);
  });

  it("throws RunGoneError on the server's `event: error` frame — not a transport failure", async () => {
    const fetchImpl = vi.fn(async () =>
      streamResponse(['event: error\ndata: {"detail":"unknown job"}\n\n']),
    );
    await expect(
      followRun<State>({
        streamUrl: "/s",
        pollUrl: "/p",
        isTerminal,
        fetchImpl: fetchImpl as unknown as typeof fetch,
        sleep: noSleep,
      }),
    ).rejects.toBeInstanceOf(RunGoneError);
  });

  it("falls back to polling when the stream cannot be opened at all", async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (url.endsWith("/events")) throw new TypeError("network error");
      return jsonResponse({ status: "succeeded" });
    });
    const res = await followRun<State>({
      streamUrl: "/api/jobs/j1/events",
      pollUrl: "/api/jobs/j1",
      isTerminal,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleep: noSleep,
    });
    expect(res).toEqual({ state: { status: "succeeded" }, terminal: true });
  });

  it("falls back to polling when the stream ENDS before reaching a terminal state", async () => {
    // The backend's stream caps itself at ~5 minutes and then simply stops emitting. Trusting the
    // stream alone would leave a long run pinned at "running" forever.
    const fetchImpl = vi.fn(async (url: string) =>
      url.endsWith("/events")
        ? streamResponse(['data: {"status":"running"}\n\n'])
        : jsonResponse({ status: "succeeded" }),
    );
    const res = await followRun<State>({
      streamUrl: "/api/jobs/j1/events",
      pollUrl: "/api/jobs/j1",
      isTerminal,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleep: noSleep,
    });
    expect(res.terminal).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("treats a 404 from the poll floor as the run being gone", async () => {
    const fetchImpl = vi.fn(async (url: string) =>
      url.endsWith("/events") ? streamResponse([], false) : jsonResponse({}, 404),
    );
    await expect(
      followRun<State>({
        streamUrl: "/api/jobs/j1/events",
        pollUrl: "/api/jobs/j1",
        isTerminal,
        fetchImpl: fetchImpl as unknown as typeof fetch,
        sleep: noSleep,
      }),
    ).rejects.toBeInstanceOf(RunGoneError);
  });

  it("gives up at the ceiling and reports the last state as NON-terminal", async () => {
    let clock = 0;
    const fetchImpl = vi.fn(async (url: string) =>
      url.endsWith("/events")
        ? streamResponse([])
        : jsonResponse({ status: "running" }),
    );
    const res = await followRun<State>({
      streamUrl: "/api/jobs/j1/events",
      pollUrl: "/api/jobs/j1",
      isTerminal,
      timeoutMs: 3000,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleep: async () => {
        clock += 1000;
      },
      now: () => clock,
    });
    expect(res).toEqual({ state: { status: "running" }, terminal: false });
  });
});
