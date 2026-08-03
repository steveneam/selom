# F1 — visual parity audit: Selom vs cnsplots

Run 2026-08-03. Method + acceptance: `spec.md` §1. This is the artifact that makes F2 a checklist
instead of taste, and it is **re-run at the end of F2** with the same table as the proof.

Re-run Selom's side: `uv run python scripts/render_parity.py --out ../../docs/cnsplots-port/audit`
(needs `SELOM_DATASETS_DIR` + Chrome). cnsplots' side: `audit/render_cns.py`, in a throwaway venv
outside the repo.

---

## 0. The headline, before the styling

The premise of the phase — *"their plots look better"* — is correct, and the ported styling values
in §3 are real. But the audit found something the phase charter did not predict:

> **Three of the five audited plot types have a defect that is not a styling gap.** Two of them
> (`enrichment`, `heatmap`) are *unreadable*: one draws its dots at 1–3 **pixels**, the other
> silently mislays 7 of 17 clusters. No amount of theme porting fixes either.

So F2's checklist grew a prerequisite: **F1.5 — fix what is broken before restyling what is ugly.**
A restyle applied on top of these would produce a prettier unreadable figure.

The three defects, then the styling table.

---

## 1. Confirmed defects (not styling — correctness)

### D1 — `enrichment` dot sizes are 1–3 px, so the dot plot has no visible dots

| Selom (as shipped) | cnsplots, **identical numbers** |
|---|---|
| ![](audit/selom/dotplot.png) | ![](audit/cnsplots/dotplot.png) |

The skill emits `marker.size = [1, 2, 3, 3]` (the gene count per term) with
`marker.sizemode = "diameter"`. In Plotly `sizemode: "diameter"` means **size is a diameter in
pixels** — so the dots are literally 1–3 px across and the size encoding is invisible. matplotlib's
`s` is an *area in points²*, which is why the same array renders as readable dots on the right.

Two consequences, both visible above:

- the dot plot's entire size channel (genes per term) cannot be read;
- **there is no size legend at all**, so even at a correct size the reader could not decode it.
  cnsplots emits one by default.

**Fix:** scale the count to a pixel diameter with an explicit floor and ceiling (Plotly's
`sizeref`/`sizemin` exist for exactly this), and emit a size legend. Home: the `enrichment` skill's
figure builder, not `theme.py` — the theme must not learn a skill's data semantics (spec D1).

### D2 — `heatmap` loses 7 of its 17 clusters and orders the rest lexicographically

| Selom (as shipped) | Same spec, `xaxis.type="category"` + numeric order |
|---|---|
| ![](audit/selom/heatmap.png) | ![](audit/heatmap-fix-evidence.png) |

The trace's `x` is `['0','1','10','11','12','13','14','15','16','2',…,'9']` — **strings that look
like numbers, in lexicographic order**. Plotly coerces a numeric-looking string axis to a *linear*
axis, so the columns are placed at their numeric values instead of at consecutive category slots.
The result on the left: the matrix occupies ~55% of the canvas, ticks run to 16 past the data, and
the columns that should be clusters 10–16 are not readable as distinct columns.

The right-hand image is the *same figure spec* with two changes — `xaxis.type = "category"` and the
columns sorted `key=int`. All 17 clusters appear, evenly spaced, in cluster order.

This is a **data-integrity** defect, not a cosmetic one: a reader of the shipped figure draws
conclusions about cluster identity from column position, and the position is wrong. Lexicographic
ordering alone would be a defect even if the axis type were right (cluster 10 sits between 1 and 11).

**Fix:** pin `type: "category"` and sort cluster-like category axes numerically when every label
parses as an int. Worth auditing every skill that builds a categorical axis from `str(...)` labels —
this is a class of bug, not one instance.

### D3 — the declared house font `Inter` is loaded nowhere, so no figure ever renders in it

`skills/styles.py` sets the default style's `font_family` to
`"Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"`, and `lib/figure/figure-spec.ts:24`
repeats it for the browser. **Inter is not installed on the render box and is not loaded by the
frontend** — `app/layout.tsx` loads Geist (via `next/font`), and a repo-wide search finds `Inter`
named in exactly two places and fetched in zero.

Measured on this box: `fc-match Inter` → **DejaVu Sans**. So every server-side export (PNG/SVG/PDF
through Kaleido/Chrome) renders the house style in DejaVu Sans — a wide, low-contrast face that is
a large part of why the shipped figures read as "web chart" rather than "journal figure".

The sharper half: **the on-screen figure and the exported figure need not agree.** The browser falls
back through *its own* stack (`ui-sans-serif, system-ui`), the server falls back through fontconfig.
A viewer on macOS sees Helvetica Neue; the export is DejaVu. For a product promising
publication-ready output, the typography is currently unspecified rather than chosen.

The journal styles degrade *correctly* by comparison — `Arimo` → Liberation Sans, which is
metric-compatible with Arial by design. Only the default style falls off a cliff.

**Fix:** pick one and do it properly — bundle Inter (`next/font/local` + install the face for the
server renderer) **or** change the declared family to one present on both sides. Do not leave a
font named but never loaded.

### Not a defect: SVG export keeps live text

The check owed by `plan.md` §5 — does Kaleido outline text? — **passes.** A rendered SVG carries 16
`<text>` elements with the gene symbols intact and a `font-family` attribute (`audit/selom/box.svg`
is kept as evidence). Selom's "editable vector export" claim holds. Note this is *because* the
fallback still emits text; it is unrelated to D3.

---

## 2. The five plot types, side by side

Both sides are the **same numbers**: Selom's skills ran on the real corpus, and the resulting
arrays were fed verbatim to cnsplots, so every difference below is renderer or styling, never data.

Canvas: 6.0 × 4.5 in at 200 dpi. Selom lands exactly on 1200 × 900; cnsplots' figures are saved
with matplotlib's `bbox_inches="tight"` and so vary (863–917 px tall). cnsplots' 8 pt house type
is scaled ×2.4 to the audit canvas — it is tuned for a 150 pt (~2.1 in) panel, and at native size
on a 6 in canvas nothing would be legible. **Ratios are preserved, absolute point sizes are not**;
§3 quotes cnsplots' native values, not the scaled ones.

### box — `boxplot`, ERG b-wave by condition

| Selom | cnsplots |
|---|---|
| ![](audit/selom/box.png) | ![](audit/cnsplots/box.png) |

Selom: grid on, light-grey axis, left-aligned regular title, **one colour per box**. cnsplots:
gridless, black spines (bottom+left only), **bold centred title**, one colour for every box, and
`n=` counts under each category.

**Both handle the long category labels badly, and cnsplots handles them worse** — its labels
overlap into an unreadable smear, while Selom's rotated labels stay legible but collide with the
`condition` axis title and clip at the right edge. This is the audit's clearest "do not port"
row: long-label layout is a *shared* gap, and Selom is currently ahead.

### scatter — `pca`, JEV proteome samples

| Selom | cnsplots |
|---|---|
| ![](audit/selom/scatter.png) | ![](audit/cnsplots/scatter.png) |

The closest pair. Differences are the same base set (grid, tick colour, title weight/position) plus
marker size — Selom's 12 px points against cnsplots' small dots.

**Point-label collision is unsolved on both sides** (`PD2`/`PD4` overlap in both; `DR4`/`DR5` in
both). cnsplots does not apply `adjustText` in `scatterplot`, so there is nothing to port — this is
a genuine gap for F4 and, if Selom builds it, a differentiator rather than a catch-up.

### heatmap — `heatmap`, marker z-scores per Leiden cluster

| Selom | cnsplots |
|---|---|
| ![](audit/selom/heatmap.png) | ![](audit/cnsplots/heatmap.png) |

Dominated by **D2**. Beyond it: Selom draws a grid *through* a heatmap (meaningless on a filled
matrix), and its colour scale runs `RdBu` with **blue = high** — inverted from the genomics
convention where red is high expression. cnsplots renders `RdBu_r` (red high).

The `gene` axis title sits jammed against the row labels on Selom's side — the same automargin
collision as the dot plot.

### volcano — `volcano`, JEV EV proteome DE

| Selom | cnsplots |
|---|---|
| ![](audit/selom/volcano.png) | ![](audit/cnsplots/volcano.png) |

Selom's is **more informative** — it labels the top genes with leader lines, which cnsplots'
`volcanoplot` did not draw at all here. But Selom's labels overlap each other (`Aqp1` occludes its
neighbour), and each label carries a bordered white box that is heavy for print.

cnsplots is cleaner in the point cloud: smaller markers, a thin dashed zero line, an unframed
legend with a title, and a fourth class (`p_adj < 0.05` but sub-threshold fold change) that Selom
folds into `n.s.`.

*Caveat:* because cnsplots drew no gene labels, this pair does **not** compare label placement.

### dotplot — `enrichment`, GO/Reactome ORA

Covered as **D1** above.

---

## 3. The difference table — what F2 ports

Verdicts per `spec.md` §1.4. cnsplots values are its native settings (`cnsplots.settings`,
v0.6.0); Selom values are measured from `audit/selom-probe.json`.

| # | Heading | cnsplots | Selom today | Verdict | Note |
|---|---|---|---|---|---|
| 1 | Typography — title weight | `bold` | regular | **PORT** | Single biggest "reads as a journal figure" cue. |
| 2 | Typography — title position | `center` | `left` | **CHECK** | Journal-dependent; Cell/Nature captions sit below. Decide per style pack, not globally. |
| 3 | Typography — title:body ratio | 8 pt title / 7 pt ticks (1.14×) | 16 px / 11 px (1.45×) | **PORT** | Selom's title is proportionally oversized; flatten the ramp. |
| 4 | Typography — family | Helvetica → Arial → DejaVu | `Inter` (**never loaded**) | **PORT** | = **D3**. Declare a family that resolves on both sides. |
| 5 | Grid | `axes.grid = False` | on for box/scatter/volcano/heatmap | **PORT** | Publication default is gridless. Keep a per-style override. |
| 6 | Spines | bottom + left only, `black`, 0.5 pt | `showline` both, `#c4ccd4`, 1 px | **PORT** | Black at 0.5 pt vs light grey at 1 px is most of the "print vs dashboard" feel. |
| 7 | Tick geometry | len 2 pt, width 0.6 pt, pad 1 pt | len 4 px (3 pt), width 1 px (0.75 pt) | **PORT** | Selom's ticks are ~50% too long and heavy. |
| 8 | Tick colour | `black` | `#c4ccd4` (axis) / `#33404d` (labels) | **PORT** | Grey ticks lose contrast in print. |
| 9 | Axis margins | 5% on x and y | Plotly default | **PORT** | Stops data touching the spine. |
| 10 | Legend frame | `frameon = False` | already transparent | — | Already equivalent. |
| 11 | Legend density | `markerscale 0.5`, handles 0.7×0.7, pad 0.3 | Plotly default | **PORT** | Recovers plot width; Selom's legend block is wide. |
| 12 | Colour — categorical | palette encodes **something**; one colour otherwise | one colour per category always | **PORT** | Not a palette swap — a *rule*: colour only when it carries information (see box). |
| 13 | Colour — palette values | `Ecotyper1` default; `Cell`/`Nature`/`Science`/`NEJM`/`Lancet`/`JAMA`/`JCO` packs | Selom 8-colour + Okabe–Ito on journal styles | **CHECK** | Take the *journal* packs into the registry. Check each against the `dataviz` CVD rules before shipping — several are not colourblind-safe. |
| 14 | Colour — sequential | `gnuplot` | `Viridis` | **REJECT** | Viridis is perceptually uniform and CVD-safe; `gnuplot` is neither. Selom is right. |
| 15 | Colour — diverging direction | `RdBu_r` (red high) | `RdBu` (blue high) | **PORT** | Selom is inverted vs the field convention for expression z-scores. |
| 16 | Marker size — dense scatter | small points | 6.5 px (volcano), 12 px (PCA) | **PORT** | Only for dense clouds; PCA's large points are fine at n=10. |
| 17 | Background | `savefig.transparent = True` | white paper | **CHECK** | Transparent composites better into a multi-panel; white is safer for a naive download. Offer both at export. |
| 18 | SVG text | `svg.fonttype = "none"` (live text) | live text | — | Already equivalent; §1 check passed. |
| 19 | Annotation — significance | `pairs=` brackets + stars built in | none | **PORT** (F4) | Highest-value missing item; the ERG work hand-rolled it. |
| 20 | Annotation — group counts | `add_count=True` → `n=` per category | none | **PORT** | Cheap, and reviewers ask for it. |
| 21 | Long category labels | overlapping smear | rotated, legible, collides with axis title | **REJECT** | Selom is **ahead**; fix Selom's own collision, do not port. |
| 22 | Point-label collision | not solved (`adjustText` unused) | not solved | **REJECT** | Shared gap → F4 opportunity, not a port. |
| 23 | Axis-title vs long tick labels | n/a | title collides with labels (dot plot, heatmap) | **PORT**\* | \*Selom-only fix, no cnsplots source. Automargin must reserve for the title too. |
| 24 | Panel geometry | 150 × 150 pt panel, `figure_dpi 144` / `savefig 288` | figure-driven, export presets in mm | **CHECK** | Selom's mm-based presets are the better model; take cnsplots' *max panel height* research into the packs. |

**Ported: 14 · Rejected: 4 · Check (needs a journal guideline or a product call): 5 · Already equal: 2.**

---

## 4. What F2 should do, in order

1. **F1.5 first — D1, D2, D3.** They are correctness, they are cheap, and a restyle over them is
   wasted. D2's fix should be a sweep of every `str(...)`-labelled categorical axis, not one skill.
2. **The base restyle** — rows 1, 3, 5, 6, 7, 8, 9, 11 land as style tokens in `skills/styles.py`.
   All eight are single values; none needs a skill to change.
3. **The rules, not the values** — row 12 (colour only when it encodes) and row 15 (diverging
   direction) are decisions the theme applies per figure kind, so they belong in `theme.py`'s
   `_KIND` dispatch.
4. **Row 23 and Selom's own label collisions** — the layout defects the audit found that cnsplots
   does not solve either. These are where Selom can beat it rather than match it.
5. **The journal packs** (row 13, 24) — verify against each journal's author guidelines, ship
   unverified ones as `draft` (spec D4).

`spec.md` §2 already says the registry is the one home and that no skill learns about styling. That
holds for everything except D1/D2, which are skill-level data defects and must be fixed there.

---

## 5. Honest limits of this audit

- cnsplots' figures use `bbox_inches="tight"`, so their canvases differ from Selom's exact
  1200 × 900. Absolute whitespace is therefore **not** comparable; ratios and treatments are.
- cnsplots' type was scaled ×2.4 to the shared canvas. §3 quotes native values.
- `cns.volcanoplot` drew no gene labels on this input, so **label placement was not compared** on
  the volcano pair.
- The heatmap pair uses `imshow` + `cns.setup_ax` rather than `cns.heatmapplot`, which takes an
  `AnnData` and builds its own clustered figure — that would have compared two different *figures*
  instead of two renderings of one matrix. `setup_ax` is the cnsplots styling layer either way,
  which is what §3 is measuring.
- Five plot types, not 36. The base rows (1, 3, 5–9, 11) are style-wide and generalise; the
  figure-kind rows (12, 15, 16, 19, 20) were observed on the types listed and should be re-checked
  as each kind is restyled.
