# Phase F — figure quality: port cnsplots into Selom

Owner-directed 2026-08-02: *"the plots in cnsplots look much better than ours … copy the code
(frontend and backend) of all its graphs/plots and integrate and elaborate it with ours. This
requires a full phase on its own and possibly massive overhaul in design (mobbin) and features."*

Source: <https://github.com/faridrashidi/cnsplots> · v0.6.0 · BSD-3-Clause · 552 stars · actively
maintained (last push 2026-08-02).

**Status: plan + spec written, nothing built.** This is a phase charter, not a ticket.

---

## 0. The premise is correct, and it is the point

Selom's figures do not look as good as cnsplots'. That is the finding, and everything here serves
it. Selom's differentiator is the *editable* figure with provenance and auto-methods — but a figure
a scientist would not put in a paper does not get to claim publication-ready, and "publication-ready
editable figures" is the product's own promise. **Visual quality is not polish here; it is the
product.**

So the goal of Phase F is stated as a test, not a preference:

> Put a Selom figure and a cnsplots figure of the same data side by side. A reader cannot tell which
> came from which — and only Selom's is still editable.

---

## 1. Licence — copying is allowed, and no clean room is needed

**cnsplots is BSD-3-Clause.** We may read it, copy it, modify it, ship it commercially, in source or
binary. The only obligations are **attribution** (retain the copyright notice, licence text and
disclaimer) and not using the author's name to endorse Selom. No copyleft, no SaaS trigger.

The brief asked for a clean room. **A clean room is the expensive path a *copyleft* licence forces
on us** — the Harmony precedent, where the standing rule is literally "do not read the GPL repo"
([[selom-harmony-reimplementation]], [[selom-harmony2-scope]]). None of that applies. Insisting on a
clean room against BSD-3 would cost weeks and buy nothing. **We copy, and we credit.**

Mechanics: `LICENSES/cnsplots-BSD-3-Clause.txt`, a `ported from cnsplots (BSD-3-Clause)` header on
every file that carries ported values, and a row in `docs/external-tools-study.md`
([[selom-external-tools-study]]).

**Dependency triage is separate and is owed at decision time, never from this list**
([[license-decision-framework]]): cnsplots' runtime set pulls `lifelines`, `comprisk`,
`pycomplexheatmap`, `statannotations`, `upsetplot`, `matplotlib-venn`, `palettable`, `adjustText`,
`biopython`. `gseapy` and `scanpy` are already cleared BSD ([[selom-gseapy-is-bsd]]); **biopython is
not plain BSD**. This only bites if we *depend on* those packages — §3 says we mostly should not.

---

## 2. The one hard constraint, and where the beauty actually lives

**cnsplots is matplotlib/seaborn: it renders images.** Selom's figure is a **Plotly spec** that opens
in the editor, is mutated by JSON-Patch, carries provenance and emits auto-methods
([[selom-figure-editor-architecture]]). A matplotlib figure arriving in Selom is a PNG or SVG — it
cannot be opened in the editor, re-themed, or patched.

So "copy the code" has a right layer and a wrong layer, and the distinction is not pedantry — it
decides whether the copied work survives contact with the product:

- **Wrong layer — the render calls.** `ax.boxplot(...)`, the figure/axes construction, `multipanel`.
  Copying these produces static images and a second class of figure that looks like a Selom figure
  and does none of what one does ([[unify-on-superior-framework]]).
- **RIGHT layer — the styling.** This is where the visual quality actually lives, and it ports
  **value for value**: exact font families and sizes, tick length/width/direction, spine treatment
  (which spines are dropped), line widths, marker sizes, legend geometry and placement, margins and
  padding, panel dimensions, palette hex values, and the annotation geometry for significance
  brackets. **That is real code copying** — it is just `_settings.py` / `_setup.py` / the palette
  tables rather than the drawing calls.

A matplotlib box plot and a Plotly box plot of the same data look different **almost entirely because
of those values**, not because of the renderer. That is the good news: the quality gap is portable.

**Where the maths is the work, port or depend freely** — venn set arithmetic, ROC/AUC, survival
curves, clustering order. Those emit numbers; Selom draws them in Plotly.

> **Open question for the owner, worth one decision (deferred to next week):** if a specific plot is
> genuinely better as a static publication image and editability is worthless for it, Selom *could*
> add a static-render skill class. My recommendation is **no** — it forks the product's core promise —
> but it is a real option and it is yours, not mine. Nothing in this plan depends on it.

---

## 3. Scope of the phase

### F1 — Visual parity audit (do this first; it makes everything else measurable)

Render Selom's existing skills and cnsplots' gallery **on the same data**, put them side by side, and
write down every difference: typography, weight, tick treatment, spines, grid, legend, whitespace,
colour. Without this the phase is taste; with it, it is a checklist.

Output: `docs/cnsplots-port/parity-audit.md`, with images. This is the artifact that proves the
phase worked when it is re-run at the end.

### F2 — The theme overhaul (the core of the phase)

Port the styling values into Selom's theme layer. `skills/theme.py` is applied centrally in
`run_skill` ([[selom-publication-theme]]) and `skills/styles.py` already exists, so this is one
well-placed change rather than 36. This is also the already-planned
**`theme.py` → named style registry** refactor ([[selom-journal-styles-feature]]) — Phase F is what
finally forces it.

Includes **journal style packs**: Cell / Nature / Science column widths, panel geometry, font sizes.
cnsplots encodes these, which is the tedious research. **Verify against each journal's own author
guidelines before shipping** — cnsplots is a lead, not a source of record.

### F3 — Frontend: the editor and the design overhaul

The owner's "frontend and backend" and "massive overhaul in design (mobbin)". Two parts:

- **The figure surface** — how a figure is presented, framed, and exported in the editor. **Mobbin
  first, standing rule** (owner-directed 2026-08-02): `search_screens` for chart/report surfaces in
  mature analytics and scientific products. Comparison instrument, not template — record what is
  ruled **out**.
- **Style/theme controls** — a user picking "Nature" must see it apply live. This is the inspector's
  job and it does not exist yet.

Run `fe-review` at the end of F3 (it conducts **ui-ux-pro-max** + **impeccable**), per the playbook.

### F4 — The plot inventory gaps

Selom has 36 skills and already covers most of cnsplots' basic + scientific band: boxplot, heatmap,
corr_heatmap, dotplot, volcano (`deg`), gsea/ssgsea, sankey, **upset**, pca, regression,
violin/strip/bar, scatter/line, go_graph, string_network, trajectory, pvca.

Real gaps, cheapest and most-wanted first:

| Gap | Why |
|---|---|
| **Venn** | Owner named it. Selom has `upset` but **no venn**, and for 2–3 sets — most DE-overlap figures — a venn is what reviewers expect. |
| **Significance annotation** (brackets + stars) | The highest-value non-plot item. The ERG Fig-1E work hand-rolled exactly this ([[selom-erg-manual-marks]]); every boxplot wants it. |
| **Forest** | Effect size with CI. Selom's DE output is already the input. |
| **QQ** | p-value calibration — makes an inflated test *visible*, diagnostic for work Selom already does. |
| **Confusion matrix** | Serves `annotate` / `markers`. Trivial heatmap variant. |
| **Ridge** | Distribution-per-group; the companion to `composition`. |
| **Slope · lollipop · donut** | Cover before-after, ranked-single-value, part-of-whole — three shapes currently forced into a bar chart. |

**LATER** — survival (Kaplan–Meier) and cumulative incidence are excellent but need clinical
time-to-event data Selom does not handle, plus `lifelines`/`comprisk` triage. Phylo and genomics
tracks are out of scope.

Each gap ships as a normal Selom skill — real engine, Plotly spec, table contract, golden test — and
is **independently shippable. Do not batch them.**

### Rejected, deliberately

- **The matplotlib render path** (§2).
- **`multipanel`, the layout manager.** Selom's editor owns layout; a panel grid computed in Python
  is precisely what direct manipulation replaces. Take automatic A/B/C panel labelling as an
  *editor* feature; reject the implementation.
- **The CLI + bundled agent-skill installer.** Selom is a product, not a plotting CLI.
- **Wholesale palette import.** Take named journal palettes into the style registry; do not add a
  competing palette system. Check every categorical palette against the `dataviz` accessibility
  rules — a palette that looks good and fails colour-vision deficiency is not publication-ready.

---

## 4. Sequencing and cost

**F1 → F2 → F3 → F4**, and F4's items are individually shippable at any time after F2.

F1 and F2 are where the owner's complaint gets fixed; they are also the cheapest. **F3 is the
expensive one** — a design overhaul is open-ended by nature and should be scoped by the audit, not
by ambition. F4 is a long tail of small, well-understood skills.

Honest estimate: **F1 ≈ ½ session · F2 ≈ 1–2 · F3 ≈ 2–4 · F4 ≈ ½ per plot.** F3's spread is the
uncertainty, and it narrows once F1 exists.

## 5. One check owed before F2

cnsplots advertises Illustrator-compatible SVG with **editable fonts, not text-to-path**. Does
Selom's Kaleido SVG export keep `<text>` as text, or outline it? If it outlines, every "vector
export" Selom has shipped is not actually editable in Illustrator — a claim the product makes.
One-line check, potentially a real defect.
