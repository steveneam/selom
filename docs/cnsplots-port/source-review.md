# Phase F — cnsplots source review, and the plot-parity plan

Owner-directed 2026-08-03: *"look at every plot type that cnsplots has, and make sure you can
replicate it exactly if not better, backend, engine, and interface frontend wise"* — after
*"thorough investigation and look into each folder and file in the cnsplots github … see what you
can take, integrate and elaborate to make selom better."*

Source: `github.com/faridrashidi/cnsplots` @ v0.6.0, cloned and read (not the PyPI wheel this
time). **BSD-3-Clause** — copy and credit, no clean room (`plan.md` §1).

---

## 0. Two premises in the brief that the source corrects

**There is no web, backend or frontend to port.** cnsplots is a pure Python plotting library:
153 tracked files, ~380 KB of Python under `src/cnsplots/`, a Sphinx docs site, 37 example
scripts, 30 test files. No JS, no React, no server, no API. Its "web" is documentation. So the
frontend half of this phase has **no source to copy from** — it has to come from Selom's own
design work plus Mobbin (§6), which is what the rest of this doc does.

**`_methods.py` is not methods text.** It holds `CoxModel`, `LogisticModel` and `prerank` —
statistical *models*, not prose. cnsplots generates **no auto-methods, no provenance, no
citations**. Selom's lit-synthesizer has no counterpart here. That is a Selom differentiator, not
a gap.

### What I actually read, so the depth is not overstated

| Read in full | Surveyed (signature + structure + targeted reads) |
|---|---|
| `_setup.py`, `_settings.py`, `_svg.py`, `_agent_skill/**`, `plot-catalog.md`, `AGENTS.md`, the public API of `_validation.py` and `_methods.py` | `plots/*` (8 modules, ~170 KB — every public signature + docstring extracted and the categorical module read), `helpers/*`, `_utils.py`, `_multipanels.py`, `docs/`, `tests/` |

The per-plot verdicts in §3 rest on signatures, docstrings and the catalog — enough to decide
*what* to build and *what it must do*, not enough to copy an implementation line-for-line. Each
build ticket re-reads its own module first.

---

## 1. The engine gap that matters more than any single plot type

Six cnsplots functions take **`pairs=`** — `boxplot`, `violinplot`, `barplot`, `lollipopplot`,
`stackplot`, `survivalplot`. It runs the pairwise test and draws the bracket + stars.
**Selom has this nowhere**, and the ERG work hand-rolled it once already
([[selom-erg-manual-marks]]). It is the highest-value item in the whole phase because it is
*one* engine feature that upgrades every categorical plot at once.

Four more cross-cutting behaviours, same shape — build once, every plot inherits:

| Feature | cnsplots | Selom today |
|---|---|---|
| `pairs=` → test + bracket + stars | 6 plot types | **none** |
| `add_count=True` → `n=` under each category | 4 plot types | none |
| `errorbar` = `se` / `sd` / `ci`, **bootstrap CI for medians** (1000×, seeded) | lollipop, line | ad-hoc per skill |
| `hue` / `order` / `hue_order` as a uniform grouping contract | every categorical plot | inconsistent param names per skill |

**Do these first.** A venn plot helps one figure; `pairs=` helps every figure with categories in
it, and the uniform `hue`/`order` contract is what makes a plot-type picker (§6) coherent instead
of 50 bespoke parameter forms.

---

## 2. Licence triage — done at decision time, not from a list

| Dependency | Licence | Verdict |
|---|---|---|
| cnsplots itself | BSD-3 | ✅ copy + credit (already in `LICENSES/`) |
| `statannotations` (the `pairs=` engine) | BSD-3 | ✅ but see below |
| `matplotlib-venn` | MIT | ✅ — though Selom draws venn in Plotly, so it is the *set arithmetic* we want, which is trivial |
| `upsetplot` | BSD-3 | ✅ (Selom already has its own UpSet) |
| `lifelines` (survival) | MIT | ✅ if survival is ever built |
| `comprisk` | check at build time | ⚠️ LATER with survival |
| `pycomplexheatmap` | check at build time | ⚠️ Selom's heatmap is already richer; likely never needed |
| `adjustText` | MIT | ✅ — the label-collision fix (audit row 22) |
| **MuPDF / `mutool`** (the SVG pipeline, §4) | **AGPL-3.0** | ⛔ **do not put on the shipped path.** Network-use trigger on a SaaS ([[license-decision-framework]]). |

**`statannotations` caveat:** it is a matplotlib/seaborn artist. Selom emits Plotly specs, so we
take its *statistics and bracket geometry*, not its drawing. That is a port, not a dependency —
and it keeps the figure an editable Plotly spec, which is the whole product.

---

## 3. Every cnsplots plot type vs Selom

31 public plot functions. **Selom already covers 12 at or above parity, 3 need a feature, and 16
do not exist.** Selom has 20 skills cnsplots has no answer to (§3.3).

### 3.1 Selom has it — verify parity, do not rebuild

| cnsplots | Selom skill | Verdict |
|---|---|---|
| `boxplot` | `boxplot` | **HAVE** + needs `pairs`/`add_count` (§1) |
| `violinplot` | `violin` | **HAVE** + needs `pairs`/`add_count` |
| `heatmapplot` | `heatmap` | **HAVE+** — Selom has dendrograms, categorical tracks, block splits, a quant side-bar. Ours is richer. |
| `dotplot` | `markers`, `enrichment` | **HAVE** (size key fixed 2026-08-03) |
| `volcanoplot` | `volcano` | **HAVE+** — Selom labels genes with leader lines; cnsplots drew none |
| `upsetplot` | `upset` | **HAVE** |
| `sankeyplot` | `sankey` | **HAVE+** — Plotly's native `sankey` trace vs their 15 KB hand-drawn matplotlib helper (§4) |
| `stackplot` | `composition` | **HAVE** + needs `pairs`/`normalize` parity |
| `regplot` | `regression` | **HAVE** — confirm correlation stats are on-figure |
| `prerank` | `gsea` (gseapy) | **HAVE** |
| `scatterplot` | `pca` | **PARTIAL** — Selom has no *generic* scatter skill, only PCA. See 3.2. |
| `confusionplot` | — | **GAP**, trivial heatmap variant; serves `annotate`/`markers` |

⚠️ **`gseaplot` is not Selom's `gsea`.** cnsplots' `gseaplot` is a **dot plot of enriched terms**
(NES colour, size, FDR cutoff, top-N). Selom's `gsea` is the **running-enrichment curve**. They
are different figures with the same name. Selom's `enrichment` dot plot is the nearer match.
Ship both; do not conflate them.

### 3.2 Build these — ranked by value, each independently shippable

| # | Plot | Why now | Cost |
|---|---|---|---|
| 1 | **Significance annotation** (not a plot — §1) | Unlocks 6 existing skills | M |
| 2 | **`venn`** | Owner named it; 2–3-set DE overlap is what reviewers expect | S |
| 3 | **`forest`** | Selom's DE output is already the input; pairs with effect sizes | S |
| 4 | **`qq`** | Makes an inflated test *visible* — diagnostic for work Selom already does | S |
| 5 | **`scatter`** (generic x/y/hue) | The most-requested shape Selom cannot draw without a PCA | S |
| 6 | **`line`** (generic, with `errorbar`) | Same; the ERG skills each hand-roll one | S |
| 7 | **`confusion`** | Trivial heatmap variant | S |
| 8 | **`ridge`** | Companion to `composition`; distribution-per-group | S |
| 9 | **`strip`** | Individual points; the honest companion to every box plot | S |
| 10 | **`slope`** | Before/after — currently forced into a bar chart | S |
| 11 | **`lollipop`** | Ranked single value; brings the bootstrap-median CI with it | S |
| 12 | **`hist` / `kde` / `dist`** | Three views of one distribution; build as one skill with a mode | M |
| 13 | **`donut` / `pie`** | Part-of-whole. Low scientific value — build last, or not at all | S |
| — | `survivalplot`, `cumulativeincidenceplot` | **LATER** — needs clinical time-to-event data Selom does not ingest | L |
| — | `phyloplot` | **REJECT** — out of scope (`plan.md` §3) |
| — | `rocplot` | **LATER** — needs a classifier surface Selom does not have yet |
| — | `multipanel` | **REJECT** — the editor owns layout (`plan.md` §3). Take *automatic A/B/C panel labelling* as an **editor** feature. |

### 3.3 What Selom has that cnsplots cannot do at all

`annotate` · `cepo` · `cluster` · `deg` · `diff_abundance` · the four **ERG** skills ·
`facs_gating` · `go_graph` · `integration` (Melody) · `mixing_metrics` · `normalization_qc` ·
`pathway` · `proteomics_de` · `pseudotime_genes` · `pvca` · `scorecard` · `ssgsea` ·
`string_network` · `trajectory` · `umap_scrna`.

Plus the three things that are the product: **an editable figure**, **provenance**, and
**auto-methods**. cnsplots renders an image and stops. **Parity is not the goal — it is the floor.**

---

## 4. Machinery worth taking (or deliberately not)

- **`_validation.py` — TAKE the pattern.** 21 named validators (`validate_time_to_event_data`,
  `validate_binary_column`, `validate_pairs_format`, `safe_division`…), each raising a message
  naming the function and column. Selom's equivalent is scattered per skill. A shared
  `skills/_validate.py` with the same shape is cheap and pays back on every new skill.
- **A large share of cnsplots' code is *matplotlib compensation* — and Plotly gives Selom it free.**
  This is the single biggest cost correction in the review, and it cuts the estimate rather than
  raising it. `helpers/_sankey.py` (15 KB) hand-draws a Sankey from vertical bars and strips
  **because matplotlib has no sankey primitive** — Selom emits Plotly's native `sankey` trace
  (`skills/sankey/run.py:34`). `helpers/_heatmap.py` (21 KB) subclasses PyComplexHeatmap purely to
  stabilise detached colorbar/legend axes; Selom sets Plotly axis domains directly. The SVG
  pipeline below is the same story. **None of those three helpers needs porting**, and a future
  session should not read their size as difficulty.
- **`_svg.py` — TAKE the goal, and the AGPL flag turns out to be moot.** Their pipeline is
  matplotlib → PDF → `mutool convert -O text=text` → SVG → *ungroup text, flatten clip groups,
  restore bold, un-subset font names*. That is what "opens cleanly in Illustrator" actually
  requires. **`mutool` is AGPL and must not go on the shipped path** — but Selom never needs that
  conversion: cnsplots round-trips through PDF only because *matplotlib's own SVG is poor*, and
  Kaleido/Chrome emits SVG with live `<text>` directly (verified, `parity-audit.md` §1).
  Selom's PDF stack is already licence-clean and was chosen with the same instinct —
  **`pypdfium2`** (BSD-3/Apache-2.0, wrapping Google's PDFium, the engine inside Chrome) plus
  **`pypdf`** (BSD-3), with `papers.py:16` stating outright that it *"Deliberately AVOIDS
  PyMuPDF/`fitz` (AGPL)"*. That stack covers text, raster and metadata, **not** vector PDF→SVG —
  and it does not need to. So the AGPL flag costs us nothing.
  What is still **unverified** is whether Kaleido's SVG is *flat* or a nest of `<g clip-path>`.
  **Owed check:** open a Selom SVG export and count group depth. If nested, a pure-Python
  post-process closes it — still no AGPL.
- **Defect-driven tests — TAKE the habit.** Of 30 test files, 7 are named `*_defects.py` /
  `*_regressions.py` (`test_heatmap_defects`, `test_crash_regressions`,
  `test_plot_behavior_regressions`…). Every bug becomes a named permanent test. Selom's
  `test_figure_encoding_integrity.py` is the same instinct; make it the convention.
- **The bundled agent skill — TAKE the packaging idea.** `_agent_skill/cnsplots/` ships a
  `SKILL.md` + `references/plot-catalog.md` *inside the Python package*, so any agent installing
  the library gets the usage contract. Selom's Skill Store could ship the same per skill.
  (Its *content* — "never invent thresholds or tests", treat `pairs` as an analysis choice — is
  already Selom doctrine, so there is nothing to learn there, only to confirm.)
- **`_settings.py` context manager — TAKE.** `settings.context(...)` applies style temporarily
  and restores it. Selom's style registry has no scoped-override equivalent; the editor will
  want one for preview-before-apply.
- **`datasets/gallery.py` + bundled CSVs — TAKE the idea.** Ships iris/tips/penguins/fmri/flights
  so every example runs with no data. Selom's plot-type picker (§6) needs exactly this to render
  a live preview before a user has uploaded anything.

---

## 5. Wiring — what "properly wired" means for each new skill

Every plot in §3.2 is not done until all seven hold. This is the checklist a build ticket closes
against, and it is why the count of plot types is the *small* part of the work.

1. **Real engine** in `skills/<id>/run_real.py` + a dependency-free stub in `run.py`.
2. **`skill.json`** — id, title, engine, omics, entrypoint, inputs, `param_spec`.
3. **Golden test** — the stub pinned (`tests/test_skills_golden.py` picks it up automatically).
4. **A smoke case** in `skills/smoke.py` `CASES` against a **real corpus file** — a missing case
   fails the ratchet, and the figure-integrity invariants apply automatically
   ([[selom-skill-smoke-matrix]]).
5. **Themed centrally** — no styling in the skill; `theme.py` handles it, new figure kinds get a
   `_KIND` entry.
6. **A Statistics table** (`skills/_table.py`) so the figure carries its numbers.
7. **Reachable** — a real FE call site, or `test_reachability_guard.py` fails it
   ([[selom-shipped-not-reachable]]). **This is where past work died** — `assemble-scrna`
   shipped with no surface.

---

## 6. The frontend — no source to copy, so this comes from Mobbin + what Selom already has

Adding ~16 plot types breaks the current model, where a skill is chosen by the engine's
recommendation or from a flat Skill Store list. At ~50 skills a scientist needs to *choose a
figure*, which is a picker problem. Mobbin pass (web):

- **[Asana — Add chart](https://mobbin.com/screens/3eb0a0c1-439f-4abd-b63e-4ea3f4c80b97)** —
  left rail of **categories**, right pane of cards, each card previewing the chart *with the
  user's own data semantics in the title*, and "Add custom chart" offered first. **TAKE the
  skeleton**: category rail + card grid maps directly onto Selom's plot families
  (distribution / relationship / matrix / sets / genomics).
- **[Google Analytics — Add Cards](https://mobbin.com/screens/29f7c7f5-854a-427e-94f3-6ecd9714ae07)**
  — search field, collapsible groups, multi-select with an "N of M selected" counter, and each
  card states its **chart type** and its **source** ("From 'Audiences'"). **TAKE** the search +
  the provenance line; a scientist choosing among 50 plots needs to filter, and the source line
  is where Selom's dataset lineage belongs.
- **[Whop — Select widgets](https://mobbin.com/screens/1bf39e9f-e8e3-4b78-b168-d843080b7270)** —
  live previews, and tiles that cannot render say **"No data available"** on the tile.
  **TAKE, and this is the one to elaborate** (below).
- **[Fibery — New Report](https://mobbin.com/screens/c6c99e44-475c-4cf6-9774-c5e87781f606)** —
  four generic types as grey isometric **illustrations**. **RULED OUT.** An abstract icon tells a
  researcher nothing about whether a plot suits their matrix, and it does not scale past a
  handful of types. If the picker shows art instead of data, it is the wrong picker.

### The elaboration — where Selom beats all four

None of these four know whether a chart *fits* the data; they offer everything and let you fail.
**Selom already has the answer to that**: the data-fit scorer (`engine/compat.py`, fit 0–100 +
confidence band, [[selom-data-fit-scorer]]).

So the picker is not a gallery — it is a **ranked, fit-scored gallery**: every tile carries its
fit against the *loaded dataset*, sorted best-first, and a tile that cannot work says **why**
("needs a condition column", "needs ≥3 replicates per group") instead of failing after the click.
Whop's honest empty state, driven by machinery Selom already shipped. That is the FE thesis of
this phase, and it needs no cnsplots source because cnsplots has none.

**Still owed at build time** (Mobbin is a standing rule on any FE work, and one search does not
cover a phase): the **figure surface** itself (F3), the **style/journal-pack picker**, and the
**significance-bracket editing** interaction — a user must be able to move a bracket the engine
placed. Run `fe-review` at the end of each.

---

## 7. Sequence

Everything below is autonomous — no owner input, no keys, no spend.

1. **F2.5a — the significance-annotation engine** (§1). One feature, six skills upgraded. Brings
   `add_count` and the `hue`/`order`/`hue_order` contract with it.
2. **F2.5b — the shared validator module** (§4), because every new skill in step 4 uses it.
3. **F2.6 — audit rows 21–23** (label collisions), already the standing NEXT. `adjustText` is
   the lead for row 22. These are defects Selom *and* cnsplots both have; fixing them is where
   Selom passes it.
4. **F4 — the plot types**, in §3.2 order, one commit each, closing §5's seven-point wiring
   every time. Stop and re-assess after **venn + forest + qq**: three shipped plots will say more
   about the real per-plot cost than this estimate does.
5. **F3 — the picker + figure surface** (§6), once there are enough plot types for a picker to
   be worth having. Mobbin first, `fe-review` at the end.

**Owed checks before the relevant step:** the SVG flatness check (§4) before claiming Illustrator
compatibility; a re-read of each `plots/*` module before porting it; per-dependency licence
verification at the moment it is proposed, never from §2's table alone.
