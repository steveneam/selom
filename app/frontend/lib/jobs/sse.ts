"use client";

/**
 * Follow a server-side run to its terminal state: read its Server-Sent Events stream, and fall
 * back to polling its non-streaming sibling when the stream is unavailable or ends early.
 *
 * WHY A `fetch` READER AND NOT `EventSource`. Three reasons, all load-bearing for this contract:
 *
 *  1. **Auth.** `EventSource` cannot set request headers, so it can never carry the
 *     `Authorization: Bearer` the backend's clerk auth mode requires (`auth/context.py`). Every
 *     `/jobs/{id}/events` subscription would 401 the moment P-E turns real auth on. A `fetch`
 *     reader carries whatever headers it is handed.
 *  2. **`event: error` is ambiguous under `EventSource`.** `routers/jobs.py` emits a real
 *     `event: error` frame for an unknown job id, but `EventSource` delivers TRANSPORT failures on
 *     that same listener — a consumer cannot tell "the server says this job is gone" from "the
 *     connection dropped". Here they are different code paths.
 *  3. **Reconnect.** `EventSource` auto-reconnects when the server closes the stream, which is
 *     exactly what both streams do on reaching a terminal state — it would restart the whole poll
 *     loop server-side, forever. A plain reader stops when the server stops.
 *
 * Both streams (`/jobs/{id}/events`, `/reproduction-runs/{id}/events`) cap themselves at ~5
 * minutes and then simply stop emitting, so a reader that trusted the stream alone would leave a
 * long run pinned at "running". Hence the poll fallback: the stream is the fast path, polling is
 * the floor.
 */

export interface SseFrame {
  /** The `event:` name, defaulting to `message` as the SSE spec requires. */
  event: string;
  /** The joined `data:` lines. */
  data: string;
}

/**
 * Parse ONE SSE frame (the text between blank lines). Returns null for a frame that carries no
 * payload and no explicit event name — a comment/keep-alive, which callers must ignore rather
 * than treat as a state update.
 */
export function parseSseFrame(raw: string): SseFrame | null {
  let event = "";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) continue; // blank or comment (keep-alive)
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1); // the spec strips ONE leading space
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (!event && data.length === 0) return null;
  return { event: event || "message", data: data.join("\n") };
}

/** Split a growing buffer into complete frames, returning the frames and the unconsumed tail. */
export function drainSseBuffer(buffer: string): { frames: SseFrame[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const frames: SseFrame[] = [];
  for (const part of parts) {
    const frame = parseSseFrame(part);
    if (frame) frames.push(frame);
  }
  return { frames, rest };
}

/** The server explicitly said this run is unknown/gone — a real answer, not a transport failure. */
export class RunGoneError extends Error {
  constructor(detail: string) {
    super(detail);
    this.name = "RunGoneError";
  }
}

export interface FollowOptions<T> {
  /** The SSE endpoint (fast path). */
  streamUrl: string;
  /** The non-streaming sibling, polled when the stream is unavailable or ends early. */
  pollUrl: string;
  /** True when this state needs no further watching. */
  isTerminal: (state: T) => boolean;
  /** Called for EVERY state the server reports, from the stream or from a poll. */
  onState?: (state: T) => void;
  pollIntervalMs?: number;
  /** Hard ceiling on the whole follow. Mirrors the backend's own ~5-minute stream ceiling. */
  timeoutMs?: number;
  /** Injected for tests. */
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
}

export interface FollowResult<T> {
  /** The last state the server reported, or null if it never reported one. */
  state: T | null;
  /** True when {@link FollowOptions.isTerminal} accepted that state. */
  terminal: boolean;
}

const DEFAULT_POLL_MS = 1000;
const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;

function defaultSleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Read the stream until it yields a terminal state (or ends). Returns the last state seen.
 * Throws {@link RunGoneError} when the server sends its `event: error` frame.
 */
async function readStream<T>(
  res: Response,
  opts: FollowOptions<T>,
): Promise<FollowResult<T>> {
  const body = res.body;
  if (!body) return { state: null, terminal: false };
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let last: T | null = null;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = drainSseBuffer(buffer);
      buffer = rest;
      for (const frame of frames) {
        if (frame.event === "error") {
          let detail = "This run is no longer available.";
          try {
            const parsed = JSON.parse(frame.data) as { detail?: unknown };
            if (typeof parsed.detail === "string") detail = parsed.detail;
          } catch {
            /* a non-JSON error frame still means "gone" */
          }
          throw new RunGoneError(detail);
        }
        let state: T;
        try {
          state = JSON.parse(frame.data) as T;
        } catch {
          continue; // a malformed frame is not a state change
        }
        last = state;
        opts.onState?.(state);
        if (opts.isTerminal(state)) return { state, terminal: true };
      }
      if (done) return { state: last, terminal: false };
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      /* already closed */
    }
  }
}

/**
 * Follow a run to its terminal state. Never throws for a transport problem — a stream that will
 * not open just degrades to polling — but DOES throw {@link RunGoneError} when the server says
 * the run is unknown, because that is an answer the caller has to surface.
 */
export async function followRun<T>(opts: FollowOptions<T>): Promise<FollowResult<T>> {
  const doFetch = opts.fetchImpl ?? fetch;
  const sleep = opts.sleep ?? defaultSleep;
  const now = opts.now ?? Date.now;
  const deadline = now() + (opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  let last: T | null = null;

  // 1) Fast path — the event stream.
  try {
    const res = await doFetch(opts.streamUrl, { headers: { accept: "text/event-stream" } });
    if (res.ok) {
      const streamed = await readStream<T>(res, opts);
      if (streamed.terminal) return streamed;
      last = streamed.state ?? last;
    }
  } catch (e) {
    if (e instanceof RunGoneError) throw e;
    // Any other stream failure is a transport problem — fall through to polling.
  }

  // 2) Floor — poll the non-streaming sibling until terminal or the ceiling.
  while (now() < deadline) {
    let res: Response;
    try {
      res = await doFetch(opts.pollUrl, { headers: { accept: "application/json" } });
    } catch {
      await sleep(opts.pollIntervalMs ?? DEFAULT_POLL_MS);
      continue;
    }
    if (res.status === 404) throw new RunGoneError("This run is no longer available.");
    if (res.ok) {
      const state = (await res.json()) as T;
      last = state;
      opts.onState?.(state);
      if (opts.isTerminal(state)) return { state, terminal: true };
    }
    await sleep(opts.pollIntervalMs ?? DEFAULT_POLL_MS);
  }
  return { state: last, terminal: false };
}
