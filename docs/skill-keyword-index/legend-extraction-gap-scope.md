# Skill Keyword Index — legend extraction↔recovery gap (fast-follow, scope + diagnosis)

_Stamped 2026-06-20 +10:00 (session 35). Claude (acting FE+BE). Reconciles the L2 figure-caption
recovery with the **production** PDF extractor so the per-figure "gravy" lands on real PDFs._

## The gap (as handed off from s34)

Per-figure routing ("the gravy") worked on the Hani PDF but yielded **0 figures on the JEV PDF
through the app**. The L2 figure-caption recovery (`extract/routing/segment.py`) was tuned on the
committed text fixture `D:/selom-data/_jev_text.txt`, which the production extractor
(`papers.extract_text` → pypdfium2) does **not** reproduce. The L3 skill INVENTORY (the core
promise) was never affected — it routes over the whole cleaned text independent of caption
detection. Only the per-figure attribution was missing.

## Diagnosis (measured, not assumed)

Ran `papers.extract_text` on the three real PDFs and compared caption forms to what L1/L2 expect.
**Two production caption forms L1/L2 missed**, both distinct from the fixture's letter-spaced
`F IG U R E ` (own short line) that L2 was tuned on:

1. **Inline custom-font-glyph form (Wiley / JEV).** The marker word is intact but the figure
   *number* renders as a Unicode **Private-Use-Area glyph** and the caption text is **inline** on the
   same long line:
   `FIGURE  Müller glia miRNA expression… (a) Experimental paradigm…`
   - `_MARKER_INLINE` requires a `\d+` after the marker → the glyph isn't a digit → no match.
   - The `len(s) > 40` guard then rejects the long line *before* `_MARKER_BARE` is tried.
   - Result: **0 of 8 captions detected** on the real JEV PDF.
   - The 8 glyphs are `f6dc` (fig 1) then sequential `f63a…f640` (figs 2–8), in document order →
     **ordinal recovery (already built) numbers them correctly**; the glyph itself is undecodable.

2. **Line-numbered manuscript / preprint form (bioRxiv / Ishii).** Every line carries a manuscript
   line-number prefix, which breaks the `^fig` anchor:
   `305 Fig. 1. Pseudotime trajectory analysis reveals two lineages…`
   - The clean `Fig. 1.` marker is perfectly structured — only the leading `305 ` hides it.
   - Result: **0 of 4 captions detected** on the real Ishii manuscript.

## Fix (surgical, L2 only — `segment._marker`)

Additive recovery — never touches L1's clean path, never touches L3:

- `_MARKER_GLYPH = ^fig(?:ure)?\.?\s+[PUA]+\s+(.*)$` — recognises the inline glyph-number caption,
  returns `number=None` (recovered ordinally) + the inline caption text. Gated by `_looks_like_caption`
  so a stray "Figure" token can't masquerade as one.
- `_LINENO = ^\d{1,4}\s+` — a leading manuscript line-number, stripped **locally for marker matching
  only** (the stripped candidate is tried first, then the raw line) so a line-numbered preprint's
  clean `Fig. N.` captions are seen. No whole-document rewrite (lowest risk); the minor line-number
  noise that rides into caption continuation text is inert for keyword routing.
- The existing `_MARKER_INLINE` (clean numbered) and `_MARKER_BARE` (letter-spaced de-spaced) paths
  are unchanged. This keeps the layered design: L1 structured, L2 recovery sweep widened to two more
  real-PDF forms ([[layered-deterministic-extraction]]).

## Validation (validate-by-metric, real production PDFs)

`papers.extract_text` → `route_text` / `build_auto_ledger`, current vs patched:

| Paper | figures before→after | tier | per-figure sanity | L3 inventory |
|---|---|---|---|---|
| **JEV** (glyph) | **0 → 8** | recovered | Fig3→volcano, Fig4→PCA+heatmap+volcano, Fig8→UMAP+trajectory | unchanged ✓ |
| **Ishii** (line-no) | **0 → 4** | structured | Fig1→trajectory (0.71), Fig2→violin, Fig4→deg | unchanged ✓ |
| **Hani** (already worked) | **5 → 5** | structured | identical | unchanged ✓ |

`inventory(current) == inventory(patched)` for all three — the fix is **pure per-figure gravy**, the
core promise is untouched. JEV's 8 are recovered-tier → all 8 flagged for the L4 AI upsell
(`needing_review=8`); Ishii's 4 are structured-tier (clean after de-numbering) → high confidence.

## Tests + fixture reconciliation

- **Committed unit fixtures** (deterministic, offline, in-repo): `GLYPH_INLINE` (real ``
  codepoint + inline caption) and `LINENO_MANUSCRIPT` (`305 Fig. 1. …`) in `tests/test_routing.py`.
  These are the permanent regression guard for the two production forms.
- **Regenerate `D:/selom-data/_jev_text.txt` from `papers.extract_text`** (local, gitignored data —
  backed up to `graphify-out/scratch` first) so the three `skipif` "real_jev" tests exercise the
  **actual production path**, not a non-reproducible hand fixture. Verified: production text passes
  all three (8 recovered, ledger ⊆ inventory, `wet_lab` oos, `needing_review == 8`).

**Compounding lesson (made permanent):** browser/CLI-verifying against the REAL production extractor
output — not a committed text fixture — is what surfaces extraction↔recovery gaps. The fixture now
*is* the production output, so the two can never silently diverge again.

## Out of scope / deferred

- **FE per-figure display** (owner note, s34): show *all* matched skills per figure (not one + the
  rest minimised) for visual weight. Deferred — frontend, separate task.
- Ishii Fig 3 routes `top=oos:atac` off "motif enrichment" (RNA-splicing motifs, not ATAC) but keeps
  `enrichment` in-scope — an honest borderline, the L4 verify tier's job, not a determinism bug.
