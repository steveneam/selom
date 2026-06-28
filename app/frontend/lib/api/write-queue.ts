"use client";

/**
 * Background write queue for the optimistic stores (sub-spec §2.4).
 *
 * Mutators apply to the in-memory cache synchronously and return at once; the durable API write is
 * enqueued here and drained off the render path. Features:
 *  - **FIFO drain** with transient-retry backoff (network/5xx) and **roll-back on permanent fail**
 *    (4xx the user can't fix — the caller's `onPermanentFail` reverts the optimistic change).
 *  - **Coalescing** by `coalesceKey` — a newer op replaces a pending one (the live figure-spec edit
 *    storm collapses to one PATCH carrying the latest spec).
 *  - **Grace delay + cancel** — a delete is enqueued with `graceMs`; an Undo within the window calls
 *    `cancel(key)` and the DELETE never fires (no data loss, no API round-trip).
 *  - A subscribable **status** (idle | saving | offline | error) for a non-blocking sync chip.
 */

export type SyncStatus = "idle" | "saving" | "offline" | "error";

export interface EnqueueOp {
  /** Cancelable id (e.g. `del:figure:f1`) — `cancel(key)` drops it if not yet started. */
  key?: string;
  /** Replace a pending op with the same coalesceKey (latest wins) — e.g. `spec:f1`. */
  coalesceKey?: string;
  /** Delay before the op becomes eligible (the delete grace window). Default 0. */
  graceMs?: number;
  run: () => Promise<unknown>;
  /** Called if the op fails permanently (4xx) so the caller can revert the optimistic change. */
  onPermanentFail?: () => void;
}

interface QueuedOp extends EnqueueOp {
  readyAt: number;
  tries: number;
  started: boolean;
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, Math.max(0, ms)));
const backoff = (tries: number) => Math.min(1000 * 2 ** (tries - 1), 15000);

export class WriteQueue {
  private ops: QueuedOp[] = [];
  private running = false;
  private status: SyncStatus = "idle";
  private listeners = new Set<() => void>();
  private now: () => number;

  /** `now` is injectable for tests; defaults to `Date.now`. */
  constructor(now: () => number = () => Date.now()) {
    this.now = now;
  }

  subscribe = (cb: () => void): (() => void) => {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  };

  getStatus = (): SyncStatus => this.status;

  /** For tests / a "saving…" guard: how many writes are still pending. */
  get pending(): number {
    return this.ops.length;
  }

  private setStatus(s: SyncStatus): void {
    if (s !== this.status) {
      this.status = s;
      this.listeners.forEach((l) => l());
    }
  }

  enqueue(op: EnqueueOp): void {
    if (op.coalesceKey) {
      // Collapse onto a PENDING (not-yet-started) op only — an op already in-flight can't be
      // replaced, so edits arriving during a slow save become a single trailing op (latest wins).
      const existing = this.ops.find((o) => o.coalesceKey === op.coalesceKey && !o.started);
      if (existing) {
        existing.run = op.run;
        existing.onPermanentFail = op.onPermanentFail;
        this.kick();
        return;
      }
    }
    this.ops.push({ ...op, readyAt: this.now() + (op.graceMs ?? 0), tries: 0, started: false });
    this.kick();
  }

  /** Drop a not-yet-started op (an Undo within the delete grace window). Returns true if removed. */
  cancel(key: string): boolean {
    const op = this.ops.find((o) => o.key === key && !o.started);
    if (!op) return false;
    this.remove(op);
    if (!this.ops.length && this.status !== "error") this.setStatus("idle");
    return true;
  }

  private remove(op: QueuedOp): void {
    this.ops = this.ops.filter((o) => o !== op);
  }

  private nextReady(): QueuedOp | undefined {
    const now = this.now();
    return this.ops.find((o) => !o.started && o.readyAt <= now);
  }

  private kick(): void {
    if (!this.running) void this.drain();
  }

  private async drain(): Promise<void> {
    this.running = true;
    try {
      for (;;) {
        const op = this.nextReady();
        if (!op) {
          const pending = this.ops.filter((o) => !o.started);
          if (!pending.length) break; // nothing left to run (in-flight ops finish on their own)
          await sleep(Math.min(...pending.map((o) => o.readyAt)) - this.now()); // grace window
          continue;
        }
        op.started = true; // identity-tracked — splice by reference, not a stale index
        this.setStatus("saving");
        try {
          await op.run();
          this.remove(op);
        } catch (e) {
          if ((e as { permanent?: boolean })?.permanent) {
            this.remove(op); // give up — revert the optimistic change
            this.setStatus("error");
            op.onPermanentFail?.();
          } else {
            op.started = false; // transient — re-pick after backoff
            op.tries += 1;
            this.setStatus("offline");
            await sleep(backoff(op.tries));
          }
        }
      }
      if (this.status !== "error") this.setStatus("idle");
    } finally {
      this.running = false;
    }
  }
}
