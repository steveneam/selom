# Skill Keyword Index — engine-wiring scope (fast-follow #1)

> **Status: scoped 2026-06-20 (session 34), owner-approved breadth.** Wires the validated
> 4-layer router's **L3 inventory + per-figure routes** into the reproduction engine's front-half,
> so a dropped paper auto-produces the panel→skill map the four ledgers hand-encode today. Builds
> on the v1 router (`docs/skill-keyword-index/spec.md`) + the legend-hardening 4-layer core
> (`docs/skill-keyword-index/legend-hardening-scope.md`). Resolved decision #2 of the v1 spec
> ("Auto-populating `Panel.skill_id` is a fast-follow after the backtest passes") — now due.

## What

Two bridges from `route_text(...) -> FeasibilityMap` into the engine's `reproduction.Panel`/`Ledger`:

1. **`extract/golden.to_engine_panels(spec, *, feasibility=None)`** — the existing DE-count→`Panel`
   bridge gains an optional `FeasibilityMap`. When present, each panel's `skill_id` is stamped from
   its figure's route (top in-scope skill), and an out-of-scope figure sets the mapped `scope`.
   `feasibility=None` → **byte-identical to today** (skill_id stays `None`).

2. **`extract/routing/engine.py`** (new):
   - `route_to_panels(fmap) -> list[reproduction.Panel]` — the auto-ledger skeleton: **one `Panel`
     per routed figure**, `skill_id` = the figure's top in-scope skill (the full ranked in-scope
     suggestion set carried in `note`), or the mapped out-of-scope `scope` (skill_id `None`) for an
     oos figure.
   - `build_auto_ledger(text, paper_id, *, paper=None, index=None) -> reproduction.Ledger` — route
     the text and wrap the panels in a `Ledger` with a minimal `Paper`, so "drop a paper → an
     engine-ready ledger skeleton" is one call. Drives cleanly through `build_scorecard`.

BE-only / dogfood (D12). No new endpoint this slice (the FE feasibility surface is fast-follow #3;
`POST /papers/route` already returns the `FeasibilityMap`).

## The one forced design constraint — figure granularity, no fabricated panel letters

The router resolves to **figure** granularity with a *ranked candidate list* per figure; it cannot
know real sub-panel letters (which of 1A/1B/1C is the UMAP vs the dotplot). The engine keys panels
by `key = f"{figure}{panel}"` and `Ledger.panel(key)` / the scorecard's `val_by_key` take the first
match — so **duplicate keys shadow**. Two consequences, both resolved by emitting **one panel per
figure**:

- **Unique keys** come free (figure numbers are distinct).
- **No fabricated letters.** Inventing `1a/1b/1c` to spread a figure's candidate skills across
  panels would mislabel the figure (routing order ≠ panel order) — a violation of the repro
  discipline (`figure-repro-look-at-figures-first`, "declare, don't infer"). Instead the **primary**
  skill is `skill_id` and the **full ranked in-scope suggestion set** rides in `note`
  (`"auto-routed via Skill Keyword Index: umap_scrna (also: markers, trajectory, pseudotime_genes);
  tier=…, attribution=…, confidence=…"`). The complete per-figure candidate detail already lives on
  the `FeasibilityMap` the caller holds.

This is the same honest degradation already documented for the router: the auto-map is the
**skeleton** a human (or, later, the L4 AI tier) refines into sub-panels — not a claim of exact
panel-letter knowledge.

## Mapping rules

| route fact | engine `Panel` |
|---|---|
| `fr.in_scope` (top is `skill:<id>`) | `skill_id=<id>`, `scope=TRANSCRIPTOMIC`, `status="mapped"` |
| oos (top is `oos:<reason>`) | `skill_id=None`, `scope=scope_of(top)` (`MODALITY_UNSUPPORTED`/`WET_LAB`/`DATA_NOT_DEPOSITED`), `note` carries the reason |
| in-scope suggestion set | the ranked in-scope skill ids in `note` |
| `tier` / `attribution` / `confidence` | summarised in `note` (the provenance trail; never silently asserted) |

`scope_of` / `is_skill` / `skill_id` / `oos_reason` are the existing helpers in
`extract/routing/models.py` — no new scope vocabulary (K5). `chart_form` is left empty (the router
does not reliably classify a figure's chart form; the ledger author / classifier fills it).

## Validation (validate-by-metric — the four hand ledgers are the golden, again)

Backtest the auto-map against the per-figure **hand-encoded** skill sets of the four
`reproduction_*` ledgers (offline text fixtures, the same ones the router backtest uses):

| ledger | in-scope figure → hand skills (the golden the auto-map must land inside) | oos figures |
|---|---|---|
| Dorgau | 1→{umap_scrna, markers, trajectory, pseudotime_genes} | 2 spatial, 4 atac, 6 grn, 7 wet_lab → scope mapped |
| Hani | 1→{composition}, 2→{corr_heatmap, boxplot}, 3→{violin, cepo}, 4→{regression}, 6→{umap_scrna} | 6 also has a wet_lab panel (paper-level oos) |
| JEV | 1→{deg}, 3→{volcano}, 4→{pca, heatmap, deg}, 6→{composition} | — |
| RPGRIP1 | 5→{deg, gsea, pca}, 6→{annotate, composition, gsea, deg} | 5 also wet_lab |

Assertions:
1. **Per-figure skill ∈ the hand set.** For every in-scope figure the auto-map produces, its
   `skill_id` (and each suggestion-set entry) is one of that figure's hand-encoded skills — no
   skill invented that the figure doesn't use.
2. **Out-of-scope scope matches.** Each purely-oos figure's auto-`Panel.scope` equals the hand
   ledger's scope for that figure (`MODALITY_UNSUPPORTED` for spatial/atac/grn, `WET_LAB`).
3. **`build_auto_ledger` drives.** The DORGAU fixture → a `Ledger` that runs through
   `build_scorecard` without error; `n_in_scope` counts only the in-scope figures (oos figures
   greyed/excluded, the two-axis-score invariant).
4. **Backward compatibility.** `to_engine_panels(spec)` (no feasibility) is unchanged — skill_id
   stays `None`; with a feasibility map the DE-count panels gain the routed skill_id/scope.
5. **Real JEV.** The skipif real-JEV test extends: `build_auto_ledger` over the real PDF text
   yields in-scope figure panels whose skills ⊆ the JEV ledger inventory, oos `wet_lab` flagged.

Library-only; no new deps; no network. pytest + ruff green before any push.

## Out of scope (this slice)

- A surfacing endpoint / FE feasibility view (fast-follow #3; pairs with the paper-metadata intake).
- The L4 AI-verify + synonym-mining seam (fast-follow #2).
- Auto-resolving real sub-panel letters / chart forms (needs vision/segmentation — the paid tier).
- Touching the four hand ledgers (validated ground truth — read-only here).
