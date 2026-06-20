# Umbrella shell — spec

> Status: **SHIPPED + browser-verified (s40, 2026-06-21)** — built and verified on :3001 vs the live
> BE. Live handoff (drop Hani PDF → route → Reproduce → `/paper/<id>?stage=reproduce`), all three
> stages (Skill Match inventory · Reproduce intake · Score skeleton), URL-driven pills + deep-links,
> both old-route redirects, supplement intake persistence, and the untouched showcase all confirmed.
> Two owner refinements folded in mid-build: the Reproduce **trigger moved to the pipeline's top-right
> ("Run reproduction")** and a **layout twitch fixed** (`scrollbar-gutter: stable` on the `<main>`
> scroll container — the centered page no longer shifts when a scrollbar appears between a short and a
> tall stage). One regression caught + fixed in-session: a hydration mismatch from `useSearchParams`
> shifting store-hydration timing → gated `PaperShell` behind a `mounted` flag. Gates: tsc · eslint
> 0err · vitest 99 · console clean. Spec-first per the owner direction. Owner picked the
> umbrella shell (option b) from the s39 handoff, then confirmed the decisions below: **D-a** new
> `/paper/[id]` shell · **D-b** Recover data deferred to step (a) · **D-c** Score = its own tab, AND
> (owner steer) the ghosted score + heatmap get a **faithful aligned skeleton** mirroring the real
> `PaperDetail` score region (today's loose dashed ghost has no real skeleton — same fix discipline as
> the s39 spectrum-card redesign) · **D-d** keep the entry/showcase navs. This spec covers ONE step:
> collapsing the per-paper surfaces into a single tabbed workspace over one **Paper** anchor. It is the
> realization of
> `docs/workspace-library/spec.md` §10 (the unified Paper workflow) and resolves §10's first open
> question (*"replace the three nav entries with one Paper workspace, or keep them as deep-links?"*).
> Lane: **Claude FE** (the Paper anchor + all four surfaces are client-side; no backend in scope).
> [[selom-workspace-library]] [[unify-on-superior-framework]]

## 1. Why

s37–s39 built the substrate: a `SavedPaper` anchor, a shared `PaperMetaHeader`, and a `PaperPipeline`
stage strip whose pills already navigate per-paper (Skill Match ⇄ Reproduce; Score gated). But the
per-paper work still lives across **two separate routes** that re-mount full-page chrome on every hop:

- `/skill-match/[id]` — the saved skill inventory (stage 1 destination).
- `/reproduction/paper/[id]` — the supplements intake + ghosted score + ghosted heatmap (stage 2).

Both render the *same* chrome (back-to-Library link → `PaperPipeline` → `PaperMetaHeader`) and differ
only in the body below it. The owner's umbrella vision (§10): **one first-class Paper, the stages as
tabs over it** — drop a PDF once, then move Skill Match → Reproduce → Score without the surface
feeling like three different pages. The handoffs are now proven (s38/s39), so per §10's lean answer it
is time to *collapse into the shell*.

**Goal:** one umbrella route — `/paper/[id]` — that holds the persistent chrome and swaps only the
stage body beneath it, with the pipeline strip acting as the stage nav. The per-paper Skill-Match and
Reproduction routes fold into it; the entry/showcase navs stay.

## 2. Scope

In:
- A new **`/paper/[id]`** route + a **`PaperShell`** client component: persistent chrome (Library
  back-link + `PaperPipeline` as the stage nav + `PaperMetaHeader`) over a **stage body that swaps**
  by `?stage=`.
- Three stage bodies, extracted from today's surfaces into shared, self-contained components:
  - **Skill Match** — the saved routed inventory (today's `SavedSkillMatch` → `Inventory`).
  - **Reproduce** — the matched-skills recap + supplementary-materials intake + the staged Reproduce
    CTA (today's `PaperWorkspace` middle).
  - **Score** — the two-axis score + reproducibility heatmap, **ghosted "awaiting reproduction"**
    until the live drive lands. **Rebuilt as a faithful skeleton (D-c)** mirroring the real
    `PaperDetail` score region — the two `Axis` cards (matching class names/dims), a `FindingsBanner`
    ghost row, and a heatmap grid using the real `ReproHeatmap` cell dimensions
    (`grid-cols-[repeat(auto-fill,minmax(96px,1fr))]`, content cells, the static tier legend) instead
    of today's loose `size-6` dashed squares — so when the live drive lands it fills the identical
    skeleton with zero reflow.
- The pipeline strip drives the active stage **via the URL** (`?stage=skill-match|reproduce|score`),
  so stages are deep-linkable and the back button works; **all three pills become navigable** inside
  the shell (Score is reachable and shows its ghost, instead of being a dead pill).
- **Re-point** every internal link that targeted the old per-paper routes to `/paper/[id]` (Skill
  Match forward button, the pipeline `links`, `your-reproductions`, the Library Papers tab).
- **Fold the old routes**: `/skill-match/[id]` and `/reproduction/paper/[id]` redirect into the shell
  (so any saved pill/bookmark still resolves) — no second per-paper code path.

Out (later, separate owner-gated steps — keep as-is for now):
- **`/skill-match`** (the *live drop* entry — transient PDF blob, no Paper id yet) stays its own
  surface. Dropping + routing + Save/Reproduce there is what *creates* the Paper anchor and enters the
  shell. The shell is for a **saved** Paper.
- **Recover data** as a shell stage — deferred to step (a) (the pdf.js viewer + in-viewer region
  capture). Until that renderer swap exists there is nothing Paper-anchored to show, so `/extract`
  stays the standalone nav. The shell's stage model is built to accept a 4th tab without a rewrite.
- The **live reproduction ingest+drive+grade** backend — step (c). The Reproduce CTA stays staged
  ("Live run coming") and the Score stage stays ghosted until that contract lands.
- The showcase surfaces (`/reproduction` spectrum + `/reproduction/[slug]` dogfood detail) — untouched.

## 3. The route + shell

```
/paper/[id]?stage=skill-match            ← default stage when ?stage absent
/paper/[id]?stage=reproduce
/paper/[id]?stage=score
```

`app/paper/[id]/page.tsx` → `<PaperShell id={id} />` (client). The shell:

```
← Library
┌───────────────────────────────────────────────────────────┐
│  PaperPipeline   ● Skill Match → ○ Reproduce → ○ Score     │  ← stage nav (active = ?stage)
├───────────────────────────────────────────────────────────┤
│  PaperMetaHeader   title / authors / Year·Journal… / ids   │  ← persistent
├───────────────────────────────────────────────────────────┤
│                                                            │
│            { active stage body }                           │  ← swaps by ?stage
│                                                            │
└───────────────────────────────────────────────────────────┘
```

- Chrome above the divider is **identical to s39** (same components, same order). Only the body swaps,
  so the shell looks like the s39 reproduction workspace with the stage content made switchable.
- `PaperShell` resolves `wselect.paper(ws, id)`; the not-in-Library empty state is reused verbatim
  from the two surfaces being folded.
- Stage = `searchParams.stage` (validated against the three keys, default `skill-match`). Switching
  stage is a shallow URL change (`router.replace`, scroll-preserved) — the shell stays mounted, only
  the body re-renders. `useSearchParams` is read inside a `<Suspense>` boundary per Next 16 App
  Router; the route is already dynamic (`[id]`), so no static-generation concern.

### Pipeline as stage nav
`PaperPipeline` keeps its current `links` API but the shell passes all three:
`{ "skill-match": "/paper/<id>?stage=skill-match", reproduce: "…", score: "…" }`. The `current` prop
tracks `?stage`. The forward "Reproduce →" button stays on the Skill-Match stage as the prominent
next-step (it just switches stage now instead of routing across pages). No change to
`pipeline.tsx`'s internals — it already renders a link-or-static pill per stage.

### Stage bodies (refactor, not rewrite)
Move the existing bodies into `components/paper/stages/`, each taking `{ paper }`:
- `skill-match-stage.tsx` ← `SavedSkillMatch`'s `Inventory` (+ its "drop again for the per-figure
  breakdown" note).
- `reproduce-stage.tsx` ← `PaperWorkspace`'s `MatchedSkills` + `SupplementsSection` + `ReproduceStep`.
- `score-stage.tsx` ← `PaperWorkspace`'s `AwaitingScore` + `AwaitingHeatmap`.

`SavedSkillMatch` and `PaperWorkspace` components are deleted (their chrome moves to `PaperShell`,
their bodies move to the stage files). The old route files become redirects (§4).

## 4. Folding the old routes

- `app/skill-match/[id]/page.tsx` → `redirect("/paper/" + id)` (server redirect; lands on the default
  Skill-Match stage).
- `app/reproduction/paper/[id]/page.tsx` → `redirect("/paper/" + id + "?stage=reproduce")` (preserves
  the intent — that route always meant "the reproduce workspace").
- Internal links updated to point at `/paper/[id]` directly (so redirects are only a safety net, never
  the hot path):
  - `skill-match.tsx` `handleReproduce` → `/paper/<id>?stage=reproduce`.
  - `saved-skill-match`/`paper-workspace` pipeline `links` → folded into `PaperShell` (those files go
    away).
  - `your-reproductions.tsx` card href → `/paper/<id>?stage=reproduce`.
  - Library Papers tab "open" → `/paper/<id>` (Skill-Match stage) — confirm the current target in
    `app/library/page.tsx` and re-point.

## 5. Invariants

- **U1 — Chrome parity.** The above-divider chrome (Library link → `PaperPipeline` → `PaperMetaHeader`)
  renders identically on every stage; switching stages never reflows or re-mounts it.
- **U2 — Deep-linkable + back-button.** `/paper/<id>?stage=score` loads straight onto the Score stage;
  browser back returns to the prior stage. An absent/invalid `stage` falls back to `skill-match`.
- **U3 — No new behaviour.** Every stage body is byte-equivalent in behaviour to today's surface
  (supplements add/remove/persist, idempotent, the same ghosts, the same "graded example" link). This
  step is a *consolidation*, not a feature — the only new thing is the tabbed chrome.
- **U4 — Additive to showcases.** `/reproduction` (spectrum + "Your papers") and `/reproduction/[slug]`
  are untouched; the default index stays byte-identical when no user papers exist (s38 property holds).
- **U5 — Extensible stage model.** The stage list is data-driven so step (a) can add a `recover` stage
  (4th pill + body) and step (c) can light up Score without reshaping the shell.
- **U6 — Score ghost = real skeleton.** The ghosted Score stage uses the *same* layout primitives and
  Tailwind dimensions as the real `PaperDetail` score region (axes, findings row, 96px heatmap cells,
  legend). The live drive (step c) fills the identical skeleton with zero reflow — no second layout.

## 6. Build plan

1. `PaperShell` + `app/paper/[id]/page.tsx` — chrome + `?stage` router + Suspense + empty state.
2. Extract the three stage bodies into `components/paper/stages/*`; delete `SavedSkillMatch` +
   `PaperWorkspace` (chrome lifted to the shell).
3. Re-point internal links (§4) + add the two redirect pages.
4. Verify gates: `npx tsc --noEmit` · `npx vitest run` (no logic change → 99 green) · `npx eslint .`
   (0 err). Browser-verify desktop on :3001 vs the live BE: match a paper in `/skill-match` → Reproduce
   → lands on `/paper/<id>?stage=reproduce`; pipeline pills switch stages without chrome reflow; drop a
   supplement on Reproduce → persists → Library shows the count; Score stage shows the ghost; deep-link
   `/paper/<id>?stage=score` loads onto Score; old `/skill-match/<id>` + `/reproduction/paper/<id>`
   redirect in; `/reproduction` index + a `/reproduction/[slug]` showcase unchanged; console clean.

## 7. Decisions (RESOLVED by owner, 2026-06-21)

- **D-a — Route name `/paper/[id]`** ✓ — the new `/paper/[id]` names the first-class Paper the umbrella
  is built on, and reads cleanly as the stages tab beneath it; the old per-paper routes redirect in.
- **D-b — Recover data deferred** ✓ to step (a) (the pdf.js viewer) rather than a placeholder 4th tab —
  a Recover stage with no in-viewer capture is a hollow tab; the stage model leaves room for it (U5).
- **D-c — Score as its own (ghosted) stage** ✓ — it is the 3rd pipeline pill (1:1 pill→tab), and it
  splits the over-long Reproduce scroll (inputs on Reproduce, the graded output on Score). **Owner
  steer:** the ghost must be a **faithful skeleton** of the real `PaperDetail` score region, not loose
  dashed boxes (see §2/§3 + U6).
- **D-d — Keep the entry/showcase navs** ✓ (Skill Match = drop entry, Reproduction = showcase + Your
  papers, Recover data = standalone, Library = all papers); the shell is the *per-paper* workspace they
  funnel into — resolves §10's open question with its own lean answer (don't nuke the nav; unify the
  per-paper surfaces).
```
