# Pillar 2 slice 5 — annotation layer REMEDIATION spec

Status: **SPEC — awaiting review** · 2026-07-25 18:0x +1000 (Sydney)
Extends `docs/pillar-2-direct-manipulation/spec.md` §5 slice 5. Not a rewrite — slice 5 shipped
(`d06a28b`) and its **container and primitives are sound**; what it got wrong is *who owns a statistical
claim*.

**Why this document exists.** The annotation layer is **deferred pending a proper plan** — owner intent,
clarified 2026-07-25. `NEXT_PUBLIC_ANNOTATION_LAYER=off` is the *holding mechanism*, **not** a decision
to shelve the work. This is the owed plan, and §6 defines exactly what must be true before the flag
flips.

---

## 1. The diagnosis — three defects, proven in code

The milestone review filed ~20 findings against this layer. They are not twenty problems. They are
**one architectural mistake with three consequences**: the client reimplemented a server capability
*without the data*.

**The backend already does this correctly and completely** (`app/backend/skills/_charts.py`):
`sig_brackets(cat_values, idx_of, means, his, pt_y, comparisons, sig_test)` takes real group pairs,
computes stars from the real values via `compare_groups` (Welch / Student / Mann–Whitney), **stacks**
brackets by `level` so they never collide, and returns `y_top` so the caller grows the axis. The
`comparisons` + `sig_test` params are already user-facing (`lib/catalog/params.ts:374-385`), already
support per-pair overrides (`:**` or `:0.003`), and already ride the staged re-run.

### D1 — a fabricated statistical claim (A9, the severity-setter)
`lib/figure/annotations.ts:166` `starsForP(p)` duplicates the server's `sig_stars` — but the client has
no values, no test, and no p-value. `addSigBracketOps` defaults to the literal string `"*"` when no `p`
is supplied, and **every UI path supplies none**. So the discoverable affordance emits an
unprovenanced significance claim onto a figure destined for a paper. `provenance.actions[]` is never
touched. This is the same class as the campaign's worst blocker (raw-vs-adjusted p) and must be treated
with the same severity.

### D2 — the two paths are geometrically incompatible, so the client's output is often invisible
The shared bar/box helper pins `yaxis.range = [0, y_top*1.08]` where `y_top` includes **error bars and
points** (`_charts.py:295-315`). `bracketGeometry` places the client bracket at **means-only** `yMax`
`+12%`. Therefore a client-added bracket lands either **on top of the error bars** or **above the fixed
range — clipped, rendering nothing.** The client also has no `level` stacking, so repeated adds are
pixel-identical. Combined with there being no post-add confirmation, *"invisible"* and *"it didn't
work"* are indistinguishable to the user. This is why several §C rows read as "nothing happened".

### D3 — one object, two homes, and a silent edit path
Server-computed brackets carry no `selom` tag, so they list under **Marks**; hand-added ones list under
**Annotate**. Same visual object, two tabs, no way to audit which is which — and the Marks text editor
lets a **computed `*` be retyped to `***`**, converting a verified claim into a false one with no trace.

### The meta-lesson worth ratcheting
Slice 5(a) *already specified the right behaviour*: "**ideally** it reads the p-value from the
Statistics table (so the asterisks are *correct*, not hand-typed)". The word **"ideally"** is why it
shipped wrong. **A non-binding intent in a spec is not a ratchet.** Every requirement in §5 below is
paired with an executable guard in §7, or it is not in this spec.

---

## 2. The design principle

> **An annotation that makes a claim is DATA. An annotation that does not is DECORATION.**
> Claims are computed by the server and provenance-stamped. Decoration is a client-side cosmetic patch.

This is the existing figure-edit UX pattern ([[selom-figure-edit-ux-pattern]]) applied to annotations —
cosmetic edits are LIVE client-side; anything requiring data is STAGED with a preview and one re-run —
and it maps cleanly onto the provenance chokepoint already in place.

| | Claim-bearing | Decoration |
|---|---|---|
| Examples | significance brackets + stars, computed p-values | text labels, panel letters (A/B/C), arrows, callouts, highlight boxes |
| Owner | **server** (`comparisons` → `sig_brackets`) | client |
| Path | staged re-run, one recompute | live JSON-Patch |
| Provenance | full: test, p-value, groups | `actions[]` entry, tier `cosmetic` |

## 3. Owner decisions taken (2026-07-25)

1. **Hand-typed stars are ALLOWED but marked `unverified`.** A user reporting a test run in Prism/R
   must have a path — forbidding it makes people fight the tool. But a typed claim must never be
   able to masquerade as a computed one: it carries `verified: false` in provenance **and** is visually
   distinguishable on the figure. Neither half is optional; the marker convention is §5.1.
2. **Selection goes FULL direct-manipulation** — armed tool modes (pick tool → click canvas to place),
   duplicate, cascade offset on repeated adds, numeric x/y fields, keyboard delete/nudge, and
   row↔canvas linking. Larger slice, but it closes ~10 gaps and removes the "one-shot commit" tools-rail
   model that currently surprises every user with an Illustrator expectation.

---

## 4. Gap coverage

§C of the review lists 21 user tasks: 2 already work (undo, hide-without-delete), **4 are editor chrome
owned by Lane 3** (recolour swatch, see-whole-figure, collapse rails, zoom/fit) and are *not* in this
spec. That leaves **15 annotation-layer gaps**, all covered below.

| Slice | Closes | Gaps |
|---|---|---|
| **C1** claims to the server | 6 | bracket over the groups I'm *actually* comparing · bracket + stars move as one · **see** the bracket I just added · bracket carrying a real p-value · tell computed from typed · repeated brackets don't collide (server `level`) |
| **C2** re-run carry-through | 2 | keep brackets + panel letters across a re-run · free text label on a volcano not colliding with the gene-label system |
| **C3** direct manipulation | 5 | which panel row is which canvas item · place where I click · keyboard delete/nudge · duplicate · repeated *decoration* cascades instead of stacking |
| **C4** decoration completeness | 2 | style an annotation (colour/size/arrowhead/weight) · draw a box/highlight + snap to guide |

---

## 5. The slices

### C1 — Claims route to the server *(the honesty blocker; mostly deletion)*
Cheapest and highest-value, because the machinery exists and this slice largely **removes** code.

1. **The Annotate panel's "Significance bracket" becomes a pointer, not a producer.** It opens the
   Figure-data `comparisons` / `sig_test` params (already built, already staged-re-run) with the two
   groups pre-filled from the current selection. Group pickers come free — the server takes real keys.
2. **Retire `starsForP` and `addSigBracketOps` as claim producers.** They survive only behind the
   explicit "typed / unverified" path (5.1). Delete the duplicated star-tier logic; the server's
   `sig_stars` is the single home.
3. **Tag server-computed brackets** with `selom: { kind:"sigBracket", verified:true, … }` so both paths
   list in **one** place, and make the Marks text editor **refuse** to edit the text of a `verified`
   item (D3's silent-retype hole).
4. **Delete the client geometry path for brackets entirely** — no `bracketGeometry`, no `+12%`, no
   clipping (D2). The server positions and stacks; the client renders what it is given.

#### 5.1 The `unverified` marker convention (owner decision 1)
- Provenance: `actions[]` entry, tier `cosmetic`, `{ kind:"sigStars", verified:false, source:"typed" }`.
- On the figure: a typed star group renders with a **distinguishing visual marker** — proposal: the
  stars in the same ink but followed by a superscript dagger `†`, with a figure-caption footnote
  *"† significance reported by the author, not computed by Selom"* emitted into the auto-methods text.
  **This must be decided at build time with `impeccable`** — never colour alone (the palette-strip
  mistake, `A25`).
- The auto-methods text must state which brackets were computed (with the test) and which were reported.

### C2 — A re-run must not silently discard user work
`rerunFigure` (`components/project/hooks/use-figure-run.ts:199-225`) carries **only** gene labels via
`captureCarryLabels`/`carryLabels`; every Selom annotation is dropped, with no warning on the Re-run
button or the StaleBadge.

1. **Carry all `selom`-tagged annotations** across a re-run, not just gene labels.
2. **Identity by `selom.id`, never by `text`.** `lib/volcano/labels.ts` matches annotations **by text
   string** and ignores the `selom` tag — which is why a label reading `RPGRIP1` makes the Statistics
   table believe that gene is already labelled. (`b1a49e8` fixed the *deletion* symptom; the identity
   confusion itself remains.)
3. **Re-anchor honestly.** A carried item keeps its own `xref`/`yref`; a `paper`-referenced label must
   not be silently re-anchored to data coords (today's bug flings it off-canvas).
4. **If something cannot be carried, say so** — a named count on the Re-run button / StaleBadge before
   the run, never a silent drop.

### C3 — Full direct manipulation *(owner decision 2)*
One missing primitive causes most of the remaining gaps: **there is no canvas selection model.**

1. **Selection store** — a `selectedAnnotationId`; set `captureevents: true` on Selom items so a click
   selects instead of falling through to `onSelectTrace` (which today yanks the inspector to the Data
   tab, away from Annotate).
2. **Row ↔ canvas linking** — hover-highlight and click-row-to-select both ways, so panel rows stop
   being indistinguishable "Text label / Significance" entries.
3. **Keyboard** — Delete/Backspace removes the selection; arrow keys nudge (Shift = coarse). Must stay
   inert while focus is in a panel input (the existing Cmd-Z discipline already does this correctly).
4. **Armed tool modes** — the tools rail becomes *pick tool → click canvas to place*, replacing one-shot
   commit. `aria-pressed` must reflect the genuinely active tool (it is currently hardcoded on Select,
   and `ToolContextStrip` always describes Select).
5. **Duplicate** + **cascade offset** so repeated adds never land pixel-identical.
6. **Numeric x/y fields** for precise placement, and in-place text editing: re-enable Plotly's
   double-click text edit for **decoration** items (`annotationText: false` at
   `figure-canvas.tsx:445` currently disables it for *everything* to protect the gene-label identity
   model — scope it to gene labels only, which C2.2 makes safe).

### C4 — Decoration completeness
1. **Style controls** — colour, font size, line weight, arrowhead. `INK` and sizes 15/16/12 are
   hardcoded in `annotations.ts`; items must also follow the **active journal-style stamp** so switching
   style doesn't leave hand annotations visually off-system.
2. **Boxes / highlights.** *Dependency:* "snap to an alignment guide" belongs to the **unbuilt slices 3
   (rulers) and 4 (guides + snap)** of the parent spec — C4 ships the box primitive; snapping arrives
   with slice 4. Do not silently promise snapping here.

---

## 6. The flag-flip condition — what "done" means

`NEXT_PUBLIC_ANNOTATION_LAYER` flips to on **only** when:

- **C1 and C2 are complete and their §7 ratchets are green.** These are the correctness and
  data-loss slices; neither may ship partially.
- **C3 is complete** (owner chose full direct manipulation, so a half-built selection model is a worse
  experience than the current flagged-off state).
- **C4 may trail** behind the flip — decoration gaps degrade the experience but make no false claims
  and lose no work.
- A **real-browser pass at desktop widths** on the lead's main checkout (Selom is desktop-only), run
  *after* Lane 3's artboard changes land — see §9.
- `fe-review` (V·R·D·A·R·N) run at the milestone, conducting `impeccable` for the 5.1 marker.

## 7. Ratchets — every requirement above is guarded, or it is not a requirement

The parent spec's "ideally" is exactly what this section exists to prevent.

| Guard | Asserts |
|---|---|
| `annotations.claim-provenance.test.ts` | No client path can emit a star glyph into `layout.annotations` without `verified:false` + a provenance `actions[]` entry. Fails if a bare `"*"` default ever returns. |
| `annotations.verified-immutable.test.ts` | The Marks/Annotate text editor **refuses** to change the text of a `verified:true` item (closes the retype-to-`***` hole). |
| `figure-rerun.carry-through.test.ts` | A re-run preserves **every** `selom`-tagged annotation, not just gene labels; anything droppable is reported, never silent. |
| `annotations.identity-by-id.test.ts` | Annotation matching is by `selom.id`; a label whose `text` equals a gene symbol does **not** register as that gene's label. |
| `annotations.no-client-bracket-geometry.test.ts` | The client emits no bracket geometry — a structural guard that D2 cannot return. |
| Backend: extend the existing `_charts` tests | `sig_brackets` stars follow the chosen `sig_test`, and the emitted `y_top` always exceeds error-bar + point extent (D2's root cause, guarded server-side too). |

## 8. Explicitly out of scope

Node/Bézier/path-boolean editing (the parent spec's §7.5 "Inkscape trap" — hard line, unchanged) ·
rulers/guides/snap (slices 3–4) · the compositing artboard (parent §8) · journal-style presets
(slice 9, deferred) · anything in Lane 3's editor-chrome territory.

## 9. Dependencies & sequencing

- **Lane 3 is changing `artboard-host.tsx` and `palette-strip.tsx` right now.** C1's "can I actually
  see the bracket" verification and §6's browser pass are **height-sensitive**, so they must run
  against **post-merge-train `main`**, not today's tree. Do not measure clipping until Lane 3 lands.
- **No conflict with the live lanes otherwise:** every file this spec touches
  (`lib/figure/annotations.ts`, `components/figure/figure-canvas.tsx`, `lib/volcano/labels.ts`,
  `components/project/hooks/use-figure-run.ts`, `skills/_charts.py`) is outside all three lane globs.
  This spec was written *while* the lanes ran, deliberately touching no shared file — including the
  plan's Status table, which all three lanes edit.
- **Suggested order: C1 → C2 → C3 → C4.** C1 first because it is the integrity defect *and* the
  cheapest (mostly deletion, machinery already exists). C2 second because it is data loss. C3 is the
  largest slice and gates the flag. C4 can trail.
