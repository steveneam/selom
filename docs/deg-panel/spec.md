# The differential-expression panel — `deg` + `diff_abundance`

**Status:** written 2026-08-05 · board `NEXT#1(d)`, converged with `NEXT#2`'s level widget
**Scope:** two skills — 23 API-only knobs (`deg` 16, `diff_abundance` **all 7**) and 35 untriaged
prose waivers (`deg` 26 across both companion modules, `diff_abundance` 9).

---

## 0. Why this one wanted a spec

Every previous `API_ONLY_KNOBS` batch was an overlay: read the runner, name the knob, write the
help. `deg` is not that shape, and the board said so before I opened it. Three things make it
different, and each was confirmed by reading the runner's body rather than the guard line:

1. **`deg` is four disjoint engines behind one knob, and that knob is itself API-only.**
   `skills/deg/run_real.py:30-40` dispatches on `mode` to `_scrna` · `_bulk` · `_pseudobulk` ·
   `_timecourse`. The 18 declared params partition almost cleanly across them — `time_col` is
   meaningless on an h5ad, `groupby`/`method` are meaningless on a counts CSV. A flat panel of 18
   controls would be *reachable* and *wrong*: it would offer a user on single-cell data four knobs
   that their run cannot read.
2. **The knobs the panel needs are the knobs the prose is silent about.** The board's instruction —
   take `deg`'s 26 prose waivers *with* this spec, not piecemeal — is right for a reason worth
   stating: `method`, `normalization`, `sample_col`, `condition_col` and `min_cells` are the same
   params on both lists. Triaging them separately would mean reading the same four runner bodies
   twice and risking two different readings of the same code.
3. **`reference`/`treatment` are a *level*, not a column** — the widget `NEXT#2` scoped
   independently. `deg` and `diff_abundance` are 4 of its 6 target knobs.

---

## 1. What reading the runners found

This section is findings, not design. Everything below is cited and was confirmed in the source.

### 1.1 Six live printed-vs-computed lies in `companions/methods._deg`

The prose↔param guard is green on all six, because **it checks that a param is *mentioned*, not
that the sentence is *true*** — its known one-directional blind spot, the same one that produced
the `pvca` / `cepo` / `_boxplot` / `_gsea` families.

| # | The claim | What the run does | Cite |
|---|---|---|---|
| a | *"marker genes were ranked … with the Wilcoxon rank-sum test"* — unconditional | `method` is passed straight to `sc.tl.rank_genes_groups`; `t-test`, `logreg` and `t-test_overestim_var` are all accepted | `run_real.py:104` vs `methods.py:204` |
| b | *"ranked per `{groupby}` group"* — quotes the param | **When the requested column is absent the runner clusters the cells itself (Leiden) and groups by that.** The figure title carries the resolved name; the paragraph carries the requested one | `run_real.py:96-102` vs `methods.py:204` |
| c | *"summed per biological replicate (`{sample_col}`)"*, defaulting the word `sample` | Blank `sample_col` resolves through `_SAMPLE_FALLBACKS` — `sample`, `Sample`, `sample_id`, `donor`, `orig.ident`, `library`, `batch`. On an h5ad keyed `orig.ident` the paragraph names a column that does not exist | `run_real.py:116-130,193` vs `methods.py:175` |
| d | *"modelled as bulk RNA-seq with PyDESeq2 … tested with the Wald test"* + a PyDESeq2 **citation** | On `ImportError` the engine falls back to **log2 of mean CPM — no model, no test, no p-value at all** — and the paragraph and its three citations are unchanged | `run_real.py:374-381` |
| e | *"p-values corrected by the Benjamini-Hochberg procedure"* + a BH **citation** | Same fallback: there are no p-values to correct. This is the `_boxplot` "cites Welch and BH while returning `[]`" family, third occurrence | `run_real.py:374-381` |
| f | The default paragraph describes **both** the single-cell and the bulk path in one sentence | `mode="auto"` resolves to exactly one of them from the file extension. The reader is told about an engine that did not run — the `erg_flicker.view` family | `run_real.py:31-33` vs `methods.py:203-206` |

Two more that are silences rather than false sentences, and are owed a claim because they decide
what was **measured**:

- **`normalization="tmm"` can silently degrade.** `_fit_deseq_with_tmm` is wrapped in a bare
  `except Exception` that falls back to median-of-ratios and records it *only* in the figure
  subtitle as `TMM unavailable` (`run_real.py:350-356`). `_diff_abundance`'s paragraph describes
  this exact knob; `_deg`'s never mentions it.
- **Two sample-exclusion criteria are undisclosed.** `min_cells` drops replicates from a pseudobulk
  contrast and `min_count` drops genes from every DESeq2 path (`run_real.py:235-237,273,320-321`).
  Both are disclosed in the figure subtitle and in neither companion.

`covariate_col` is a third of this shape and is the one that must **not** simply be quoted: the
adjustment is applied only when the column resolves to ≥2 distinct levels
(`run_real.py:619-621`), so a covariate naming a constant column is silently ignored.

### 1.2 A figure defect: the scRNA bar is labelled `log2 fold-change` and carries a z-score

`_scrna` plots `res["scores"]` (`run_real.py:109`). Scanpy's own docstring for
`rank_genes_groups` says `scores` stores *"the z-score underlying the computation of a p-value"*,
and exposes `logfoldchanges` as a **separate** field
(`.venv/…/scanpy/tools/_rank_genes_groups.py:601-609`). `_bar` then titles the x-axis
`"log2 fold-change"` and heads the Statistics column `"log2 fold-change"`
(`run_real.py:447,454`).

So on the **default path of the flagship DE skill** — and on the corpus smoke case, which pins
`method: wilcoxon` (`skills/smoke.py:120`) — the axis, the table header and the exported CSV all
name a quantity the figure does not contain.

**Bounded honestly:** this does *not* currently reach a reproduction score. `extract.readers.
de_counts` requires an explicit `direction` column and `deg`'s table has none, so `_read_de_table`
returns `None` and the legend's `_de_split` contributes nothing. It is a user-facing and
export-facing lie, not a scored one. (`diff_abundance` **does** emit `direction`, so its table is
`de_counts`-readable — its numbers are genuinely log2 fold-changes and stay correct.)

### 1.3 ⚑ An eighth layer of *shipped ≠ reachable*: a param no declaration knows about

`skills/contract._execute` merges caller params over the defaults and passes the result to the
runner **unfiltered** (`contract.py:78,90`); `validate_param_ranges` skips any key absent from
`param_spec` (`contract.py:164-166`); and `resolved_params` passes unknown keys through into the
recorded provenance bundle (`contract.py:210-212`).

`deg`'s runner reads two params its `skill.json` does not declare:

- **`group_regex`** (`run_real.py:78`) — overrides the replicate-suffix strip that derives bulk
  group labels from column names. It decides *what the two groups are*.
- **`label_val`** (`run_real.py:198`) — an undocumented alias for `label`.

They are accepted, honoured, and recorded. But because every guard in this repo is driven by the
*declaration*, **none of them can see these**: `API_ONLY_KNOBS` iterates the declared spec, the
prose↔param guard compares against `load_skill(id).param_spec`, and `paramFieldsFromSpec` drops an
overlay key with no spec entry (`warnDeadKnob`) so a control can never be built for one.

The seven known layers were all *the user cannot get to it* or *the user is told it isn't there*.
This is a new one: **the param works, and no declaration admits it exists** — so the reachability
backlog cannot count it and the honesty backlog cannot audit it. See `[[selom-shipped-not-reachable]]`.

### 1.4 Two enum knobs are declared as bare strings, so an unknown value runs a *different engine*

`mode` and `method` carry no `options` in `skill.json`, so `validate_param_ranges` cannot reject
one. `run()` tests the three known mode families and then **falls through to `_scrna`**
(`run_real.py:34-40`) — it lowercases but does not strip, so `mode=" bulk"` silently runs the
single-cell engine. An unrecognised `method` instead raises from inside scanpy.

### 1.5 `diff_abundance` renders a literally empty parameter panel

It has no entry in `PRESENTATION` at all — the `sankey` shape, where a blank panel is
indistinguishable from "this skill has no options". All 7 of its knobs are API-only, including
`reference`/`treatment` (which `deg` at least exposes as text boxes) and `normalization`, whose
default (`tmm`) differs from `deg`'s (`deseq2`) for a documented reason the user cannot see.

---

## 2. Decisions

### D1 — The panel is **mode-first and mode-gated**, using the existing `showWhen`

`mode` becomes the first control: a `select` whose options name the *method*, not just the mode
(`Auto` · `Single-cell markers` · `Bulk RNA-seq` · `Pseudo-bulk` · `Time-course`). Every
engine-specific knob carries `showWhen: {key: "mode", equals: "<mode>"}`. Shared knobs (`top_n`,
`reference`, `treatment`) stay ungated.

> **⚑ CORRECTION, made while building.** This decision originally read *"under the default `auto`,
> only the shared knobs render"*. Building it showed that would be a **regression**:
> `reference`/`treatment` are visible text boxes today, and hiding them until the user names a mode
> takes a working control away in the name of fixing reachability — the `fdr_threshold` lesson (a
> new gap created by the fix for a gap). The rule that replaces it is tighter and needs no guess:
> `auto` resolves to exactly **two** of the four engines (`.h5ad` → scRNA, anything else → bulk;
> `run_real.py:31-33` — pseudo-bulk and time-course are *never* auto-selected), so **`auto` shows
> the union of those two engines' knobs and hides the other nine.** Everything reachable today
> stays reachable, nine knobs still come off the default panel, and `mode`'s help states the rule
> rather than leaving the mixture unexplained.

**Mobbin — the pattern it ruled OUT is the useful half.** The obvious answer to "four engines, one
choice" is a radio-card chooser with a description per option, and it is well attested:
[Wise](https://mobbin.com/screens/25abbcc5-bf34-47f2-9ffd-deac17910720),
[User Interviews](https://mobbin.com/screens/5736458c-508b-4917-9c4f-d2429feeca05),
[Gusto](https://mobbin.com/screens/596eaa91-c1df-4424-a958-cb0f8d340086),
[Revolut Business](https://mobbin.com/screens/9a470d89-52f7-49bf-8aeb-07d89658ee13),
[Cake Equity](https://mobbin.com/screens/00538b25-9fc2-4298-a5e5-b7d6401191cc). **Every single
instance is a full-page step in a wizard**, consuming the viewport, with a Back/Next pair. Selom's
param panel is a narrow dock inside the Workbench and there is no wizard step to host one — so the
pattern is **not available to Selom**, not merely unchosen.

What *is* transferable, and is adopted:
- **A mode select with the conditional block rendered directly beneath it**, which is exactly how
  [Copilot](https://mobbin.com/screens/48fc4413-ba3a-4966-b1cf-b6a9ad369373) presents
  `Visibility → Custom visibility → Show if …` and how
  [Cloudflare](https://mobbin.com/screens/0276ab05-a2e6-4004-95cf-1ab994f34267) stacks its
  operator/value token sections.
- **Gusto's per-card bullet list**, compressed: the thing that makes those cards work is that each
  option states *what it does*, not just its name. In a select that has to live in the option
  label and the help text — hence `Pseudo-bulk (sum per replicate, then DESeq2)` rather than
  `Pseudobulk`.

**Why `showWhen` (hide) and not `enabledWhen` (grey out):** the ERG precedent for `enabledWhen` is
a knob that is *inert* under the current setting but belongs to the same figure. These knobs belong
to a **different engine** — `time_col` is not a disabled option on a single-cell run, it is not
part of that analysis at all. Review finding (g) ("`showWhen` shifts the grid with no cue") is
answered by the mode select sitting directly above the fields it governs, which is the Copilot
shape; the cue is positional, and the fields never move without the user changing the control
immediately above them.

### D2 — A new `level` widget: pick one level from a chosen column

`type: "level"` with `levelsFrom: "<sibling column field key>"`, resolved per render the way
`pairs` already is (`visibleParamFields` → `resolvePairsField`). It is a single-select over that
column's real level names, sourced from `design.group_candidates[].levels[].name` — data the FE
already fetches and persists, so it costs no request.

**Resolution rule, and the one place it differs from `pairs`:**

1. If `levelsFrom` names a sibling field and that field has a value, offer that column's levels.
2. **If the sibling is blank *and* the context carries exactly one group candidate, use it.**
3. Otherwise fall back to `text` — the field it has always been.

Rule 2 is the addition, and it exists because of a shape `pairs` never met. For a **bulk counts
CSV** the contrast levels come from the sample-column *names*, which `questionnaire.py:189`
publishes as a single candidate under the `__column_names__` sentinel — there is no column field to
name it, because there is no column. The design-sheet branch (`:136`) and the time-course branch
(`:181`) each publish exactly one candidate too. So "when the file offers exactly one grouping there
is nothing to disambiguate" covers all three with one rule and stays strict on h5ad, which usually
has several.

**What is deliberately NOT done: no fallback to `best_group`.** `params.ts:60-64` records that
`design.best_group` is not threaded because a chart skill's auto-detect is a different rule from
the engine's contrast pick. That reasoning is scoped to chart skills and it would be tempting to
say `deg` is the exception — `best_group` is *literally* computed as the deg contrast pick, and
`engine/questionnaire._obs_aliases()` imports `deg.run_real`'s own `_CONDITION_FALLBACKS` directly
rather than shadow-copying it (`questionnaire.py:426-431`), so the two agree **whenever an alias
column is present**.

They diverge when none is: the runner **raises** (`_resolve_obs_col`, `run_real.py:130`) while
`best_group` falls back to the lowest-cardinality candidate. A widget built on that fallback would
offer levels for a run the backend refuses. Not worth one rule with an exception in it — so
`condition_col` must be chosen, and its *placeholder* shows the detected column name so choosing it
is one click.

`reference_guess` annotates the matching option (`control — likely reference`) and **never
pre-selects**: the backend already defaults the contrast when exactly two groups exist, and writing
a value into the param would turn an inferred default into a recorded user choice.

### D3 — Obs columns come from `groups`, not `columns`

Review finding (f): `resolveColumns` reads `ctx.columns`, which is `[]` for an h5ad by construction
(`engine/compat.py:175`), so a `column` widget on a single-cell knob is a text box on exactly the
files it consumes.

`deg`'s and `diff_abundance`'s obs knobs therefore resolve against `ctx.groups` (the real,
level-carrying obs columns) rather than `ctx.columns`:

| Knob | Source | Widget |
|---|---|---|
| `condition_col`, `label_col` (both skills) | `design.group_candidates[].key` | obs-column select |
| `sample_col` (both skills) | `design.sample_col_candidates` — built for exactly this and never threaded | obs-column select |
| `groupby` (`deg` scRNA) | `design.group_candidates[].key` | **combobox (pick-or-type)** |
| `group_col`, `group_val`, `time_col`, `covariate_col` | a separate **design sheet** the context does not carry | stays `text`, honestly |

`groupby` is the combobox and the rest are selects, for the reason review finding (f) already
gives: `leiden` does not exist until the run. A select would make the runner's most common resolved
value unofferable; a free-text box alone hides the columns the file does have. Pick-or-type is the
only honest shape.

`ParamDataContext` gains one optional field, `sampleColumns?: string[] | null`, mapped 1:1 from
`design.sample_col_candidates` at the two existing construction sites
(`workbench-panel.tsx:117`, `project-workspace.tsx`). No new request, no new backend field.

### D4 — `deg.normalize` joins the shared scRNA block

`params.ts:251-253` already states the conclusion and defers the action to this spec: `deg`'s
`normalize` is `to_bool(params.get("normalize", True))` gating
`normalize_total(1e4)` + `log1p` (`run_real.py:92-94`) — byte-identical to the eleven skills in
`scrnaNormalize()`. It is spread into the `deg` overlay under `showWhen: mode=scrna`, and the
comment block loses its "left out only because" clause.

`deg.groupby` does **not** join `scrnaGroupby()`. That block's five members all draw the figure
*over* the grouping (dotplot rows, violin categories, PAGA nodes); `deg` uses it to pick which
group's markers get ranked and then shows **one** group (`res["names"].dtype.names[0]` —
`run_real.py:106`). Same key, adjacent-but-different job — the `pvca.normalize` rule, applied to a
case where the difference is subtle rather than obvious.

### D5 — Prose: a sentence where the param answers, `layout.meta` where only the run does

Following the three existing lifts (`meta.significance` · `meta.adaptation` · `meta.clustered`),
each written **only when it differs from the param-derived answer**, so every default run stays
byte-identical and no golden moves.

**Get a sentence and leave the waiver list** (the param is the answer): `method` · `normalize` ·
`min_count` · `min_cells` · `time_col` · `label_col` · `group_col`/`group_val`.

**Ride `layout.meta` as a `VIA_OUTCOME` fact** (only the runner knows):

| Fact | Answers | Because |
|---|---|---|
| `_de_mode` | which of four engines ran | `mode="auto"` resolves from the file at run time (1.1f) |
| `_de_groupby` | the column actually grouped on | Leiden fallback (1.1b) |
| `_de_sample_col`, `_de_condition_col` | the obs columns actually used | alias resolution (1.1c) |
| `_de_engine` | `pyDESeq2 (Wald)` \| `… TMM norm` \| `… TMM unavailable` \| `CPM log2FC (pyDESeq2 absent)` | the fallbacks in 1.1d/e and §1.1's TMM degrade — **and this one governs the citations**: no PyDESeq2/BH citation may be emitted on the CPM path |
| `_de_covariate_adjusted` | whether the time-course adjustment fired | ≥2-levels gate (§1.1) |

**Keep a waiver, with a verdict:** `label` is `IN_METHODS` for the legend (the paragraph carries
the restriction; a caption is one sentence about one figure). `top_n` on the bulk paths is a **cap**
(`.head(top_n)`) not a count, so the sentence says "up to" — the `ssgsea.top_n` correction.

There is no `OWED` verdict, per the guard's own rule: a param whose fix is owed gets the fix.

### D6 — The `log2 fold-change` mislabel is fixed at the label, not the value

The scRNA path keeps ranking by z-score — that is scanpy's marker ranking and changing it would
change every figure. What changes is that the axis and the Statistics column **say what they hold**,
resolved from the same `_de_mode` fact: `Wilcoxon z-score` (or the method's own statistic) on the
scRNA path, `log2 fold-change` on the three DESeq2 paths.

**Blast radius, checked:** `tests/golden/deg.json` pins the **stub** (`run.py:_stub_figure`, the
hard-coded PBMC gene list), not the real engine, so a `run_real._bar` label change does not move it.

> **⚑ CORRECTION, made while building.** This paragraph originally said the stub's own
> self-contradiction — axis `"score (signed)"`, table column `"log2 fold-change"` for the same
> numbers (`run.py:62,69`) — would be fixed by moving the axis, "which **does** move the golden by
> exactly one string." That was the wrong direction. The stub's numbers are invented and are not a
> fold change of anything, so `"score (signed)"` is the **honest** label and the TABLE is the half
> that lies. Moving the table to meet the axis fixes the contradiction, is the more truthful of the
> two labels, **and** moves no golden — the golden pins the figure, from which the table is popped
> before capture (`contract._execute:94`). Strictly better on all three counts than what was
> specified.

### D7 — Backend: declare the enums, declare the undeclared

Three one-line `skill.json` changes, each closing a hole named above:

- `mode` gains `options` (§1.4) so an unknown value is a **400 with a message** instead of a
  silent single-cell run.
- `method` gains `options` (`wilcoxon`, `t-test`, `t-test_overestim_var`, `logreg`) so it fails at
  the boundary instead of deep inside scanpy — and so the select has a source of truth.
- **`group_regex` is declared** (§1.3). It changes what the two bulk groups *are*, so it must be
  visible to the guards; it renders under `showWhen: mode=bulk`. `label_val` is **deleted** from
  the runner instead — it is an undocumented alias for `label`, and an alias that no declaration
  mentions is a second name for one knob, not a feature.

---

## 3. Rejected

- **Radio cards for `mode`** — Mobbin-attested five times over, every instance a full-page wizard
  step. See D1.
- **Splitting `deg` into four skills.** Tempting given four engines, but `mode="auto"` is the
  default path and the *right* one for most users: it reads the file and picks. Four skills would
  force that choice onto every user up front and break every stored figure's `skill_id`.
- **Letting `reference`/`treatment` fall back to `best_group`'s levels** — D2, and the reason is
  the alias-absent case where the backend refuses the run.
- **Re-ranking the scRNA path by `logfoldchanges`** to make the existing axis label true. It is
  available for `t-test`-like methods only (scanpy's docstring), so it is `None` on the default
  Wilcoxon path — the fix would break the default it was meant to fix.
- **A `VIA_OUTCOME` waiver for `method`.** The param *is* the answer here: unlike `groupby` there is
  no fallback, so the sentence can quote it directly and the cheaper fix is right.

---

## 4. Slices

| # | What | Leaves behind |
|---|---|---|
| 1 | The `level` widget + `sampleColumns` context + guards | `NEXT#2`'s level half closed; reusable by `slope.levels` |
| 2 | `deg` overlay (16 knobs, mode-gated) + D4 + D7's `skill.json` changes | `API_ONLY_KNOBS` −16 |
| 3 | `diff_abundance` overlay (7 knobs) | `API_ONLY_KNOBS` −7 → **75 → 52, 12 skills → 10**; no more empty panel |
| 4 | The prose fixes + the `layout.meta` lifts + D6's labels | `PROSE_SILENT` untriaged **166 → 131** |
| 5 | `browser-verify` the panel end to end on the real corpus | proof the batch is reachable, not just guarded |

Slices 2 and 3 are independent of each other; 4 depends on nothing but is written last so the
`_de_mode` fact is available to D6's labels.

## 5. Guards

Extending what exists, per the repo rule that a new invariant joins an existing guard test:

- **`params.test.ts`** — the `level` widget's three resolution branches (sibling · sole-candidate ·
  text fallback), and that a context perturbs *nothing else* (the pin `pairs` already carries).
- **`registry-completeness.test.ts`** — `API_ONLY_KNOBS` shrinks by 23; the list is exact in both
  directions, so this fails until the waivers are deleted.
- **`test_methods_param_spec_guard.py`** — `_UNTRIAGED_CEILING` falls to 131, asserted by
  **equality**.
- **The new one, and the only genuinely new invariant here:** an assertion that
  `skills/**/run_real.py` reads no `params.get("<key>")` absent from that skill's `param_spec`
  (§1.3). This is the guard whose absence let `group_regex` exist for the life of the skill —
  every other guard in the repo starts from the declaration, so none of them can look the other
  way down the arrow. Expect a backlog on its first run; it carries a named waiver in the
  `API_ONLY_KNOBS` shape.

## 6. Open

Nothing blocking. One thing to flag on delivery: **`diff_abundance` defaults `normalization` to
`tmm` and `deg` defaults it to `deseq2`**, for a documented reason (the edgeR differential-abundance
convention limits compositional bias). Both defaults come from the backend spec and neither moves
here — but the two panels will now show the same knob with different defaults side by side, and the
help text has to say why rather than leaving it looking like drift.
