# Skill Match — the Skill Keyword Index FE surface (fast-follow #3)

> **Status: SHIPPED + browser-verified, session 34 (2026-06-20).** The read-only frontend for the
> deterministic router, co-designed live with the owner — it grew well past the original "paste
> text" v1 into the full **"drop a paper"** flow. Route `/skill-match` (owner-named — chosen over
> "Feasibility"/"Skill Extraction" to avoid clashing with the existing `/extract` "Recover data").
> Backed by `POST /papers/route` + a new `POST /papers/extract`. Desktop-only. Design intelligence
> via `ui-ux-pro-max`; matches the repo's existing dark system (Card/Badge, `color-mix`, lucide,
> motion). Cross-lane (Claude owns both while Codex is away).

## What shipped

**The flow:** drop a paper PDF → its **metadata appears up top** + the dropzone becomes an **inline
PDF viewer** (the browser renders the dropped file — no upload) → hit **Run** → the router genuinely
routes the extracted text and the **matched skills stream into the right column** with a staggered,
reduced-motion-aware reveal. A paste-text path is the offline fallback (no viewer).

- **Backend `POST /papers/extract`** (`main.py`) — PDF upload → `{text, filename, metadata,
  provenance}` via `papers.extract_text` + `paper_metadata.metadata_for_pdf` (degrade-safe). The FE
  shows the metadata immediately, then routes the returned `text` via `POST /papers/route` on Run.
- **`paper_metadata` enrichment** — new `metadata_for_pdf` (the PDF counterpart of `metadata_by_doi`)
  + the model now carries **`volume` / `issue` / `pages`** (parsed from OpenAlex `biblio` + CrossRef)
  and a **PMID back-fill** (OpenAlex satisfies `_complete()` without a PMID → fetch it from
  PubMed-by-DOI when missing). The metadata card shows title · **all authors** · venue · vol(issue):pages
  · year · DOI link · **PMID link** · a Preprint badge.
- **Inline PDF viewer** — an `<iframe>` of an object URL (revoked on replace/unmount); Run + Replace
  header; the layout balances to two even panes once a paper is loaded (viewer ‖ skills).
- **Skill chips** — rich Store-style pills (modality icon + colour + catalog display name), matching
  the Project's Quick-apply chips. Each carries an **installed marker** (✓ = a verified catalog
  runner exists / runs now, vs ↓ available to install), computed against the live `GET /skills`
  catalog via `useCatalog`. Chips are **static** (a stray click never navigates); a single deliberate
  **"Open the Skill Store"** link sits under the inventory.
- **Summary band (the open-core moment)** — leads with **"N skills needed · X/Y installed"** (the
  reliable deliverable); shows the per-figure breakdown (figures · clean · need-review + the
  structured/recovered tier bar) **only when the PDF exposes figure captions**, else an honest "no
  machine-readable captions" note. The Pro-AI upsell is **adaptive**: it offers per-figure mapping
  when captions are missing, or verification of the low-confidence/recovered figures otherwise. The
  CTA is a **coming-soon** affordance (the live gateway isn't built).
- **Per-figure routing** ("the gravy") — an aligned **column grid** (FIG · MATCHED SKILL · TIER ·
  CONFIDENCE) with headers; each row = the figure's primary skill chip + a single "also … · evidence"
  sub-line + the tier chip + a **5-step temperature-coloured confidence** (red→orange→amber→lime→green).
  Mixed figures stay in-scope with a noted out-of-scope readout (same rule as the engine auto-ledger).
- **Nav** — a "Skill Match" rail entry; the rail **auto-collapses to its icon spine** on this route
  (a width-hungry two-pane view) so both panes get room.

## Validated (browser-verified on two real PDFs)

- **Hani** (`1-s2.0-S2213671122005914-main.pdf`) — full metadata (8 authors, *Stem Cell Reports*
  18(1):175-189, DOI + PMID 36630901), inline viewer, **14/14 installed**, and the **per-figure
  gravy**: Fig 1→scRNA UMAP, 2→Differential expression, 3→Marker-gene dotplot, 4→scRNA UMAP, 6→
  Composition bar (+ wet-lab readout), each with tier + temperature confidence — matching the Hani
  ledger. Out-of-scope: spatial + wet-lab.
- **JEV** (`JEV2-12-12393.pdf`) — metadata (6 authors, *J. Extracellular Vesicles* 12(12), DOI +
  PMID 38082562), 18-skill inventory all installed; **0 figures** → the honest "no captions" path +
  the per-figure Pro-AI upsell. Console clean; `POST /api/papers/extract` + `/papers/route` 200.
- pytest `test_paper_metadata` +3 (extract endpoint, `metadata_for_pdf` degrade, biblio parse);
  FE vitest 63 (incl. `confidenceColor`, `citationLine`, `authorSummary`, installed-fraction);
  tsc + skill-match ESLint clean.

## Honest limitation surfaced (follow-up)

The L2 figure-caption **recovery was tuned on `_jev_text.txt`**, an extraction the production
`papers.extract_text` (pypdfium2) — and pypdf — **do not reproduce**, so per-figure routing yields 0
figures on the JEV PDF *through the app* even though the L3 inventory is robust. Reconcile the legend
recovery with the production extractor (or pick the extractor `_jev_text.txt` came from) so the
gravy lands on more real PDFs. The L3 inventory (the core promise) is unaffected.

## Out of scope (still)

- The live paid Pro-AI gateway (FF#2 seam is ready; CTA is coming-soon).
- Auto-rename / labels on intake (the rest of the `paper_metadata` intake item).
- Per-skill deep-links into the Store (the Store has no per-skill route yet — one section link instead).
