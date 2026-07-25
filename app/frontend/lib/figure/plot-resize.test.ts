import { afterEach, describe, expect, it } from "vitest";

import { observeContainerResize } from "@/lib/figure/plot-resize";

/**
 * The container-reflow watcher (W-1). The BROWSER check proves the payoff — collapsing the workrail
 * now gains the plot 204px with no window resize (`browser-verify remedy-sizing`). What a browser
 * cannot cheaply prove is the *negative*: that nothing re-lays-out when nothing changed. A Plotly
 * re-layout is expensive (it re-draws every trace and, on a `scattergl` figure, churns a scarce
 * WebGL context), so a watcher that fires on every observer callback would trade one defect for a
 * subtler one. That contract is what these tests pin.
 *
 * `environment: "node"`, so `ResizeObserver` and `requestAnimationFrame` are both absent and are
 * installed here — which also lets the frame queue be driven by hand instead of by a timer.
 */

type Entry = { contentRect: { width: number; height: number } };

class FakeResizeObserver {
  static last: FakeResizeObserver | undefined;
  observed: Element[] = [];
  disconnected = false;

  constructor(private readonly cb: (entries: Entry[]) => void) {
    FakeResizeObserver.last = this;
  }
  observe(el: Element) {
    this.observed.push(el);
  }
  unobserve() {}
  disconnect() {
    this.disconnected = true;
  }
  /** Simulate the browser reporting a content-box size. */
  emit(width: number, height: number) {
    this.cb([{ contentRect: { width, height } }]);
  }
}

/** Faithful enough to matter: a cancelled frame must not run, or dispose proves nothing. */
const frames = new Map<number, () => void>();
let nextFrameId = 0;
let cancelled = 0;

function installBrowserGlobals() {
  FakeResizeObserver.last = undefined;
  frames.clear();
  nextFrameId = 0;
  cancelled = 0;
  const g = globalThis as Record<string, unknown>;
  g.ResizeObserver = FakeResizeObserver;
  g.requestAnimationFrame = (fn: () => void) => {
    const id = ++nextFrameId;
    frames.set(id, fn);
    return id;
  };
  g.cancelAnimationFrame = (id: number) => {
    cancelled += 1;
    frames.delete(id);
  };
}

/** Run whatever the watcher queued, as the browser would on the next paint. */
function paint() {
  const queued = [...frames.values()];
  frames.clear();
  for (const fn of queued) fn();
}

afterEach(() => {
  const g = globalThis as Record<string, unknown>;
  delete g.ResizeObserver;
  delete g.requestAnimationFrame;
  delete g.cancelAnimationFrame;
});

const EL = {} as Element;

describe("observeContainerResize", () => {
  it("ignores the observer's first callback — that is the size the figure already has", () => {
    installBrowserGlobals();
    let calls = 0;
    observeContainerResize(EL, () => calls++);

    FakeResizeObserver.last!.emit(800, 600);
    paint();

    expect(calls).toBe(0);
  });

  it("reflows once the container actually changes size", () => {
    installBrowserGlobals();
    let calls = 0;
    observeContainerResize(EL, () => calls++);

    FakeResizeObserver.last!.emit(800, 600); // baseline
    FakeResizeObserver.last!.emit(1008, 600); // the workrail collapsed: +208px
    paint();

    expect(calls).toBe(1);
  });

  it("does not reflow when the reported size is unchanged (incl. sub-pixel jitter)", () => {
    installBrowserGlobals();
    let calls = 0;
    observeContainerResize(EL, () => calls++);

    FakeResizeObserver.last!.emit(800, 600);
    FakeResizeObserver.last!.emit(800, 600);
    FakeResizeObserver.last!.emit(800.2, 599.8); // rounds to the same box
    paint();

    expect(calls).toBe(0);
  });

  it("coalesces a burst of callbacks into a single reflow per frame", () => {
    installBrowserGlobals();
    let calls = 0;
    observeContainerResize(EL, () => calls++);

    FakeResizeObserver.last!.emit(800, 600);
    // A CSS width transition reports a new box every frame; each is a real change, but the figure
    // only needs to be laid out at the size it ends up on this frame.
    for (const w of [850, 900, 950, 1008]) FakeResizeObserver.last!.emit(w, 600);
    paint();

    expect(calls).toBe(1);

    // …and the next real change still reflows: the frame gate resets, it does not latch.
    FakeResizeObserver.last!.emit(1008, 400);
    paint();
    expect(calls).toBe(2);
  });

  it("disconnects the observer and drops any pending frame on dispose", () => {
    installBrowserGlobals();
    let calls = 0;
    const dispose = observeContainerResize(EL, () => calls++);

    FakeResizeObserver.last!.emit(800, 600);
    FakeResizeObserver.last!.emit(1008, 600); // queues a frame
    dispose();

    expect(FakeResizeObserver.last!.disconnected).toBe(true);
    expect(cancelled).toBe(1);
    // The unmounted canvas must never be asked to resize — its graph div is gone.
    paint();
    expect(calls).toBe(0);
  });

  it("is a no-op where ResizeObserver is absent, leaving window-resize behaviour untouched", () => {
    // Older engines and any non-DOM render path: degrade to what shipped before, never throw.
    expect(() => observeContainerResize(EL, () => {})()).not.toThrow();
  });
});
