# LANE 3 — WRAP

**Branch:** `agent/fe-polish/l3` · **Worktree:** `/home/deploy/work/selom-lane3` · forked from `f43d97f`
**Closed:** 2026-07-25 08:02 +0000 (UTC) — i.e. 18:02 +1000
**Commits (2, both green, none pushed):**

| Commit | ID | What |
|---|---|---|
| `f4f9ca3` | `L3-01` (A24) | The stage sizes the artboard, not a viewport guess |
| `3398c37` | `L3-02` (A25 · B13) | Retire the inert palette strip |

**Not merged, not pushed, not rebased** — the lead drives the train (`Lane 1` → `Lane 3` → `Lane 2`).

---

## Status per ID

| ID | Status | Note |
|---|---|---|
| `L3-01` | **DONE** | A24 → FIXED. Executable ratchet in place; browser confirmation is `D-5` below. |
| `L3-02` | **DONE — retired** | B13 → FIXED. A25 → **PARTIALLY** fixed: three of its four placeholders sit outside this lane's glob and are re-filed on the finding (see *Residuals*). |
| `L3-03` | **DROPPED** | Pre-decided at the Phase 0 gate (DECISIONS #12 — lucide stays). No icon work was done, correctly. |
| `L3-04` | **DONE (reporting row)** | §D turned into 12 runnable checks below. Nothing was closed on my word — a browser cannot run in this worktree. |

### `L3-01` — the artboard hero was clipped inside its own stage

The white card kept the pre-shell `height: min(74vh, 720px)` after it became a flex child of a host
whose height is only what the shell's bands leave over: it asked for 720px inside a 548px stage
(measured 1512×1050 by the review), so ~24% of the hero — x-axis title, legend — sat below the visible
area with the document itself not scrolling.

The inline height is gone. A responsive figure now **stretches to the stage** (`items-stretch`,
bracketed by `min-h-[20rem] max-h-[56rem]`); a min/max can only resize the card *away* from the
stage's height, never overflow it the way an exact height does. A **fixed**-size figure (numeric
`layout.width` — ERG trace grids, multi-panel) is untouched: declared size, top-aligned, stage
scrolls, which is the correct behaviour there.

The rule is one pure `artboardFrame(fixed)` in `app/frontend/lib/ui/artboard-frame.ts`, consulted by
the **two** hosts that render the artboard (`CanvasShell` and the classic `EditorWorkspace`, the one
`/extract` uses), so they cannot drift apart again.

### `L3-02` — retire, not restyle

Retiring was the honest branch of the kickoff's either/or. Making it "real" means deriving
`/layout/colorway`, naming it, and titling each swatch — but that control **already exists**,
accessible and spec-derived, three files away in the inspector's Style tab
(`panels/style-panel.tsx:599-627`). A second read-only copy would spend the same ~34px to restate it,
in the editor `L3-01` had just shown to be height-oversubscribed. So: no colour-only claim, no *wrong*
claim (it hardcoded Okabe–Ito regardless of the spec), no `aria-hidden` region, and the artboard gets
its pixels back. A **live** palette board is welcome back as a real control; when it lands it must
derive from the spec exactly as B13 specifies.

---

## Ratchets added (the durable half)

`app/frontend/lib/ui/artboard-frame.test.ts` — 5 tests. Both findings were **CSS-only claims with no
gate**, which is why they shipped: `fe-build` cannot see layout and no browser is drivable in a lane.
So the invariants are executable now, and **both were verified to actually fail**, not assumed to:

| Ratchet | Proven red by |
|---|---|
| A responsive artboard carries no height of its own; no `vh` in the host or the rule | restoring `height: "min(74vh, 720px)"` → 2 of 5 tests fail |
| No band under `components/figure/shell/**` renders "coming soon" | restoring `palette-strip.tsx` → 1 of 5 tests fails |

The chrome guard strips comments before scanning, so a comment recording *why* a band was retired
doesn't read as the band coming back.

---

## Verify ledger

Command (the only one), run raw with the exit code captured from `verify.sh` itself, never through a
pipe:

```bash
export SELOM_PYTEST_WORKERS=2
./scripts/verify.sh --fe --fast
```

| Run | Result |
|---|---|
| Baseline, before any edit | **PASS** — hygiene · fe-lint · fe-types · fe-test · 53 files / 541 tests / 28s |
| After `L3-01` | **PASS** — 54 files / 545 tests |
| After `L3-02` (final, `EXIT=0`) | **PASS** — 54 files / **546** tests / 24s |

`fe-lint` reports **12 warnings, 0 errors — all pre-existing and unchanged** by this lane (they are in
`figure-canvas.tsx`, `annotations-panel.tsx`, `controls.tsx`, `marks-panel.tsx`, `property-panel.tsx`,
`gene-set-browser.tsx`, `data-panel.tsx`, `sweep-form.tsx`, `lib/reproduction/api.ts`).

**Two gates this lane could NOT run, and they matter here:**
- `fe-build` — `SKIP` by construction. Turbopack rejects the out-of-root `node_modules` symlink. It is
  the only gate that catches SSR/integration breaks. **Merge-train step on the lead's main checkout.**
- **the browser** — no `next dev` in a worktree either. Every layout claim in this lane is therefore
  *reasoned + unit-pinned, not observed*. That is exactly what §D below is for.

`lib/figure/ssr-plotly-import.test.ts` is green; nothing in this lane touched a dynamic import.

---

## §D — the browser-check list the lead must run on `main` after rebase

§D's 12 bullets were **arithmetic-backed predictions from the CSS that no browser ever observed**
(the review says so itself). Below, each is a runnable check: what to load, at what viewport, and the
signature that proves or disproves it. **Close or re-file each one honestly — none of them are closed
here.**

**Setup, once.** Real backend and a real figure, not `dev:mock` — a mock proves the wire, not the
content, and these are content-shaped layout claims (long axis titles, real legend text). Run
`uv run uvicorn main:app --reload` (`:8000`) + `npm run dev` (`:3000`) on the **main checkout**, and
drive a real run to a figure at `/p/<project-id>`. Sizes below are the browser **viewport** (devtools
device toolbar → Responsive → type the numbers), not the window. **Desktop only — never check a
mobile width, Selom has no mobile.**

**Read this first — the build state moved under §D.** The annotation layer is now behind
`NEXT_PUBLIC_ANNOTATION_LAYER` (**off by default**, `lib/config/env.ts:36`). With the flag off the
inspector has **no Annotate tab** (max 6 tabs, `property-panel.tsx:81`) and the tools rail is
**Select only** — the three draw tools *and* the two dead Shape/Guide slots all disappear together
(`tools-rail.tsx:42`). So: `D-2` is unreachable in a default build, and `D-1`/`D-6`/`D-7` lose the
half that motivated them. Anything you check with the flag **on** is testing **deferred Plan C
territory** — file the result against Plan C's spec, do not close it as shipped-and-fine.

| # | §D bullet | Status going in |
|---|---|---|
| D-1 | Inspector tab strip | flag changes it — check the **6**-tab case, which is now the max |
| D-2 | Annotate panel body | **unreachable** in a default build (flag off) |
| D-3 | ExportMenu popover + cloud row | unchanged, run as written |
| D-4 | CanvasShell four-region frame | **changed by `L3-02`** |
| D-5 | ArtboardHost — the hero | **changed by `L3-01`** — highest value |
| D-6 | ToolsRail | flag changes it — new question below |
| D-7 | Marks tab visibility | flag changes half of it |
| D-8 | CloudImportMenu | **run AFTER Lane 2 merges** — it owns that surface |
| D-9 | AI panel overlay vs inspector dock | unchanged, run as written |
| D-10 | Frozen / read-only inspector | unchanged, run as written |
| D-11 | `/extract` editor | **changed by `L3-01`** — second host of the same fix |
| D-12 | scRNA assemble intake | already `verified=True`, nothing to render |

---

## ✅ RESULTS — run in a real browser 2026-07-25, on merged `main`

Run with **`scripts/browser-verify.sh`** (real backend `:8152` + real frontend `:3152` + the real
EYG_28 DE export). **The checks are now EXECUTABLE and live in
`app/frontend/e2e/browser-verify/*.spec.ts`** — this table is the record, the specs are the ratchet.
Re-run them; do not re-reason them.

| # | Verdict | The measured fact |
|---|---|---|
| **D-5** | **PASS — A24 is fixed** | `overflow=0` and `card = stageClient − 32` **exactly** (Δ0) at all three viewports. `stageClient` = **402 / 502 / 720**. x-axis title *and* legend both inside the stage. A24's signature (`card ≈ min(0.74×vh, 720)`) would have been 592/666/720 — it is not. |
| **D-5** floor | **KEEP `min-h-[20rem]`** | The floor never engages: the shortest real stage is **402px**, 50px above the 352px engagement point. The wrap's arithmetic (~400px) was right. Do **not** lower it. |
| **D-5** 88rem cap | **NOT EXERCISED — cap is unreachable** | The stage is only **938px** wide even at 1920×1080, so the `88rem` (1408px) cap never engages and centring could not be observed. It would need a ~2400px viewport. The card is flush (`gutters L0/R0`) because it fills the stage, not because it is centred. |
| **D-5** legibility | **❌ FAIL — new finding, a WIDTH defect** | At 1280×800 the plotting area is **90px**, not the ~506px §D assumed. Chain: viewport 1280 → main 1024 → stage 298 → card 266 → **plot 90**. Fixed columns — sidebar 256 + workrail (`w-64`) 256 + tools rail 48 + inspector dock 330 = **890px, 70% of the viewport**. The hero gets 21%, the plotting area **7%**, and gene labels overlap into an unreadable cluster. Independent of `L3-01`, which is working exactly as specified. Legible at 1920 (718px of plot). Evidence: `test-results/browser-verify/d5-1280x800.png`. |
| **D-4** | **PASS — the retirement held** | No band below the artboard row; zero "Palette board / coming soon" matches. Bands at 1280: **151px** command cluster + **30px** ToolContextStrip + **402px** artboard row. The CommandBar cluster wraps to **3 rows (74px)** at 1280 and is `shrink-0`, so that 74px is charged to the hero. The ToolContextStrip fits on **one** line — §D predicted this correctly. |
| **D-1** | **PASS — §D's prediction DISPROVEN** | 6 tabs, dock 305px, every track **48px**; every label fits with **13–26px of slack** (`Legend` tightest at 35px in 48px). §D predicted `Legend` overflowing by ~4px and `Marks` by ~1px at 6 tabs — it does not. The flag-off case is fine. |
| **D-7** | **PASS** | A volcano carries skill-emitted gene labels → **Marks is present** (Style · Axes · Legend · Data · Marks · Page). That is the transition §D cared about, and it behaves. |
| **D-6** | **FOUNDER CALL (reported, not closed)** | The rail ships as a **48px column holding exactly one always-pressed button** (`Select`, `aria-pressed=true`). That is 48px of the 266px the hero gets at 1280 — the same §3.3 "fixed chrome must justify its pixels" question the palette strip failed. |
| **D-3** | **PASS** | Popover bottom **622** ≤ shell bottom **776** — not clipped. Popover height 337px (§D estimated ~318px). |
| **D-9** | **PASS** | AI panel at `left=920`, `z=40`; artboard right edge **895** → no overlap, so the artboard cannot poke through. A reachable close affordance is present. |
| **D-10** | **PASS + a founder call** | A frozen figure sizes identically through the same `ArtboardHost`: `overflow=0`, `card = stageClient − 32` (444/412). **"Edit a copy" appears twice on one screen** (frozen command cluster *and* the inspector dock) — a duplicated affordance for a single action. |
| **D-11** | **NOT RUN** | `/extract` needs manual canvas calibration (four reference-tick clicks + their values) before the editor renders — a contained next step now the harness exists, but it is not a selector fix. |
| **D-2**, D-1/D-6/D-7 flag-on | **NOT RUN — deferred Plan C** | Reachable with `ANNOTATION=on scripts/browser-verify.sh`; results file against the annotation remediation spec, never as shipped-and-fine. |
| **D-8** | **NOT RUN** | Lane 2's cloud surface; unchanged from its own gate. |
| **D-12** | **N/A** | Backend-only, no FE surface. |

**Also found while building the harness — a blocking crash on the primary flow, now fixed
(`3e171e5`):** `datasets.qc` carries two different shapes and `fromApiDataset` cast whichever
arrived into the FE's `QcReport`. The real upload path stores the *engine's* report (no
`nObs`/`nVar`), every consumer formats `qc.nObs.toLocaleString()`, so **dropping any real file took
the whole app to the error overlay.** Invisible to every prior gate because `dev:mock` skips
`uploadDataset` entirely.

---

### D-5 · The artboard is the hero — does it still clip? *(run this one first)*

- **Load:** `/p/<id>`, a figure open, a **responsive** figure (volcano / UMAP / DEG bar — anything
  without a numeric `layout.width`).
- **Viewport:** `1280×800`, then `1440×900`.
- **Do:** devtools console —
  ```js
  // `.bg-artboard` also matches the Figure-data preview and the compare panes — assert ONE match
  // (the views are mutually exclusive, so a count > 1 means you are not on the figure editor).
  const cards = [...document.querySelectorAll('.bg-artboard')]
    .filter(el => el.parentElement.classList.contains('overflow-auto'));
  console.assert(cards.length === 1, 'expected exactly one artboard stage', cards);
  const card = cards[0], stage = card.parentElement;
  ({ stageClient: stage.clientHeight, stageScroll: stage.scrollHeight,
     card: Math.round(card.getBoundingClientRect().height),
     overflow: stage.scrollHeight - stage.clientHeight })
  ```
- **PASS:** `overflow === 0` **and** `card ≈ stageClient − 32` (the stage's `lg:p-4` gutter, 16px top
  + bottom; it is `p-3` → 24 below 1024px, which we do not check). The figure's **x-axis title and
  legend are visible without scrolling inside the stage.**
- **FAIL (the A24 signature returning):** `card ≈ min(0.74 × innerHeight, 720)` with
  `stageScroll > stageClient`.
- **Also confirm:** the card is still **horizontally centred** when it caps at `88rem` (1408px) — only
  visible above ~1470px of stage width, so check at `1920×1080` too; and that the figure is still
  **legible** at 1280 (tick labels, legend, colour bar at ~506px of plot width, per §D's own number).
- **New risk this fix introduces — only a browser can settle it:** the floor is `min-h-[20rem]`
  (320px). If a stage is ever shorter than ~352px the card hits the floor and the stage scrolls
  instead of shrinking further. Report `stageClient` at both viewports; if it is anywhere near 352px,
  the floor is wrong for real screens and should be lowered.

### D-4 · CanvasShell frame — did retiring the band actually buy the artboard its pixels?

- **Load / viewport:** as D-5, `1280×800` and `1440×900`.
- **PASS:** there is **no band below the artboard row** — the shell's bottom edge is the artboard +
  inspector row. No swatch row, no "Palette board — coming soon".
- **Then measure what the remaining fixed chrome costs**, because that is the §3.3 principle and the
  reason `L3-01` was needed:
  ```js
  const shell = document.querySelector('.bg-artboard').closest('.overflow-hidden');
  [...shell.children].map(el => [el.className.slice(0, 40), el.getBoundingClientRect().height]);
  ```
  Report the **CommandBar's height and how many rows it wrapped into at 1280** — it is `shrink-0`, so
  every wrapped row is stolen from the artboard inside a `min-h-[520px]` box. Also whether
  `ToolContextStrip`'s ~130-char hint wraps to a second line at 1280 (§D predicted it fits on one at
  918px of cluster width — worth ~16px).
- **Judgement call for the founder, not a bug:** with the palette band gone, does the shell still read
  as *mostly unbuilt*? Remaining placeholders are the `ToolContextStrip` (static prose) and — flag-on
  only — two dead rail tools. See *Residuals*.

### D-11 · `/extract` — the second host of the `L3-01` fix

- **Load:** `/extract`, drop a single bar/line/scatter panel image, run the recovery so the editor
  renders. (A live backend `POST /api/extract/chart` is needed; the MSW handler at
  `mocks/handlers.ts:119` is acceptable **only** to reach the editor — the layout question is about
  the editor, not the extracted numbers.)
- **Viewport:** `1280×800` and `1440×900`.
- **Do:** the same console snippet as D-5.
- **Why it is a separate check:** this page's stage is squeezed between a header, an amber
  vision-grade strip **and** a `StatsPanel` at the bottom (`defaultOpen`), so it is the **shortest
  stage in the app** and the most likely place for the 320px floor to engage. If `overflow > 0` here,
  say so — that is the honest trade `L3-01` made (scroll a too-short stage rather than collapse the
  card), not a regression, but the founder should see it.
- **Also:** §D asks whether `/extract` still looks deliberate after the gutter went `p-6 lg:p-10` →
  `p-3 lg:p-4` (the artboard no longer floats with breathing room on the dark stage). Unchanged by
  this lane — still worth an eyeball.

### D-1 · Inspector tab strip — the 6-tab case is now the worst case

- **Load:** two figures. (a) a plain volcano/UMAP → **5 tabs** (Style · Axes · Legend · Data · Page);
  (b) a figure **with marks** — an ERG trace grid, a microscopy panel with a scale bar, or a heatmap
  with skill-emitted labels → **6 tabs** (+ Marks).
- **Viewport:** `1280×800` (the dock is a fixed `w-[330px]`, so the viewport barely matters — but
  confirm the dock is not being squeezed at 1280).
- **Do:**
  ```js
  const list = document.querySelector('[role="tablist"]');
  [...list.children].map(t => [t.textContent, t.getBoundingClientRect().width,
                              t.querySelector('span').getBoundingClientRect().width]);
  ```
- **The arithmetic to disprove:** 329 dock content − `px-3` (24) − `p-1` (8) − `gap-0.5` × 5 (10) =
  287 / 6 = **47.8px per track**, minus `px-2.5` (20) = **27.8px of label box**. §D measured
  "Legend" ≈ 32px and "Marks" ≈ 29px at `text-[10px]`. **So the prediction that survives the flag is:
  at 6 tabs, "Legend" overflows its track by ~4px and "Marks" by ~1px**, into 2px gutters — labels
  touching, not merely tight. `TabsTrigger` is `whitespace-nowrap` with **no** `truncate`, so text
  spills rather than clipping (`components/ui/tabs.tsx:31`).
- **PASS:** every label's own width ≤ its trigger's content box; no visual collision between
  neighbouring labels.
- **FAIL:** any label wider than its track → the A23 fix (shorten the label + add `truncate`, or
  icon-only past 6) applies to **`Legend`**, not just to `Annotate`. Note `property-panel.tsx` is
  Plan C territory — re-file, do not fix in-place at the train.
- **Flag-on variant (Plan C only):** with `NEXT_PUBLIC_ANNOTATION_LAYER=enabled`, the same figures give
  6 and **7** tabs — §D's original HIGHEST-RISK case (40.7px/track vs a ~43px "Annotate").

### D-6 · Tools rail — a one-button rail is a new question

- **Load / viewport:** `/p/<id>` with a figure, `1280×800`.
- **Default build (flag off) — check what actually ships:** the rail is a 48px column containing
  **exactly one** button (Select, `aria-pressed`, `bg-accent/60`). **Does a 48px vertical column with a
  single always-pressed button read as a toolbar, or as a leftover gutter?** This is *not* in §D — §D
  described a six-tool rail — and it is the honest question for the shipped build. If it reads as
  dead space it is the same §3.3 complaint as the palette strip, and belongs in the same bucket.
- **Then, unchanged from §D:** confirm Select's pressed state reads as the active mode, and that the
  icon-only rail is decipherable (`title` attribute only, no visible labels).
- **Flag-on variant (Plan C only):** confirm the disabled Shape/Guide at `opacity-40` are visibly
  distinct from the enabled draw tools without reading as a rendering failure, and that the read-only
  ("paper") disabled state — `readOnly` → no store → all three draw tools disable — does **not** look
  identical to the never-coming Shape/Guide.

### D-7 · Marks tab visibility (`nonSelomAnnotationItems`)

- **Default build:** open a figure with **no** scalebar and **no** skill labels → **Marks must be
  absent** (5 tabs). Open an ERG/microscopy figure that *has* a scalebar → **Marks appears** (6 tabs).
  That transition is the one place a wrong result changes the tab-strip width class.
- **Flag-on variant (Plan C only):** the half §D actually cared about — add a significance bracket
  from the rail and confirm the tab count **stays** where it was (Marks must *not* appear for a Selom
  annotation) and the new item is listed **only** in Annotate, never double-listed in Marks.

### D-3 · ExportMenu popover — clipped by the shell's `overflow-hidden`?

- **Load / viewport:** `/p/<id>`, figure open, `1280×800` (the worst case: the `ml-auto` action group
  wraps the command cluster to a second row) — **and** with the VersionBar present.
- **Do:** open the Export menu, then
  ```js
  const pop = document.querySelector('[class*="w-72"]');
  const box = pop.closest('.overflow-hidden');
  ({ popBottom: pop.getBoundingClientRect().bottom, boxBottom: box.getBoundingClientRect().bottom });
  ```
- **PASS:** `popBottom ≤ boxBottom` — nothing clipped. **FAIL:** the popover is cut off; the clipped
  region would be the primary `Export PNG/SVG/PDF` button. §D estimated ~318px of popover in a
  ≥520px shell so it *probably* fits — "probably" is why this must be eyeballed.
- **Also:** does the disabled "Export to cloud · Coming soon" row read as *intentionally disabled* or
  as broken? Its "Coming soon" computes to ≈2.4:1 contrast at 11px (A25) — **unreadable, still open,
  and not in this lane's territory.** See *Residuals*.

### D-9 · AI panel overlay vs the inspector dock

- **Load / viewport:** `/p/<id>`, figure open, `1280×800`. Open the AI panel (header "AI" button).
- **Check:** a `fixed right-0 top-14 w-[360px] z-40` panel fully occludes the 330px inspector dock
  plus ~30px of artboard gutter. Confirm (a) the panel's **close affordance is reachable**, (b) the
  left tools rail stays clear, (c) with the AI panel open **and** the export menu open, the artboard
  is `z-[45]` — **above** the panel's `z-40` — so confirm the artboard does not poke through the AI
  panel. Pre-existing owner-directed overlay, but (c) is a real z-order collision to look at.

### D-10 · Frozen / read-only inspector

- **Load:** a **frozen** ("paper") figure — freeze one from the figure toolbar. Viewport `1280×800`.
- **Check:** the centred lock chip + `max-w-[18rem]` copy + "Edit a copy" button still centre in the
  330px dock at full shell height, and the frozen command cluster ("Frozen — read-only" +
  "Edit a copy" in the top bar) does not duplicate-affordance confusingly with the dock's button.
- **Note for D-5's sake:** a frozen figure still renders through the same `ArtboardHost`, so re-run
  D-5's snippet here too — `readOnly` changes gestures, not sizing, and that should be visible.

### D-8 · CloudImportMenu — **run after Lane 2 merges**

Lane 2 owns `components/intake/**` and is actively changing this surface (`L2-01`…`L2-06`: the
provider registry, the `Soon` chips, the labelled busy state). Checking it before that lane lands
measures a surface that is about to change. After the merge, run §D's four sub-checks verbatim at
`1280×800` on `/p/<id>` → Data stage: (a) the URL input's placeholder fits its ~218px without
ellipsis; (b) the `z-50` popover does not cover the Dropzone above or the dataset rows below while
open; (c) the trigger reads as a peer of the drop-zone, not a stray control; (d) the "coming soon"
note below the provider list does not push the popover past the fold.

### D-2 · Annotate panel body — **unreachable in a default build**

Requires `NEXT_PUBLIC_ANNOTATION_LAYER=enabled`. If Plan C's spec is being worked, run §D's checks
then: the `AddButton` two-line labels at ~253px (hint span **is** `truncate` — confirm it is not
clipped mid-word at 11px), the `StarPicker` tier row (`min-w-9 flex-1` — confirm it does not wrap to a
ragged second line), a long `AnnotationRow` label pushing the Hide/Remove buttons out, and whether
the transparent-bordered `TextEditor` reads as an editable field at rest. **File against Plan C, not
as a shipped-surface defect.**

### D-12 · Multi-sample scRNA assemble intake

Already `verified=True` in §D — `11a115f` is backend-only, there is no FE surface. **Nothing to run.**
(It becomes checkable only when Lane 2 lands `L2-05`, the user-reachable surface for
`/data/assemble-scrna`.)

---

## Residuals — things I found but did not own

1. **A25 is only partially closed.** Three placeholders remain, all outside this lane's glob:
   `shell/tool-context-strip.tsx` (~30px of static prose that never changes while Select is the only
   mode); `shell/tools-rail.tsx`'s two disabled Shape/Guide slots (flag-on only, and their `title`
   hint is unreachable because a `disabled` button takes no hover/focus for many users);
   `export-menu.tsx:223-233`'s disabled "Export to cloud · Coming soon" row over a client
   (`lib/cloud/api.ts:55 exportToCloud`) with **no caller anywhere**, including its ≈2.4:1 contrast.
   Re-filed on the A25 entry. **The export row sits in the cloud surface Lane 2 is working in — fold
   it into that lane rather than racing it.**
2. **The tools rail ships as a one-button column** in the default build (flag off). Not a §D bullet,
   because §D predates the gating. It is the same "fixed chrome must justify its pixels" question the
   palette strip failed — see `D-6`. Founder call, not a defect.
3. **A24 has a SIBLING the review missed — `components/project/views/figure-data-view.tsx:204-207`.**
   Found while validating `D-5`'s selector. The Figure-data stage's preview is a near-verbatim copy of
   the artboard card — same class string — carrying `height: "min(70vh, 680px)"` inside a
   `min-h-0 flex-1 items-start overflow-auto p-6` container. That is **exactly the A24 shape**: a
   viewport-relative pixel height inside a flex host whose own height is only what its siblings leave
   over, so the preview clips the same way whenever the stage is shorter than 70vh. Lower stakes (it
   is a read-only preview, and the surrounding chrome is lighter than the editor's), but it is the
   same defect and it will now drift from the rule the editor follows. **Outside this lane's glob**;
   the fix is a two-line change — consult `artboardFrame(fixed)` from `lib/ui/artboard-frame.ts`
   instead of the inline height, and swap `items-start` for the returned `alignClass`. Note the width
   cap differs on purpose there (`56rem` vs the editor's `88rem`), so `artboardFrame` would need a
   width argument, or that call site keeps its own `maxWidth` and takes only the height behaviour.
   Re-filed on the A24 entry so it is not lost.
4. **`min-h-[20rem]` is a judgement, not a measurement.** I chose the floor by arithmetic (min shell
   520px − CommandBar − ToolContextStrip ≈ 400px of stage, so it should never engage in the real
   shell) and could not confirm it in a browser. `D-5`/`D-11` report the real numbers; lower it if a
   real stage comes anywhere near 352px.

## Out-of-glob edits — declared

The kickoff's territory is `shell/{artboard-host,palette-strip}.tsx` + `lib/ui/**`. Two edits fall
outside it; both were unavoidable and neither file belongs to Lane 1 (backend) or Lane 2
(`lib/cloud/**`, `components/intake/**`, `lib/projects/sync.ts`, `components/project/data-panel.tsx`):

- `components/figure/shell/canvas-shell.tsx` — the import, the `<PaletteStrip />` call site, and the
  region doc-comment. **A component cannot be retired while it is still mounted**; leaving the call
  site would have made `L3-02` a no-op that also broke the build.
- `components/project/views/figure-view.tsx` — **one comment line** that named the deleted strip
  ("the tools rail + palette are placeholders"). Zero behaviour; a comment naming a deleted component
  is exactly the doc-rot the repo's ratchet ladder exists to prevent.

**Nothing behind `NEXT_PUBLIC_ANNOTATION_LAYER` was touched**, and neither `property-panel.tsx` nor
`figure-canvas.tsx` was modified — Plan C's territory is intact.

## Merge-train notes for the lead

- Expect a **file deletion** (`app/frontend/components/figure/shell/palette-strip.tsx`) in the rebase.
- Both `docs/next-session-plan/plan.md` and `docs/milestone-review-2026-07-25/findings.md` are touched
  by every lane's status flips → **textual conflicts are likely and are mechanical**; resolve by
  keeping every lane's row. A conflict in `app/frontend/**` from this lane would be a surprise.
- Run the **full** `scripts/verify.sh` (no arguments) on the rebased result — `fe-build` is the gate
  no lane could run, and this lane changed how the artboard is sized on **two** pages (`/p/<id>` and
  `/extract`).
- Then `D-5` → `D-4` → `D-11` before anything else: they are this lane's own claims, and they are the
  three §D bullets whose text is now out of date.

## Housekeeping

- No dev server, no backend, no browser was started in this worktree — nothing to kill.
- `LANE-KICKOFF.md` is deliberately left **untracked** (as the lead created it). This file **is**
  committed, so the §D list survives the rebase and a worktree teardown.
