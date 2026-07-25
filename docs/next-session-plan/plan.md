# Next-session plan — the work board

_Written 2026-07-25 21:10 +1000 (Sydney) · 11:10 UTC, after the BROWSER-VERIFY session
(`ff9705d..af6f16e`)._

**Supersedes the sprint-2 lane plan** that lived here (Plan A/B/C, three worktree lanes). That plan
was executed and merged — read it at `git show ff9705d:docs/next-session-plan/plan.md` if you need
its reasoning. Its conventions are kept below because they worked.

**How this file is reached:** `agent_handoff/CURRENT.md` → ▸ NEXT points here and lists it in
▸ READ FIRST, so a session booting on `gogogo` lands here without being told.

**How this file is tracked:** every item has a stable **ID** and a **Status**. The rule: *a fix and
its status flip land in the SAME commit*, and the commit message names the ID. At session start,
mirror the open rows into harness tasks (`TaskCreate`); the durable record stays here, because
harness tasks do not survive the session.

Status vocabulary: `TODO` · `WIP` · `DONE <sha>` · `BLOCKED <on what>` · `DROPPED <why>`. A flip that
lands in the same commit as its fix cannot carry that commit's own sha — write `DONE` and find it
with `git log --grep=<ID>`, which is exactly why the commit message must name the ID.

**Owner-directed: run this SEQUENTIALLY. No worktree lanes** (owner, 2026-07-25). Lane tooling stays
ready (`scripts/worktree-setup.sh`, `scripts/lane-status.sh`) if a later sprint wants it.

---

## Start here

> **⚑ THIS WHOLE BOARD IS OWNER-APPROVED TO EXECUTE** — owner, 2026-07-25: *"we do all those next
> session on gogogo"*. Start `W-1` on boot. Do not re-present the plan for approval, and do not ask
> which item to begin with. Work the tracks in the order at the bottom of this file.
>
> **`Q-1` and `Q-2` are the exception** — founder decisions by nature. Put them to the owner
> **early, via `AskUserQuestion`**, so the answers land while `W-1` is in flight. Do not idle on
> them: `W-1`, `V-1` and `V-2` need no decision, and only `W-2` is genuinely blocked on `Q-1`.

**`W-1` is the first action.** It is a confirmed bug, it is small, its regression test is already
written and currently documents the broken behaviour, and **every other width fix stays invisible to
a user until it lands**. It needs no owner decision, so it proceeds while `Q-1`/`Q-2` sit with the
owner.

---

## Shared context — read once, applies to several tasks

**The browser-verify harness exists and is how anything visual gets checked.**
`scripts/browser-verify.sh` (needs `SELOM_DATASETS_DIR`) boots a real backend (`:8152`, SQLite in the
corpus dir) and a real frontend (`:3152`), drives *new project → drop the real EYG_28 DE CSV → run
the engine's recommended skill*, and stops both servers on exit. Checks are specs under
`app/frontend/e2e/browser-verify/` consuming the `editor` fixture. **Adding a check is a new
`.spec.ts`, never another bespoke script.** Two traps are pinned in the harness and must not be
re-litigated: serve the dev app on `localhost` (never `127.0.0.1`, or React silently never hydrates),
and the harness resets its own store each run.

**The editor only opens on a completed run.** `figure-view.tsx` branches on the LIVE editor store's
`figure.spec`, not the persisted record, and only `figure.init(spec)` seeds it. Demo projects,
API-created projects, localStorage injection and `?demo=` (mock-mode only) all dead-end. Four
shortcuts have failed; the fixture records them so they are not retried.

**A `mockMode`-guarded branch has no coverage.** `dev:mock` skips `uploadDataset` entirely, which is
how a crash on the primary flow survived seven green gates plus a 10-route real-browser smoke. When a
flow branches on `mockMode`, the real branch is untested until a real run exercises it.

**The gate of record is `scripts/verify.sh`** (7 gates, ~70s). Run it raw; never pipe it through
`| tail`.

---

## Track W — the editor's width defect (highest value; newly measured)

Measured at 1280×800 on merged `main` with a real volcano
(`agent_handoff/lane-wraps/lane3.md` §RESULTS · `e2e/browser-verify/remedy-sizing.spec.ts`):

| state | artboard card | plotting area (before `W-1`) | plotting area (after `W-1`) |
|---|---|---|---|
| as shipped | 266px | **90px** | 90px |
| workrail collapsed | 474px (+208) | **90px (+0)** | **294px (+204)** |
| + a window-resize event | 474px | 295px (+205) | 294px (**+0** — nothing left to fix) |

§D's own target is ~506px of plot. Two independent defects, and the second was invisible until the
first was fixed. `W-1` is now fixed and its gate is green; the remaining 212px is `Q-1`/`W-2`.

### `W-1` — a figure must reflow when its CONTAINER resizes · Status: `DONE`

- **Goal.** When the artboard's container changes size without the window changing size, the figure
  re-lays-out to fill it.
- **Context.** Collapsing the project workrail grows the artboard card by 208px and the plotting area
  by **zero**. Plotly's responsive mode listens for `window.resize`; a container that changes size on
  its own (a rail collapsing, a dock opening, a panel toggling) fires no such event, so the figure
  keeps its old width inside a bigger box. This is why §3.4's "collapse the rails" remedy would have
  appeared to do nothing at all. The AI panel, the version bar and every future collapse control share
  the same latent bug.
- **Relevant files.** `app/frontend/components/figure/shell/artboard-host.tsx` and the classic
  `EditorWorkspace` (the two hosts that render the artboard — see `lib/ui/artboard-frame.ts`, which
  exists precisely because they drifted apart before); the Plotly wrapper under `components/figure/`.
  `lib/figure/ssr-plotly-import.test.ts` must stay green — Plotly/WebGL stays behind
  `dynamic(…, { ssr:false })`.
- **Proposed approach.** A `ResizeObserver` on the artboard container that asks Plotly to resize the
  graph div, debounced to at most one call per frame. Put it in ONE place both hosts consult, for the
  same reason `artboardFrame()` is shared. Do not dispatch a synthetic `window.resize` — that
  re-lays-out every figure on the page, including compare panes.
- **Acceptance criteria.**
  - Collapsing the workrail at 1280×800 increases the plotting area with no window resize.
  - No re-layout happens when neither the window nor the container changed.
  - A **fixed**-size figure (numeric `layout.width` — an ERG trace grid) keeps its declared size;
    only responsive figures reflow.
  - `/extract`'s editor gets the same behaviour, being the second host of the same rule.
- **Verify.** `scripts/browser-verify.sh remedy-sizing` — that spec already measures exactly this.
  After the fix, "rail COLLAPSED" must show a plotting-area gain **before** the window nudge, and the
  nudge must add little or nothing. Then `scripts/verify.sh`.
- **Source.** `af6f16e` · `e2e/browser-verify/remedy-sizing.spec.ts` · proposal §3.4.
- **Out of scope.** Deciding which chrome yields space — that is `Q-1`/`W-2`.
- **Shipped.** A `ResizeObserver` in `lib/figure/plot-resize.ts`, wired in `FigureCanvas` — the one
  component every host renders, so the CanvasShell, the classic `EditorWorkspace`, `/extract`, the
  compare panes and the figure-data preview all got it from one place. rAF-coalesced; the observer's
  first callback and any no-change callback are ignored (a Plotly re-layout re-draws every trace and
  churns a WebGL context, so firing on every callback would trade one defect for a subtler one).
  Responsive figures only — a fixed-size figure keeps its declared size, and Plotly's own
  `Plots.resize` early-returns there too, so the rule holds in two places.
  **Measured, not reasoned:** +204px from the collapse alone, +0px from the nudge (table above).
  `remedy-sizing.spec.ts` was upgraded from evidence to a **regression gate** — it now asserts both
  halves, because "the plot grew" alone stays green on the nudge even if the container path dies.
  Two guards extended in the same change: `ssr-plotly-import.test.ts` now bounds *dynamic* plotly
  imports to an allow-list of two files and pins the new one's import to a function body (a top-level
  `await import` would 500 every page — the static-import rule reintroduced through the dynamic
  form), and `lib/figure/plot-resize.test.ts` pins the negative the browser can't cheaply prove.
- **Not measured, and honest about it:** the fixed-size branch (an ERG trace grid keeps its declared
  size) is held by an explicit `if (fixed) return` plus Plotly's own early return, but no browser run
  exercised it — the harness fixture is a responsive volcano. `/extract` inherits the fix
  structurally; **`V-1` measures it directly.**

### `Q-1` — FOUNDER QUESTION: which fixed chrome yields, and how? · Status: `ANSWERED — spec owed`

> **Owner, 2026-07-25: (a) make the inspector dock collapsible — with auto-collapse below a width
> threshold — AND (b) zoom-to-fit + a zoom-% control.** Explicitly NOT (c) folding the tools rail
> away (see `Q-2`) and NOT (d) accepting 1280 as degraded: **1280 stays a supported width**, so
> `W-2`'s acceptance number is not being renegotiated downward. Recorded in
> `agent_handoff/DECISIONS.md`. The spec at `docs/editor-room/spec.md` is still owed and still
> pauses for review before any `W-2` code.

- **Goal.** An owner decision on the layout model, before any code.
- **Context.** Even with the workrail collapsed *and* `W-1` fixed, the plot reaches 295px against a
  506px target. Fixed columns take ~70% of a 1280 viewport: sidebar 256 + workrail 256 + tools rail 48
  + inspector dock 330. The workrail already collapses; **the 330px inspector dock has no collapse
  control at all** and is the largest remaining spender. This is a layout-model decision, not a tweak,
  so it goes to the owner as forcing questions (`AskUserQuestion`) and then a `spec`.
- **Options to put to the owner** (not mutually exclusive). (a) make the inspector dock collapsible,
  and/or auto-collapse below a width threshold; (b) add zoom-to-fit + a zoom-% control so the figure
  fits whatever room it gets — the adopted four-region convention expects this and the top strip is
  currently a static hint line; (c) fold the one-button tools rail away entirely (see `Q-2`);
  (d) accept 1280 as degraded and declare a supported minimum width.
- **Acceptance criteria.** A recorded decision in `agent_handoff/DECISIONS.md`, and a spec at
  `docs/editor-room/spec.md` written and paused for review before implementation.
- **Source.** proposal §3.3/§3.4 · lane3 §RESULTS.

### `W-2` — give the figure room (implements `Q-1`) · Status: `TODO — spec written + decided`

> `docs/editor-room/spec.md` is written and its one owner call (`D-2`) is answered: **auto-collapse
> BOTH the workrail and the inspector dock at ≤1280.** Build to the spec.
>
> **⚑ The board's arithmetic was wrong and the spec corrects it:** collapsing the dock alone reaches
> **368px**, not 506 — even removing the dock entirely reaches only 416. The 506px target needs both
> rails collapsed (**576px**). Do not re-derive this; it is worked in the spec's "the finding that
> shapes this spec".

- **Scope, now that `Q-1` is answered.** (1) a collapse control on the inspector dock + auto-collapse
  below a width threshold; (2) zoom-to-fit + a zoom-% control in the top strip (today a static hint
  line); (3) drop the inspector-dock "Edit a copy" duplicate while in there (`Q-2`.2). The tools
  rail's 48px is **not** available — the owner kept it as a placeholder.
- **The arithmetic to beat.** After `W-1`, 1280×800 gives the plot 294px with the workrail collapsed
  and 90px without. The dock is 330px. Collapsing it is worth ~330px on top — which clears the 506px
  target with the workrail expanded, so **the two collapses must not be required together**; the
  spec should say which state is the default at 1280.
- **Acceptance criteria.** At 1280×800 the plotting area reaches the ~506px §D assumed. The owner
  declined "accept 1280 as degraded", so **1280 stays a supported width** and the target is not to be
  renegotiated downward without a fresh decision.
- **Verify.** `scripts/browser-verify.sh d5`. The `D-5 (also-confirm)` test currently FAILS at 90px
  and **is** the acceptance gate: it must go green, or its threshold must be changed deliberately, to
  the owner's number, with a comment saying whose decision it was.

---

## Track V — finish the verification sweep

### `V-1` — D-11: the `/extract` editor, second host of the L3-01 fix · Status: `DONE`

> **Run, and it found a broken surface.** `e2e/browser-verify/d11-extract.spec.ts` drives a real
> recovery (`scripts/browser-verify.sh d11`), generating its own panel by screenshotting the real
> volcano's artboard card — no committed binary, no MSW handler, real backend
> ("Recovered scatter (196 points)").
>
> **The artboard was never what clipped.** `EditorWorkspace`'s root is `flex min-h-0 flex-1`, so it
> takes a definite height only when its PARENT is a flex container. `CanvasShell` gave it one;
> `chart-extractor.tsx` did not. The stage fell back to CONTENT height — **829px inside an 800px
> viewport** — overflowed its band and painted the figure through the Statistics table below and the
> inspector beside it. **Every per-element measurement still read PASS** (`overflow=0`, `matches=1`,
> floor clear); only the screenshot and a band-vs-band comparison caught it. Fixed with one class.
>
> **Post-fix, the honest numbers:** 1280×800 → `stageClient=279`, `card=320`, **`overflow=73`**;
> 1440×900 → `379`/`347`/`0`. Nothing below the fold; the Statistics band starts exactly where the
> stage ends. ⚑ **The `min-h-[20rem]` floor engages here** — the first real screen where it does.
> Reported, not filed: it is `L3-01`'s deliberate trade. **It qualifies `D-5`'s "keep the floor"
> verdict**, which was measured on the shell (shortest stage 402px); on `/extract` the stage is 279px.
> A founder call if the owner wants one — 73px of scroll vs a 279px card.
>
> The check now gates the overlap itself: the Statistics band must start at or below the stage's
> bottom, and the stage must fit the viewport. That is the assertion no per-element number could make.

- **Goal.** Run §D's D-11 in a real browser: does the artboard clip on `/extract`?
- **Context.** The one reachable §D bullet still unrun. `/extract`'s stage is squeezed between a
  header, an amber vision-grade strip **and** a `StatsPanel` (`defaultOpen`), which makes it **the
  shortest stage in the app** and the most likely place for `L3-01`'s `min-h-[20rem]` (320px) floor to
  engage. It was not run because reaching its editor needs manual canvas calibration: dropping an
  image is not enough — the user must mark two reference ticks on each axis and enter their values
  before recovery unlocks. That is a real interaction to drive, not a selector fix.
- **Relevant files.** `app/frontend/components/extract/chart-extractor.tsx` (drop → calibrate →
  result stages) · `components/extract/calibration-canvas.tsx` · `lib/extract/calibrate.ts`
  (`calibrationComplete`, `calibrationDegenerate` define when the run unlocks).
- **Proposed approach.** Extend the harness, don't write a standalone script. A new
  `e2e/browser-verify/d11-extract.spec.ts` that: (1) uses the `editor` fixture to open a real figure,
  then screenshots **the artboard card element alone** to produce a genuine chart-panel PNG — the
  harness generates its own fixture from a real rendered figure rather than committing a binary;
  (2) goes to `/extract` and drops it; (3) clicks four reference ticks on the calibration canvas and
  enters their axis values; (4) runs the recovery and applies D-5's stage snippet. Read
  `calibrationDegenerate` first — points too close together are rejected, so the four must be
  genuinely spread.
- **Acceptance criteria.**
  - The check reaches `/extract`'s rendered editor on a real backend and reports `stageClient`,
    `card` and `overflow` at 1280×800 and 1440×900.
  - The result is recorded in `lane-wraps/lane3.md` §RESULTS as PASS or as an honest FAIL.
  - If `overflow > 0` here it is **reported, not filed as a regression** — it is the trade `L3-01`
    deliberately made (scroll a too-short stage rather than collapse the card). Give the number so
    the owner can judge.
  - If `stageClient` comes anywhere near **352px**, say so explicitly: that is where the
    `min-h-[20rem]` floor engages, and it would mean the floor is wrong for real screens.
- **Verify.** `scripts/browser-verify.sh d11`, then `scripts/verify.sh`.
- **Out of scope.** The accuracy of the recovered numbers — D-11 is a layout question about the
  editor. The MSW handler at `mocks/handlers.ts:119` is acceptable **only** if it is the sole way to
  reach the editor, and if it is used, the result must say so.

### `V-2` — the cloud round-trip, end to end (+ D-8) · Status: `TODO`

- **Goal.** Import a real file from **Google Drive AND Dropbox** through the UI and confirm
  `datasets.source` is visible on the resulting dataset.
- **Context.** This was Lane 2's own stated gate and no worktree could run a browser, so it has never
  been confirmed. It is genuinely unblocked now: `config.py` reads the repo-root `.env`, the backend
  resolves `https://nango.swordfish.cfd` with both providers enabled, and `deploy/nango/preflight.sh`
  passes against the live broker with both connections refreshing (google-drive `c878e8db…`,
  dropbox `5f45a106…`).
- **Relevant files.** `components/intake/cloud-import-menu.tsx` · `lib/cloud/api.ts` ·
  `docs/cloud-providers-contract/spec.md` (the FROZEN cross-lane contract — read before touching
  cloud) · `deploy/nango/preflight.sh` · `lib/projects/sync.ts::fromApiDatasetSource` (the mapper
  carrying provenance across the boundary; already guarded).
- **Proposed approach.** Run `bash deploy/nango/preflight.sh` first — if it fails, stop and fix that,
  because the UI cannot succeed where the broker check does not. Then a browser-verify spec driving
  the CloudImportMenu per provider. Fold in **D-8**, which was deferred until Lane 2's surface
  settled: its four sub-checks at 1280×800 on `/p/<id>` → Data stage — (a) the URL input's placeholder
  fits its ~218px without ellipsis; (b) the `z-50` popover covers neither the Dropzone above nor the
  dataset rows below; (c) the trigger reads as a peer of the drop-zone, not a stray control; (d) the
  "coming soon" note does not push the popover past the fold.
- **Acceptance criteria.** A file imported from each provider appears as a dataset whose source chip
  names that provider, and a skill run against it succeeds. D-8's four sub-checks recorded.
- **Verify.** `bash deploy/nango/preflight.sh` (raw) → the new spec → `scripts/verify.sh`.
- **Known blocked part.** `L2-07` (a public host for the Nango Connect UI) is **swordfish's**, not
  ours. The direct-link flow works, so a *new* user cannot self-serve a connection until it lands.
  Do not wait on it — note it and proceed with the direct link.

### `Q-2` — FOUNDER CALLS from the browser sweep · Status: `ANSWERED`

Two measured facts that were judgement calls, not defects. Both put to the owner 2026-07-25;
recorded in `agent_handoff/DECISIONS.md`.

1. **The tools rail ships as a one-button column** — 48px wide holding exactly one always-pressed
   `Select` button (`aria-pressed=true`), which is 48px of the 266px the hero gets at 1280. Same
   "fixed chrome must justify its pixels" question the palette strip failed, except this one is not
   inert, just very thin. → **KEEP as a placeholder** (owner): it signals the four-region model and
   fills up when Track C's draw tools land. So the 48px is **not** available to `W-2`.
2. **"Edit a copy" appears twice on one screen** for a frozen figure — once in the frozen command
   cluster, once in the inspector dock. One action, two affordances. → **Keep the command-cluster
   one, drop the inspector-dock duplicate** (owner). Note the reinforcing reason: the dock is the
   panel `Q-1` makes collapsible, and an action must not vanish with a panel. **Do this inside
   `W-2`**, which is already editing the dock — a separate pass would touch the same file twice.

---

## Track R — the reachability backlog

`docs/reachability/backlog.md`, **15 rows open**, enforced by
`app/backend/tests/test_reachability_guard.py`. **A stale waiver FAILS**, so the list can only shrink.
Work it *one waiver per change* — the waiver is deleted by the change that wires its surface up, never
banked ahead.

| ID | What | Status | Note |
|---|---|---|---|
| `R-02` | the whole async job pipeline has no FE consumer | `TODO` | **First.** It is a *precondition* for the unparked `OH-01` (arq + Redis job-status store), not a consequence: nothing in the FE polls a job, so that store would ship with **no reader**. Sequence them together or `OH-01` becomes another unreachable capability. |
| `R-01` + `R-03` | lit-synthesizer (`/methods/compose`, citations) and paper-level outputs (legends, methods, **Reproducibility Score**) have zero FE call sites | `TODO` | Largest user-visible loss and they overlap heavily on methods — do them together. Check first whether the Workspace Library's Methods/legend slot was the intended home. The Reproducibility Score is a named part of the product thesis and currently cannot be shown for a paper. |
| `R-04` | artifacts cannot be fetched back by id | `TODO` | Gates the proposal's `F1`, which must read artifacts back. |
| `R-06` | the reproduction progress stream has no consumer | `TODO` | Same shape as `R-02`. The non-streaming sibling *is* reached, so this is a progress-visibility gap, not a dead feature. |
| `R-05` | `/papers/metadata/by-doi` | `TODO` | A decision, not a build: surface it, or record it internal-only and waive permanently. |

---

## Track C — the annotation layer (deferred, plan exists)

`docs/pillar-2-direct-manipulation/annotation-remediation-spec.md`. **Deferred pending a proper plan,
NOT shelved** — `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism and §6 states the exact
flag-flip condition. ~20 findings are parked with it. Order **C1 → C2 → C3 → C4**.

- **`C1` — claims route to the server.** The integrity defect *and* the cheapest, because it mostly
  **deletes** code (the server already computes stars from real data). Owner decisions already taken:
  typed stars **allowed but marked `unverified`**; selection goes **full direct manipulation**.
- **`C2` — a re-run must not silently discard user work.** Data loss; second.
- **`C3` — full direct manipulation.** Largest slice, and the one that gates the flag.
- **`C4` — decoration completeness.** May trail the flip; it degrades experience but makes no false
  claims.
- **`A23` — now measured, and it is flag-on-only.** §6 lists it as blocking the flip: the tab strip
  overflows at **seven** tabs. At **six** (flag off) it is fine — 48px tracks with 13–26px of slack,
  and §D's "Legend overflows by ~4px" prediction is **disproven**. So C1.3's fold-into-Marks is the
  right fix because it keeps the strip at six.
- **Height-sensitive checks in this spec predate Lane 3's artboard change** — re-derive them against
  current geometry, and expect `W-1`/`W-2` to move it again.
- Anything checked with `ANNOTATION=on scripts/browser-verify.sh` is **Plan C territory**: file
  against this spec, never close as shipped-and-fine.

---

## Track O — awaiting the owner

Nothing here starts without a reaction. `docs/integration-robustness/proposal.md`, explicitly **no new
analysis skills** — the constraint is reachability, not breadth.

| Item | What | Note |
|---|---|---|
| `F1` | figure run history + version diff | The reproducibility wedge made visible. **Blocked on `R-04`.** |
| `F2` | cross-panel consistency audit | Paper-level: did every panel use the same normalization, thresholds and gene annotation? Exactly the failure the WS3.1 blocker was. |
| `F3` | one-click "regenerate at journal spec" | The visible payoff for the unparked `OH-07`; `docs/journal-styles/spec.md` is already written. Cheapest feature on the board. |
| `F4` | reachability dashboard | The waiver table, rendered. Nearly free once the guard exists. |
| `OH-01` | arq + Redis job-status store | **Sequence with `R-02`, not after it.** |
| `OH-07` | journal style packs | Refactor `skills/theme.py` → a named style registry; the vehicle for `F3`. |
| syd2 | public Selom backend | Needs a backend Dockerfile + GHCR image-CI (ours) + 5 data-plane answers. **Owner-gated on spend** (syd2 resize). Reply in ASK-BACKS. |

---

## Sequencing — the recommended order

1. **`W-1`** — confirmed bug, small, unblocks all width work, needs no decision. Ask **`Q-1`** and
   **`Q-2`** at the same time so the answers are waiting when `W-1` lands.
2. **`V-1` (D-11)** — closes the browser sweep; cheap now the harness exists.
3. **`W-2`** — once `Q-1` is answered and its spec reviewed.
4. **`V-2`** — the cloud round-trip + D-8; independent of everything above.
5. **`R-02` (+ `OH-01`)** → **`R-01`+`R-03`** → **`R-04`** (which unblocks `F1`) → `R-06` → the
   `R-05` decision.
6. **Track C**, entered through the spec that already exists.
7. **Track O**, as the owner reacts.

**Review cadence:** `review-gauntlet` + `fe-review` at a **phase/milestone boundary, not per task** —
they are token-heavy and add little at small scope (owner-directed). A small slice gets
`scripts/verify.sh`, plus `scripts/browser-verify.sh` if it is visual.
