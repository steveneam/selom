# Integration, robustness & what to build next — proposal

Status: **PROPOSAL — awaiting owner reaction** · 2026-07-25 17:20 +1000 (Sydney)

**Why this exists.** At the Phase 0 founder gate the owner asked for two things beyond the on-hold
triage: *"any more features or things that you think selom could benefit from"*, and *"integration
[of] the current features and layout and workflow — make sure it's tight and robust."* This is the
answer. It is a proposal, not a plan of record: nothing here is scheduled until the owner picks.

---

## 1. The honest diagnosis first

The headline number from the milestone review is that **31 of 35 user tasks have no affordance**. It
would be easy to read that as "the product is 11% reachable" and panic. That reading is wrong, and
the distinction matters for deciding what to build:

**Those 31 gaps are almost entirely the Pillar-2 annotation/drawing layer** — brackets, text labels,
draw tools, canvas selection. That layer is **deferred pending a proper plan** (owner intent, clarified
2026-07-25): `NEXT_PUBLIC_ANNOTATION_LAYER` off by default is the *holding mechanism*, **not** a
decision to shelve the work — a real plan for finishing it is owed, and the flag flips when that plan
is executed. So those gaps are not bleeding on users, but they are not closed either: **the deliverable
is the plan.**

**The reachability debt on surfaces that ARE live:**

| Shipped capability | Reachable? | Covered by |
|---|---|---|
| Google Drive + Dropbox OAuth (live tokens, 200s) | **No** — no providers endpoint, FE hardcodes `comingSoon`, flags absent from `.env` | Lane 2 (`L2-01`, `L2-02`, `L2-06`) |
| `POST /data/assemble-scrna` (works, `11a115f`) | **No** — no FE surface at all | Lane 2 (`L2-05`) |
| ERG OP · PhNR · flicker-FFT · robust a/b (`a84636c`) | **No** — measured, nothing surfaces them | Lane 1 (`L1-09`) |
| `datasets.source` provenance (backend-stamped) | **No** — dropped by the FE mapper, so a cloud import looks hand-dropped | Lane 2 (`L2-03`) |
| Artboard / editor chrome | Partly — hero clipped, no collapse, no zoom-to-fit | Lane 3 (`L3-01`, `L3-02`, `L3-04`) |

> **⚠ CORRECTION (2026-07-25, after §2 was built).** This section originally concluded *"all of it is
> already in the approved lanes — the plan is already pointed at the right work."* **That was wrong, and
> the ratchet in §2 disproved it within a minute of first running.** The table above is what a *review*
> found. The mechanical sweep found **17 of 61 user-facing routes (28%) with no frontend call site** —
> 8× more, including the entire **lit-synthesizer** (`/methods/compose`, `/citations/*` — shipped, zero
> FE) and the entire **async job pipeline** (which means the just-unparked `OH-01` job-status store
> would ship with no reader). Full list + IDs: **`docs/reachability/backlog.md`**.
>
> I am leaving the wrong conclusion visible rather than quietly editing it, because it is the whole
> argument for §2: a careful review of the *scheduled* work told me the plan was well-pointed, and it
> was not. Only the executable sweep knew.

So the gap was **both** structural *and* larger than scheduled. Nothing prevented this recurring, and
nobody had counted it. That is §2.

---

## 2. The durable fix: a reachability ratchet — ✅ **BUILT 2026-07-25**

**Owner directed "build the reachability ratchet first, then fork the lanes." Done** —
`app/backend/tests/test_reachability_guard.py`, green, 22 assertions. Backlog it produced:
`docs/reachability/backlog.md`. The rest of this section is the original reasoning, which held up.

**What it caught immediately, beyond the predicted set:** 17 of 61 user-facing paths unreachable (§1's
correction box), **and three waivers I had guessed wrong** — I assumed `/export/cloud`,
`/import/local-state` and `/uploads/local/{key:path}` were unreachable and the scan proved they are
reached. The stale-waiver half corrected its own author on the first run, which is the best evidence
it will correct a lane later.

**Recommendation as written: build this first, before any new feature.** It is small, and it is the
difference between fixing this backlog and fixing the *class*.

"Shipped ≠ reachable" is already a recorded lesson ([[selom-shipped-not-reachable]]) whose stated
remedy is "add a reachability guard test" — and that guard was never built. So the lesson lives only
in memory, which is the weakest rung of the ratchet ladder. Meanwhile CLAUDE.md's doctrine is
explicit: keep the *strongest* expression of an invariant, and enforcement must be gated on an exit
code.

**Shape.** An executable guard that enumerates user-facing backend capabilities — registered routes
plus the skill registry — and asserts each one is either:

1. **reached** by a declared FE surface (a route/component that calls it), or
2. **explicitly waived** in a single declared table, with a reason and a tracking ID.

A new endpoint with no FE path and no waiver **fails the build**. The waiver table becomes the honest,
one-glance answer to "what have we built that nobody can use?" — the question this review had to
spend a whole gauntlet pass to answer.

**Why it will hold where the memory note didn't:** it fails in the author's own run, at the moment
the unreachable thing is added, instead of in a review months later. It is the same pattern that just
worked for the `/cloud/providers` contract freeze — an invariant nobody can quietly drift past.

**Cost:** small — one guard test plus one waiver table. **Scope note:** it must ship with waivers for
today's known-unreachable set (the table in §1) so it starts green and each lane *removes* a waiver as
it lands. A guard that starts red is a guard people learn to ignore — the same trap `L1-10` was.

---

## 3. Integration / layout / workflow — "tight and robust"

Beyond what the lanes already fix, these are the coherence problems the review surfaced. Ordered by
value-per-effort.

### 3.1 One obvious next action on every surface
The G1 walkthrough's recurring complaint is not that a control is ugly — it is that after an action
**nothing confirms it happened**, so "invisible" and "broken" are indistinguishable (verbatim from
finding C: *"Nothing selects/flashes/counts the new item"*). A single shared convention — every
mutation confirms itself, and every surface names its next step — is cheap and fixes a whole class.
Pairs naturally with Lane 3.

### 3.2 Re-run must not silently discard user work
`rerunFigure` carries **only** gene labels; every other annotation is dropped with no warning on the
Re-run button or the StaleBadge. Even with the annotation layer deferred behind its flag, this is the workflow's
sharpest edge: the user's own work vanishes on the most routine action in the product. **Robustness
before features.** (Plan C territory, so it needs Plan C's spec — but it should be that spec's first
slice, not its last.)

### 3.3 The editor's vertical budget is oversubscribed
The artboard is pinned to `min(74vh,720px)` while the shell added ~150px of fixed chrome inside the
same container, so the figure clips at 1280×800 — and an inert "coming soon" palette strip
permanently spends 64px of that budget for no return. Lane 3 (`L3-01`, `L3-02`) fixes the two
symptoms; the *principle* worth adopting is that **the artboard is the hero and fixed chrome must
justify its pixels.**

### 3.4 Give the figure room: collapse, and zoom-to-fit
`ArtboardHost`'s own comment assumes collapsible rails ("collapsing the side rails gives the figure
more room") and the shell ships **no collapse control**; the top strip is a static hint line where the
adopted four-region convention expects zoom-%/fit-to-window. Two small controls, disproportionate
relief on a height-constrained editor.

### 3.5 One column-matcher, not six
`_pick` is forked verbatim into six runners, so the drift guard can see one *vocabulary* but not one
*matcher* (`A19`). This is the same class as the bug that caused the campaign's worst blocker — raw-vs-
adjusted p flipping across five runners. Already Lane 1 (`L1-02`); flagged here because it is the
robustness item most likely to cause the *next* incident.

---

## 4. Feature proposals

Filtered hard against decision #10 (win the analysis→editable-figure last mile; don't chase breadth).
Each leans on machinery Selom already has.

| # | Feature | Why it is worth it | Leverage already in place |
|---|---|---|---|
| **F1** | **Figure run history + version diff** — for a figure, show its versions and answer "what changed between v3 and v4?" across *both* numbers and cosmetics. | This is the reproducibility wedge made visible. Competitors export a raster and forget; Selom can show that a threshold moved and 40 genes left the significant set. Directly serves the "match numbers exactly" mission. | The provenance chokepoint (`stamp_ai_actions`) already stamps every write; figure versions already exist. Mostly a read-side surface over data we keep. |
| **F2** | **Cross-panel consistency audit** — at paper level, verify every panel used the same normalization, thresholds and gene annotation, and flag panels that disagree. | The single most credible thing a reproducibility product can offer, and the exact failure the WS3.1 blocker was: five runners silently disagreeing about what "significant" meant. Nobody else in the space does paper-level self-consistency. | Provenance is already stamped per run; the Reproducibility Score already aggregates per-panel. This is a new lens over existing records. |
| **F3** | **One-click "regenerate at journal spec"** — pick Nature/Cell/eLife, every panel re-exports to that spec. | Turns the just-unparked journal style packs (`OH-07`, spec already written) into the visible last-mile payoff, and it is the most common real-world chore in figure prep. | `docs/journal-styles/spec.md` exists; `skills/theme.py` centralises theming; Kaleido export ships in all three formats. Refactor theme → named registry and wire it. |
| **F4** | **Reachability dashboard** (the §2 waiver table, rendered) | Makes "what have we built that nobody can use?" a glance instead of a review pass. Costs nearly nothing once §2 exists. | Falls out of the guard's waiver table. |

**Deliberately not proposed:** new analysis skills. Selom has 30+ and the constraint is reachability,
not breadth — adding skills while five shipped capabilities have no UI makes the ratio worse. Same
reasoning the on-hold register uses to keep OmicVerse and the external-tool builds parked.

---

## 5. Recommended sequencing

1. **The 3 approved lanes** — unchanged, already partitioned and gated. They land most of §1's table.
2. **§2 reachability ratchet** — small, and it stops the class recurring. Ideally *before* the lanes,
   with waivers for today's set, so each lane removes a waiver as it lands and the ratchet is what
   proves the lane finished.
3. **§3.1 + §3.4** with Lane 3 — same files, same milestone.
4. **OH-01 (arq + Redis)** and **OH-07 → F3 (journal specs)** — the two unparked items; `F3` is the
   product-visible reason `OH-07` is worth doing at all.
5. **Plan C spec**, led by **§3.2** (re-run must not discard user work) rather than more drawing tools.
6. **F1**, then **F2** — the reproducibility moat, once the spine is coherent.

**The one thing I would not do:** start new features before §2 exists. Without it, the next capability
ships unreachable too, and the review that finds it costs more than the guard would have.
