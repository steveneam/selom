# Next-session plan — options + parallel workstreams

_Written 2026-07-25 16:14 +1000 (Sydney) · 06:14 UTC, immediately after `main` fast-forwarded to
`d950601` (the LAUNCH-CAMPAIGN merge, 20 commits, **unpushed**)._

Backlog source of truth: `docs/milestone-review-2026-07-25/findings.md` (54 confirmed findings + a
status ledger). This file is the *sequencing* decision, not a second copy of the findings.

---

## 1. What is actually left

Honest accounting after the fix pass — the review's counts include items the annotation-layer gate
made unreachable, so they must not be double-counted as open work.

### 1a. Open — backend correctness / honesty (8)

| # | Sev | What | Where |
|---|---|---|---|
| A10 | HIGH | Gene-label selection went exact→substring, so a non-label column containing a gene token wins (same family as the blocker just fixed, gene half instead of the p-value half) | `engine/columns.py` GENE + the 6 forked `_pick`s |
| A14 | MED | Multi-sample assembly zero-fills genes absent from a sample's reference — fabricated hard zero counts, no overlap verdict | `engine/assemble.py:208` |
| A15 | MED | FACS gate bounds live in a transform space anchored to a data-dependent `t_top` that is never recorded → the same gate spec on a different file means different events | `skills/facs_gating/run_real.py:45,137-155` |
| A16 | MED | FACS silently drops gates it cannot resolve — the population just vanishes from the table | `skills/facs_gating/run_real.py:220+`, `skills/_flow.py:parse_gates` |
| A17 | MED | ERG oscillatory potentials report `0.0` amplitude for "not measurable" — conflates an unmeasurable trace with absent inner-retinal activity | `skills/_erg.py:347-390` |
| A18 | MED | The opt-in robust a/b detector changes measured amplitudes but the methods text never says it was used | `companions/methods.py:599-631` |
| A19 | MED | The `_pick` resolver is still forked verbatim into 6 runners; the drift guard cannot see a forked *matcher* (only forked vocab) | 6 × `skills/*/run_real.py` |
| A21 | MED | `engine/assemble.py` re-declares the 10x detector + re-implements unit loading instead of using `engine/ingest`'s declared loader registry | `engine/assemble.py:54,95` |

### 1b. Open — reachability / the FE↔BE seam (5)

| # | Sev | What | Where |
|---|---|---|---|
| A20 | MED | Cloud provider registry forked FE↔BE: the FE hardcodes `comingSoon`, cannot track the backend's per-provider flags | `lib/cloud/providers.ts` ↔ `cloud/registry.py` |
| A27 | MED | `/data/assemble-scrna` works and has **no way for a user to reach it** | `routers/data.py:153` (no FE surface) |
| B14 · B16 | MED | Backend-stamped cloud-import provenance (`datasets.source`) is dropped by the FE dataset mapper — an imported dataset looks hand-dropped | `lib/cloud/api.ts:37`, `lib/projects/sync.ts:28-39` |
| B15 | MED | Cloud import fabricates a `File` stand-in that becomes `lastFile` and can be POSTed as the run's actual data | `components/project/data-panel.tsx:256` |
| B22 | LOW | Cloud "Import" button becomes an unlabelled spinner while busy | `components/intake/cloud-import-menu.tsx:131` |

Plus the three closed gates that make the feature dead even though **both OAuth connections are
live and verified**: `SELOM_CLOUD_GOOGLE`/`_DROPBOX` absent from `app/backend/.env`, no endpoint
reports per-provider state, FE literal says `comingSoon`.

### 1c. Open — FE polish, still user-reachable (4)

A24 artboard hero clipped inside its own stage · A25 inert "coming soon" palette strip eats 64px of
a height-constrained editor · B13 the palette strip asserts the colourway by colour alone and is
`aria-hidden` · A30 icon glyphs collide across meanings, and new work continues on lucide against the
stated Phosphor preference.

### 1d. Gated, deliberately not open (≈20)

A9 · A12 · A13 · A23 · A29 · B1–B3 · B5–B8 · B10–B12 · B17–B21 · B23–B24 — all unreachable behind
`NEXT_PUBLIC_ANNOTATION_LAYER=off`. They come back the moment the flag flips, so the flag must not be
flipped except as part of Plan C.

### 1e. Carried over / external

- **Push `main`** (20 commits) — founder gate. Then delete `campaign/parallel-lanes`.
- **swordfish:** asked for a public Connect-UI host (`:3009`); also asked them to confirm syd2's own
  `NANGO_SERVER_URL` (the one check `deploy/nango/preflight.sh` must skip). Neither blocks anything.
- **Public Selom backend on syd2** — needs a backend Dockerfile + GHCR image-CI (mine) + 5 data-plane
  answers + an owner spend gate on any syd2 resize.
- **OneDrive/Microsoft** — on hold by owner.
- **Pre-existing unrelated failure:** `test_ingest.py::test_ingest_h5ad_single_cell` (anndata ↔
  pandas-3.0 h5ad write). Not campaign work; worth its own small fix or an honest skip-with-reason.

---

## 2. Three plans

### Plan A — "Make it reachable" (product-facing)

Turn today's OAuth into a feature a user can actually use, and close the whole FE↔BE seam cluster.

1. Backend: a `GET /cloud/providers` endpoint reporting each provider's declared state (id, label,
   kind, `provider_config_key`, `enabled`) from `cloud/registry.py` + settings — **one source of
   truth**, no FE literal.
2. FE: `lib/cloud/providers.ts` becomes a typed *consumer* of that endpoint (keep a static fallback
   for offline dev), so the Connect buttons reflect backend truth instead of a build-time constant.
   Closes A20, and A26/B4/B9 stay closed for the right reason.
3. Enable `SELOM_CLOUD_GOOGLE` + `SELOM_CLOUD_DROPBOX`, then drive a **real file** from Drive and
   Dropbox into the intake pipeline end-to-end.
4. Provenance through the seam: stop dropping `datasets.source` in the FE mapper (B14/B16), and kill
   the fabricated `File` stand-in so a cloud-imported dataset is POSTed by reference, not by a
   fake (B15). Label the busy state (B22).
5. A user-reachable surface for `/data/assemble-scrna` (A27) — the multi-sample intake path.

**Value:** the highest user-visible payoff on the board; converts finished plumbing into a feature.
**Risk:** spans both lanes by nature, so it needs the endpoint contract frozen before FE work starts.
**Size:** ~1 full session.

### Plan B — "Zero the review debt" (integrity)

Sweep every open backend correctness/honesty finding (§1a) plus the reachable FE polish (§1c).

1. A10 + A19 together: give GENE the same tier treatment the p-value half just got, and move the
   forked `_pick` into `engine.columns` so the drift guard can see one matcher. This is the natural
   completion of `b73bd9b`.
2. A14 + A21: honest gene-overlap verdict on assembly (and no fabricated zeros without one), and
   assembly consults `engine/ingest`'s loader registry instead of re-declaring 10x detection.
3. A15 + A16: record `t_top` in provenance so a gate spec reproduces; an unresolvable gate becomes a
   verdict row, not a silent disappearance.
4. A17 + A18: `None`/`not_measurable` instead of `0.0` for an unmeasurable OP, and the robust a/b
   detector disclosed in the methods text (same `layout.meta` channel the FACS/volcano fixes now use).
5. §1c polish: un-clip the artboard, retire or make honest the palette strip, and decide the icon
   question (A30 — Phosphor migration or an explicit "lucide stays" record).

**Value:** every remaining "the figure says X but the code did Y" risk goes to zero. No new surface.
**Risk:** low — all of it has tests and real data to verify against.
**Size:** ~1 session, and it parallelises cleanly (see §3).

### Plan C — "Finish Pillar-2" (the gated layer)

Build the annotation layer properly and flip the flag: a canvas selection model (click-to-select,
Delete, arrow-nudge, row↔canvas linking), cascade offsets so repeat adds are visible, annotations
carried through a re-run, bracket+stars moving as one object, and the **computed** `sig_brackets`
path wired so stars carry a real p-value with provenance instead of hand-typed asterisks.

**Value:** unlocks ~20 gated findings and the Illustrator-replacement promise.
**Risk:** highest — it needs design decisions first (a spec, not just fixes), and the p-value path
touches the provenance chokepoint.
**Size:** 2–3 sessions. Wants `spec` → review → build, not a straight fix pass.

### Recommendation

**Run Plan B and Plan A as parallel lanes next session; hold Plan C for the session after, entered
through a spec.** B and A are almost perfectly disjoint (B is `skills/**` + `engine/**` +
`companions/**`; A is `routers/cloud.py` + `cloud/**` + the FE cloud/intake surfaces), so they do not
serialise. C is the one that deserves undivided attention and a design pass, and the flag means
nothing is bleeding while it waits.

---

## 3. Parallel workstreams — isolated worktree lanes

Per the standing rule: ≥2 disjoint contract-separated buckets → **one isolated `claude` session per
worktree**, not an in-context fan-out (last attempt auto-compacted mid-sprint). Local merges
autonomous; **push stays the founder gate**.

### Lane 1 — BE integrity sweep (Plan B §1–4)

- **Owns (globs):** `app/backend/skills/**` · `app/backend/engine/{assemble,columns,vocab,ingest}.py` ·
  `app/backend/companions/methods.py` · `app/backend/tests/test_{volcano,gsea,flow,erg,assemble}*.py`
- **Findings:** A10 · A14 · A15 · A16 · A17 · A18 · A19 · A21
- **Frozen contract (must not change):** the `resolve_significance` / `pick_significance` signatures
  landed in `b73bd9b`; the `layout.meta` honesty channel key names (`significance`,
  `compensation_applied`) — Lane 1 may ADD keys, never rename these.
- **Gate:** `pytest -m "not slow"` + `ruff check .` green; each fix verified against a real dataset in
  `SELOM_DATASETS_DIR`, not a fixture.

### Lane 2 — Cloud reachability across the seam (Plan A)

- **Owns (globs):** `app/backend/routers/cloud.py` · `app/backend/cloud/**` ·
  `app/backend/routers/data.py` (the assemble surface) · `app/frontend/lib/cloud/**` ·
  `app/frontend/components/intake/**` · `app/frontend/lib/projects/sync.ts` ·
  `app/frontend/components/project/data-panel.tsx` · `app/backend/tests/test_cloud*.py`
- **Findings:** A20 · A27 · B14 · B15 · B16 · B22
- **Frozen contract (I freeze this BEFORE the lane starts, and only this lane implements it):**
  `GET /cloud/providers → { providers: [{ id, label, kind, provider_config_key, enabled }] }`.
  The FE consumes it; the static list survives only as an offline-dev fallback.
- **Gate:** a real file imported from Google Drive **and** Dropbox into a project, with
  `datasets.source` visible in the UI; MSW mock updated in the same change (a contract change updates
  its mock in the same move).

### Lane 3 — FE editor polish (Plan B §5)

- **Owns (globs):** `app/frontend/components/figure/shell/{artboard-host,palette-strip}.tsx` ·
  `app/frontend/lib/ui/**` · the icon decision
- **Findings:** A24 · A25 · B13 · A30
- **Frozen contract:** none — presentational only. Must NOT touch
  `components/figure/{property-panel,figure-canvas}.tsx` (Plan C's territory) or anything behind the
  annotation flag.
- **Gate:** `tsc` + `eslint` + `vitest`, **plus a real-app load at desktop widths** — this lane's
  findings are layout claims and §D of the review was never observed in a browser.

### Merge order + conflict rules

1. **Lane 1** first — pure backend, no cross-lane contract.
2. **Lane 3** second — pure frontend presentational, cannot conflict with Lane 1.
3. **Lane 2** last — it spans the seam, so it rebases onto both and its end-to-end gate then runs
   against the final tree.

Overlap risks and their mitigations: `app/backend/tests/**` is shared ground → each lane adds tests
only in its own named files listed above. `routers/data.py` is Lane 2's alone (Lane 1 touches
`engine/assemble.py`, not the router). `companions/methods.py` is Lane 1's alone.

### Owner steps (the only things a lane cannot do for itself)

1. **Push `main`** now (20 commits) and delete `campaign/parallel-lanes` after.
2. **Approve the lane partition** above (or reshape it) before any worktree is forked.
3. **Icon call (A30):** migrate to Phosphor now, or record "lucide stays" as a decision so the
   finding stops recurring in every FE review.
4. **Push after each lane merge** (per-lane, so a bad lane never rides in on another's push).
5. If Plan C is wanted sooner than the session after next, say so — it changes the sequencing above.

---

## 4. What this does NOT include

The public Selom backend on syd2 (owner spend gate + 5 data-plane answers to swordfish), OneDrive,
and Plan C's build. Also excluded: any flip of `NEXT_PUBLIC_ANNOTATION_LAYER` — that flag is the only
thing keeping ~20 findings out of a user's figure.
