# Skill Keyword Index — legend-segmentation hardening (scope)

> **Status: DRAFT for owner review (spec-before-code, session 33, 2026-06-20).** Fast-follow #1 to
> the Skill Keyword Index v1 (`docs/records/skill-keyword-index/spec.md`, shipped s32). v1's honest
> limitation: **per-figure routing degrades on real PDFs**. This doc pins *why* (measured on the
> real JEV text), scopes the deterministic fixes, and keeps the open-core / library-only / AI-verifies
> posture intact. Per-item scope first; validate-by-metric against the four hand ledgers + the real
> JEV PDF text. Owner-sequenced 2026-06-20 ("legend hardening" picked from the s32 fast-follow menu).

## The limitation, measured (not assumed)

v1's record said per-figure routing "degrades to results-attribution when the PDF has no detectable
*Figure legends* section." Running the v1 router on the **real** JEV PDF text
(`D:/selom-data/_jev_text.txt`, 107 k chars) refines that into three concrete, fixable defects:

| # | Defect | Evidence on the real JEV text |
|---|---|---|
| **A** | **Figure legends ARE present but invisible to the matcher.** PDF extraction renders each caption marker as a *letter-spaced* `F IG U R E ` line **with the figure number stripped off**, inline between Results paragraphs (two-column reflow). `_FIG_CAPTION` (`Fig(?:ure)?\.?\s*(\d+)`) requires a number glued to the marker → **0 caption blocks detected** → `seg.legends == {}`. | 8 `F IG U R E ` markers (lines 538/552/637/652/668/680/750/771), each followed by a title + `(a)…(b)…(c)` sub-panels, **in figure order**. |
| **B** | **The bibliography is not excluded.** No `References` header line exists in the extracted text, so the ~230-line reference list (every tool name in the field appears here) lands in the `results` bucket (66 k chars) and is matched at weight 0.6. The spec named this the single biggest false-positive guard; on real PDFs it is currently off. | Doc tail (≈ lines 890–1120) is classic `Author, A., & B. (YYYY). Title. Journal …` citations; `seg.refs == ""`. Also `Discussion` (line 757) is not a recognised header → Discussion text pollutes `results` too. |
| **C** | **Results-proximity attribution looks the wrong way.** With no legends, per-figure hits fall back to `_figure_in_window`, which takes the nearest `Fig N` in the **160 chars *before*** a term. But scientific prose cites the figure *after* the claim — `"…and volcano plot (Figure 4e)"` — so a term is attributed to the *previous* sentence's figure. | `"…heat map (Figure 4d…), and volcano plot (Figure 4e…)"` → `volcano` attributed to **4d**, not 4e. Fig 5 dropped entirely; Fig 1 mis-tops to `oos:wet_lab` at conf 1.0; Fig 8 (single-cell) tops `skill:pathway`. |

**Current real-JEV per-figure output vs. the hand ledger** (`reproduction_jev.build_ledger`):

| Fig | Ledger (ground truth) | v1 router top | Verdict |
|---|---|---|---|
| 1 | `deg` (1c DE-miRNA heatmap; 1d qRT-PCR is a sub-panel) | `oos:wet_lab` (conf 1.0) | ✗ falsely confident; deg buried |
| 3 | `volcano` | `deg` | ≈ (DE family, wrong form) |
| 4 | `pca` (4c) / `heatmap` (4d) / `deg`+volcano (4e) | `volcano` | partial |
| 5 | `heatmap` | *(dropped — no route)* | ✗ |
| 6 | `composition` | `markers` | ✗ |
| 8 | `umap_scrna`/`markers`/`trajectory` (single-cell) | `pathway` | ✗ |

Paper-level routing was already correct in v1 (the s32 dogfood) — this hardening is **per-figure only**.

## What this is NOT

- Not OCR/vision over scanned PDFs, not an LLM reading pass — those stay the **paid tier** (spec K1/K7).
- Not a `reproduction.py` change — the engine front-half wiring (`to_engine_panels`/`build_ledger`)
  stays fast-follow #2, after this lands.
- Not new vocabulary tuning (e.g. taming `skill:pathway`) beyond what the section fixes incidentally
  cure — vocab is its own surface.

## Design — four deterministic fixes (all in `extract/routing/segment.py` + `route.py`)

### Fix A — detect garbled inline caption blocks (the core)

Generalise caption detection beyond a clean "Figure legends" section:

1. **De-space the marker.** A caption marker is a short line that, after collapsing intra-token
   spaces, reads `FIGURE`/`FIG`/`FIG.` optionally followed by a number — so `F IG U R E ` →
   `FIGURE`. Case-insensitive, length-bounded (a marker line is short; a sentence that merely
   contains "figure" is not one).
2. **Block = marker → next marker.** Caption text runs from one marker line to the next detected
   marker (or a hard section boundary: a recognised header, or the start of the references region
   from Fix B). Interleaved running-head / footer cruft inside a block is stripped (a small
   deny-set: the journal running head e.g. `CIOANCA et al.`, bare `of`, page-number-only lines).
3. **Recover the figure number** when the marker has none — see decision **H1** below.
4. A block is only accepted as a legend if it *looks* like one: a leading title sentence and/or a
   sub-panel run (`(a) … (b) …`), not just a stray `FIGURE` token. This is the legend-vs-noise gate.

Detected blocks populate `SectionedText.legends[fig]` exactly as today, so `route` is unchanged
downstream — legend hits attach to their figure at weight 0.8, which is what makes per-figure
honest.

### Fix B — exclude the bibliography without a header

The References section is the false-positive minefield (spec §K4). When no `References` header line
exists:

1. **Heuristic reference-region detection.** Scan from the document tail for a long run
   (≥ a threshold of consecutive lines) matching a citation shape (`… (YYYY). …` and/or a
   `https://doi.org/` / journal-tail pattern). Mark from the run's start onward as `refs` →
   excluded from matching. Conservative: only a clearly citation-dense tail trips it, so a
   methods paragraph that cites a few papers is never swallowed.
2. **More section headers.** Recognise `Discussion` / `Introduction` / `Abstract` /
   `Acknowledgements` / `Supporting Information` so they route to `body` (weight 0.3), not
   `results` (0.6) — Discussion prose shouldn't carry results weight.

### Fix C — forward, sentence-bounded results attribution (the legend-less fallback)

When a figure has no detected caption block, results-proximity is still the fallback — make it
correct: for a results hit, choose the nearest `Fig N` reference, **preferring one that follows the
term within the same sentence** (the `"claim (Figure N)"` convention), falling back to the nearest
preceding reference. Bound the search to sentence delimiters so the previous sentence's figure can't
leak in. This fixes the `volcano → 4d` class of error for any paper whose captions don't extract.

### Fix D — honest per-figure signal (the AI-verify seam)

Per-figure routing is genuinely uncertain on mixed figures (JEV Fig 1 = a DE heatmap **and** a
qRT-PCR validation panel — `deg` and `wet_lab` both belong). Rather than emit a falsely-confident
single top:

- Add `FigureRoute.attribution: "legend" | "results" | "none"` — provenance of the routing evidence.
- Keep `confidence` meaningful: a results-only route is inherently lower-confidence than a
  legend-anchored one.
- Surface the top candidates (already on `FigureRoute.candidates`); document that a low-confidence /
  results-attribution figure is exactly where the (future, gated) AI-verify pass adjudicates.

No behaviour is *forced* to a single answer it can't justify — the honest-signal posture that keeps
the two-axis credibility (memory `selom-reproducibility-score`).

## Architecture — a layered deterministic core (owner-resolved, 2026-06-20)

Owner steer mid-session: the deterministic core should be **layered** — a precise first layer for the
~90% of well-structured journals, then a recovery sweep for the messy ~10% (the JEV class) — rather
than one aggressive pass that taxes the clean case. Adopted in full:

**Two guarantees, four layers (owner framing).** The tool makes two different promises that deserve
different layers: a **paper-level skill inventory** that must be near-100% ("which skills does this
paper need?" — the core deliverable, robust because it does *not* depend on figure attribution), and
**per-figure attribution** ("which figure does each skill belong to?" — the premium gravy, hard
deterministically, perfected by AI). The core promise therefore rests on the *simplest* layer (L3).

| Layer | Scope | What | Runs when | Provenance |
|---|---|---|---|---|
| **L1 — Structured** | per-figure | recognised headers; **numbered** inline / sectioned captions (`Figure 1 \|`); explicit `References`; **exact** curated/registry match (boundary-safe v1 matcher) | always | `tier=structured` → full conf |
| **L2 — Recovery sweep** | per-figure | de-spaced / garbled / private-use-glyph markers + **ordinal** number recovery; **header-less** citation-dense refs detection; forward results-attribution | when L1 is insufficient for that paper/figure | `tier=recovered` → damped conf (AI-upsell flag) |
| **L3 — Paper vocab sweep** | **whole paper, refs excluded** | **exact + relaxed** (token-canonical: space/hyphen-insensitive + conservative stemming, so `heat map`/`Heat maps`→heatmap, `differentially expressed`→`differential expression`) match over **all** non-reference text → the **authoritative skill inventory** | always | the core guarantee — **near-100% recall**, independent of attribution |
| **L4 — AI (paid)** | per-figure | adjudicate residual low-confidence/ambiguous figures; OCR/vision for image-only PDFs; mine new synonyms back into the vocab | opt-in, gated | never required |

**Why measured here:** the per-figure recall misses (`deg`/`heatmap` dropping on JEV Figs 1/4/5) are
**surface-form** failures — exact match has `differential expression`/`heatmap` but the captions say
`differentially expressed`/`heat map(s)`. L3's token-canonical relaxed matcher closes them generically
(the canonical key of `differential expression` and `differentially expressed` is identical), with
**one** curated add (a bare `heatmap` term) for the irregular split. Crucially, even when per-figure
attribution coin-flips on a mixed figure (JEV Fig 1 = a DE heatmap **and** a qRT-PCR panel), **L3 still
lists `deg`** — the core promise holds; only the gravy is uncertain, and it's flagged for L4.

The L3 relaxed matcher is **boundary-safe by construction** (it tokenises whole words, so `PCA ∉ PVCA`,
`GSEA ∉ ssGSEA`), runs as a **gap-filler** in the per-figure paths (skips spans an exact hit already
claimed), and contributes at a **damped weight** so it never outranks a structured/exact hit. The
paper-level inventory aggregates **all** non-reference hits, so no skill is lost to a segmentation error.

## Validation (validate-by-metric)

1. **Real-JEV per-figure** (`skipif` the gitignored text is absent — same pattern as the live drives):
   after the fixes, the per-figure tops/candidates reproduce the JEV ledger — Fig 1 surfaces `deg`
   (no longer a confident `wet_lab`), Fig 3 `volcano`, Fig 4 `{pca, deg, heatmap}`, Fig 5 `heatmap`,
   Fig 6 `composition`, Fig 8 `{umap_scrna, markers, trajectory}` (not `pathway`).
2. **Refs-exclusion on the real bibliography** — a tool named *only* in the JEV reference list does
   not route (e.g. a package that appears in citations but not methods).
3. **Committed synthetic fixtures** (deterministic, offline) for the two new mechanisms: a
   garbled letter-spaced `F IG U R E ` block with a stripped number, and a header-less trailing
   reference list. Added to `tests/test_routing.py`.
4. **No regression** — the four committed ledger backtests stay green; v1's boundary / negation /
   refs / registry-extensibility / endpoint guards stay green.

Library-only (D12); no new deps; no network in the unit suite; no dev servers.

## Decisions (resolved — owner, 2026-06-20)

- **H1 — figure-number recovery = ordinal among detected blocks** ✓. The k-th detected caption block
  maps to the k-th **main** (non-supplementary `S`) figure number referenced in-text. Smallest change
  that works on the real evidence (JEV: 8 in-order blocks → Figs 1–8). When ordinality can't apply
  (out-of-order / a main figure with no caption block), the figure falls back to the now-corrected
  results-attribution (Fix C). Cross-reference pinning is a later hardening if a real paper breaks it.
- **H2 — honest signal over forced top** ✓. Add `attribution` provenance + keep confidence meaningful;
  surface candidates for mixed figures rather than a confident single top.
- **H3 — stay deterministic this iteration** ✓. AI-verify / synonym-mining remains a documented stub
  (fast-follow #3); no model on the path.
- **H4 — conservative refs-stripping** ✓. Only a clearly citation-dense tail is excluded; never a
  methods/results paragraph that merely cites a few works.
- **Scope = all four fixes (A+B+C+D)** ✓ — B and C are required for A to fix per-figure on real PDFs.

---

## Built + validated (session 33, 2026-06-20)

Shipped to the 4-layer design, library-only, no new deps. `extract/routing/`:

- **segment.py** — caption detection now handles the garbled real-PDF form: de-spaced markers
  (`F IG U R E `→`FIGURE`), trailing private-use-glyph numbers tolerated (`\W*$`), the L1/L2 gate
  (clean numbered captions always kept; bare/garbled markers accepted only when the numbered set is
  insufficient for the in-text figure pool), **ordinal** number recovery, cruft stripping, the
  caption-shape gate, and per-figure `legend_tiers`. Header-less refs excluded via a **final-cluster**
  detector (citation-shaped lines essentially only occur in the bibliography; find the trailing
  cluster, absorb wrap-gaps) — on real JEV it lands exactly on the first reference, after a
  letter-spaced `R E F E R E NC E S` the header regex can't see. Discussion/Introduction/Abstract
  recognised as headers (→ body weight).
- **index.py** — added the **relaxed token-canonical** matcher (L3 recall): canonical key = stemmed
  tokens concatenated, so `heat map`/`Heat maps`→`heatmap` and `differentially expressed`→`differential
  expression` match. Boundary-safe (whole-token), longest-span-first, negation-guarded.
- **route.py** — exact (L1) + relaxed (L3) two-pass per section; relaxed is a **gap-filler** (skips
  spans an exact hit claimed) at a **damped** weight; **canonical-term dedup** within (figure, section)
  so a repeated sub-panel term can't dominate while distinct synonyms still reinforce; the **L3 paper
  inventory** (`skills`/`out_of_scope`, robust to attribution error) + per-figure `tier`/`attribution`/
  provenance-scaled `confidence` + `tier_summary`.
- **synonyms.json** — one curated add (bare `heatmap`) for the irregular split the relaxed matcher
  can't derive.

**Validated by metric** (`tests/test_routing.py`, 23 pass + the real-JEV skipif):
- **L3 inventory recall on the real JEV PDF (the core deliverable)** — all 8 of the ledger's in-scope
  skills surfaced (`deg`/`heatmap` now recovered via the relaxed matcher; was missing pre-fix) +
  `out_of_scope=['wet_lab']`. `annotate` (a Fig-8 demo substitution) is the only ledger skill not
  surfaced — an honest, narrow gap.
- **All 8 garbled JEV captions detected** and every figure flagged `tier=recovered` (`tier_summary
  {structured:0, recovered:8}`) — the honest AI-upsell signal.
- **Header-less refs** fully excluded (full bibliography from the first reference; a mid-list term does
  not leak); **forward attribution**, **glyph tolerance**, **relaxed surface variants**, **dedup**,
  **tier provenance**, and the 4-ledger backtest all guarded. No regression.
