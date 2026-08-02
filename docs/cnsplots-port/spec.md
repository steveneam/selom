# Phase F, slice 1 — the parity audit and the theme port

Spec for the first buildable slice of `plan.md` (F1 + F2). Written 2026-08-02. **Not built.**

The rest of the phase (F3 design overhaul, F4 plot gaps) is deliberately not specced yet: F1 is the
measurement that should shape both, and specced-ahead work would be guessing.

---

## 1. F1 — the parity audit

### Goal

Turn "their plots look better" into a **list of named differences**, so F2 is a checklist and the
phase can be proved finished rather than declared finished.

### Method

1. Pick **five** plot types Selom and cnsplots both draw: **box · scatter · heatmap · volcano ·
   dot/enrichment**. They cover categorical, continuous, matrix, annotated-scatter and
   ranked-category — the whole styling surface between them.
2. Render each **from the same real dataset** (`SELOM_DATASETS_DIR`; EYG_28 for DE, an RPGRIP1
   export for the sc shapes) — Selom through its own skill, cnsplots through its API in a scratch
   venv. Real data, not synthetic: real label lengths and real category counts are where layout
   actually breaks ([[verify-on-real-data-not-mock]]).
3. Put them side by side at the same physical size and write down every difference under fixed
   headings: **typography · tick treatment · spines/frame · grid · legend · whitespace/margins ·
   colour · marker and line weight · annotation**.
4. For each difference, record a verdict: **PORT** (copy the value), **REJECT** (with a reason), or
   **CHECK** (needs a journal guideline).

### Output

`docs/cnsplots-port/parity-audit.md` — the table above, with both images inline per plot type. It is
re-run at the end of F2, and the same table becomes the proof.

### Notes

- The scratch venv is **throwaway and outside the repo** — cnsplots pulls matplotlib, seaborn,
  lifelines and biopython, and none of that belongs in Selom's backend (`uv run` auto-syncs the
  **shared** `.venv`, so it must not be installed there — [[selom-uv-sync-footgun]]).
- Rendering cnsplots is a **read-only comparison**, not a Selom code path.

---

## 2. F2 — the theme port

### Goal

Selom's default figure adopts the styling values that make cnsplots' output read as
publication-grade, **without any figure ceasing to be an editable Plotly spec.**

### Decisions

**D1 — One home: the style registry.** `skills/theme.py` is already applied centrally in `run_skill`
([[selom-publication-theme]]) and `skills/styles.py` exists. F2 completes the planned refactor to a
**named style registry** ([[selom-journal-styles-feature]]): a style is a named record of values, the
default is one entry, and journal packs are more entries. **No skill learns about styling** — the
same reason the export path has one home.

**D2 — Values are ported, not invented.** Every ported value carries a comment naming its cnsplots
origin. Where Selom and cnsplots disagree and cnsplots is not obviously right, the audit's CHECK
verdict decides it against a journal guideline, not taste.

**D3 — Attribution at the file level.** Every file carrying ported values gets a
`ported from cnsplots (BSD-3-Clause)` header; `LICENSES/cnsplots-BSD-3-Clause.txt` holds the licence;
`docs/external-tools-study.md` gets the ledger row.

**D4 — Journal packs are verified against the journal, not against cnsplots.** cnsplots is the lead
that tells us *which* numbers matter (column widths, max panel heights, minimum font size); the
authority is each journal's author guidelines. A pack whose numbers were never checked ships as
`draft` and says so.

**D5 — The theme must not break the editor.** Every value has to survive the round trip: applied by
`run_skill`, rendered, edited in the inspector, exported. A value that renders correctly but is
overwritten on the first edit is worse than not porting it.

### Acceptance

- The five audited plot types re-rendered, and **every PORT row from F1 closed** — the audit table
  re-run with before/after images.
- `scripts/verify.sh` 7/7, and the golden-image tests updated deliberately (a golden change here is
  *expected*, and each diff is reviewed rather than blanket-accepted — a blanket re-baseline would
  hide a real regression inside an intended restyle).
- A browser pass: a real figure in the editor, restyled, **still editable** — D5 proved, not assumed.
- The style registry exposes at least: `selom-default` and one `draft` journal pack.

### Risks

- **Golden-test churn.** Every skill's reference image moves at once. Mitigated by doing F2 as **one
  change**, reviewing the diffs as a set, and keeping the audit images as the human check.
- **Plotly cannot express some matplotlib treatment** (certain spine/tick combinations). Where so,
  record it in the audit as a REJECT with the reason rather than approximating badly.
- **Regression in dark mode / the app's own chrome.** The theme serves *export*; the editor renders
  the same spec on screen. Check both.

---

## 3. Explicitly out of this slice

F3 (the Mobbin-driven design overhaul) and F4 (venn, significance brackets, forest, QQ, confusion
matrix, ridge, slope/lollipop/donut). F4's items are independently shippable once F2 lands, and
**venn + significance annotation are the two the owner and the ERG work are most likely to want
first**.
