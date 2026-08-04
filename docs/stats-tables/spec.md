# Spec — a figure may carry more than one Statistics table

Status: **written, awaiting owner review** (owner-directed 2026-08-04: spec first, *"continue
learning from cnsplots and Mobbin to refine the spec as well"*). Board row: `NEXT#4` in
`agent_handoff/CURRENT.md`. **No code has been written against this.**

> **Revised 2026-08-05 after `review-gauntlet`**, which confirmed two blockers and a design
> inconsistency against the first draft. All are fixed below, each marked where it landed: the
> consumer inventory named a **test-only** function as the reproduction consumer and missed
> `extract/readers.py`, the reader actually on the score's critical path (D4 correction +
> inventory); D1's normalizer would have silently disabled the **L3 synthesis gate**, converting
> every tableless skill to `NEEDS_RECIPE` (inventory + G2b); D6's "one field" was **two**
> (`ReproRun.table`); and D2 collapsed tables 2..N by default — which hides the p-values behind a
> click, *the exact failure D2 cites to rule tabs out*.

## What

`contract.run_skill_with_table` returns `(figure, StatsTable | None)` and the wire carries
`table: StatsTable | null`. Exactly one table. This spec widens that to **one *or more*** tables per
run, decides how the frontend presents them, and names what must change at each seam.

## Why now — the squeeze is shipped, not hypothetical

Three skills **throw a computed table away** on every run where the user asks for pairwise
statistics, because a second one has nowhere to go:

| Skill | Attached with no `pairs=` | Attached with `pairs=` | What is lost |
|---|---|---|---|
| `lollipop` | ranked values + bootstrap CI (`_value_table`, `run.py:196`) | pairwise p-values (`run.py:219`) | rank · n · the CI bounds — asymmetric, so neither end is readable off the dot |
| `boxplot` | five-number summary (L3 synthesis) | pairwise p-values (`run.py:120`) | the summary the box draws |
| `violin` | PubMed marker call (L3 synthesis) | pairwise p-values (`run.py:132`) | the marker call |

The overwrite is literal — `skills/lollipop/run.py:212` carries the reason in a comment:

> The figure carries ONE table (`contract.run_skill_with_table` → `StatsTable | null`), so asking
> for `pairs` swaps the ranked values out for the p-values that produced the drawn stars.

The trade is currently made the right way round: **stars drawn on a figure whose p-values appear
nowhere** is the worse failure. But it is still a trade forced by the wire shape, not by anything
about the science.

**And a second, quieter form is already in the tree: numbers packed into a title string because
there is no second table to hold them.**

| Skill | Scalars living in the title | Source |
|---|---|---|
| `confusion` | `n`, overall agreement %, Cohen's κ — *or* the named refusal when the label sets differ | `run.py:206-215` |
| `qq` | λ + its calibrated/inflated/conservative verdict, over N tests | `run.py:126-130` |
| `ridge` | the peak-normalization mode, the KDE/Silverman disclosure, the excluded groups | `run.py:255-263` |

Those are the run's **headline numbers**, and they are the least reachable thing in the product:
not sortable, not exportable to CSV, not diffable in compare (`lib/lineage/diff.ts` aligns *rows*),
and not readable by the reproduction metric extractor (`reproduction/core.py:853`, which reads
`columns`/`rows` and never parses a title). A κ of 0.31 that only exists inside a caption string is,
for every machine consumer in this repo, **not a result** — it is prose.

This is the same class the last three sessions kept finding — a computed thing the user cannot
reach [[selom-shipped-not-reachable]] — one layer further in: the value is computed, correct, and
attached, and the *contract* is what makes it unreachable.

## Scope

**In:** the wire shape, its normalizer on each side, the persistence seam, the FE presentation, and
the guards. **Out:** changing which numbers any skill computes. The unsqueezing of the six skills
above is named here as follow-up slices (§7) and specified only to the extent needed to prove the
contract fits them. `POST /extract` (`routers/extract.py:38`) keeps its single required
`table: StatsTable` — a digitized chart yields exactly one table by construction, and the endpoint's
FE type (`lib/extract/api.ts:16`) makes it non-optional; nothing there is squeezed.

## Decisions

### D1 — the wire becomes `StatsTable | StatsTable[] | null`, normalized at exactly one place per side

| Option | Verdict |
|---|---|
| **A. Union: `StatsTable \| StatsTable[] \| null`** | **CHOSEN.** Every one of the 27 native skills, every persisted `table_stats` row, and every existing consumer keeps working unchanged — a single table stays a bare object on the wire and in the database. Only a skill that opts into two emits a list. |
| B. Add a sibling `tables: StatsTable[]`, keep `table` as the first | **Rejected.** Two fields that must agree is a hand-maintained mirror, and this repo has just spent a session removing one (`seed.ts` → generated) with the lesson written down: *distrust any hand-maintained mirror of a live registry* [[selom-shipped-not-reachable]]. Even computed at one chokepoint it serializes the primary table twice, and it leaves every consumer free to read the shape that silently omits tables 2..N. |
| C. Always a list | **Rejected.** Breaks every persisted figure (`table_stats` is a stored JSON *object*), every consumer, and all 27 runners, to buy uniformity that (A) + a normalizer already buys. |

The known cost of a union is that it invites `Array.isArray(...)` to sprout at every call site. That
is a real risk and it gets a real answer, not a convention:

> **Exactly one normalizer per side, and it is the only place the union is narrowed.**
> Backend: `skills._table.as_tables(value) -> list[dict]` (`None → []`, dict → `[dict]`, list → list).
> Frontend: `lib/skills/stats-tables.ts` `asTables(value): StatsTable[]` with the same three cases.
> Every consumer calls the normalizer and then handles a list. No consumer branches on the shape.

Guarded structurally — see §6 G2. This is the `GENE_LIST_CUTOFFS` move applied to a type: declare
the shared thing once rather than let 20 call sites each restate it slightly differently.

`_table.table(...)` (the builder) is unchanged. A runner that wants two calls it twice and attaches
a list.

### D2 — the FE **stacks** N tables; it does **not** tab them

This is the Mobbin question, and Mobbin answered it by ruling the obvious pattern out.

**What mature tools do with several result tables under one figure** — three distinct patterns, and
the selection criterion is what separates them:

| Pattern | Seen in | Used when |
|---|---|---|
| **Tabs over the result region** | [Databricks SQL editor](https://mobbin.com/screens/2c405d3f-2a2d-4760-83df-f1a6e65035a8) — one query, then `Raw results │ Results │ Top-selling product │ +`; [Dub](https://mobbin.com/screens/d0f6f9cb-db3a-43e1-ba0c-97950979f096) — `Short Links │ Destination URLs` and `Referrers │ UTM Parameters` inside one card | The tables are **alternative slices of one measure**. Dub's two tabs are both "clicks, broken down by X". Only one is the answer at a time; the others are a re-query. |
| **Stacked titled sections, all visible** | [Fresha's Performance summary](https://mobbin.com/screens/35e1ecec-04ec-4e56-96e4-5e47c9585656) — `Sales summary` then `Sales performance`, read top to bottom; [Gorgias](https://mobbin.com/screens/83b1c501-cb7d-48b4-a689-be8f869d68d6) — `Top used tags` · `Trend` · `All used tags` as separate cards | The tables answer **different questions** and are read together. This is a report. |
| **One table + a selector** | [Amplitude](https://mobbin.com/screens/61faa12c-ea78-4eb7-ae47-cc8cf1bb1a0e) — a chart above, one `Breakdown by:` table below | It is really one table, parameterized. |

**Selom is the middle row, and the deciding fact is what one of the tables *is*.** The pairwise
p-value table is not an alternative view of the ranked values — it is the **provenance of marks
already drawn on the figure**. The stars are on the canvas; the numbers behind them must be visible
in the same glance, or the product reproduces the exact failure `lollipop`'s comment exists to
avoid, one level up: the stars are drawn, the p-values exist, and they are behind an unselected tab.

Three secondary costs of tabs, all concrete in this codebase:

1. **CSV export is per-panel** (`stats-panel.tsx:68`). Under tabs, "export the statistics" silently
   means "export the tab you are looking at".
2. **Compare diffs tables** (`lib/lineage/diff.ts`). A hidden table is a hidden diff.
3. Browser find-in-page and any print/PDF of the Statistics view see only the active tab.

**Chosen presentation.** The Statistics surface renders **one `StatsPanel` per table, stacked in
array order**, each keeping the collapsible header, sort, and CSV export it already has.

- **Every table is open by default, up to three; a fourth and beyond start collapsed.** The obvious
  alternative — open the first, collapse the rest — was in an earlier draft and is **wrong for the
  reason that ruled tabs out**: it puts the p-values behind a click. A collapsed panel and an
  unselected tab hide the same numbers; only the gesture differs. If the argument is that the
  pairwise table must be visible in the same glance as the stars it explains, then it must actually
  be visible.
  - This is affordable because `StatsPanel`'s body is already height-capped
    (`max-h-[300px] overflow-auto`, `stats-panel.tsx:133`) and its rows are already capped at
    `MAX_RENDER = 200`. Two or three open tables are a scrollable report — which is exactly what the
    Fresha/Gorgias precedent looks like — not a wall.
  - The cap at three is a wall-guard, not a preference: no skill in D4 wants more than two, so it
    only ever fires on something unforeseen.
- Each collapsed header still shows `title · N rows · M columns`, so a table beyond the cap
  announces what it holds. That is the affordance tabs would otherwise be buying.
- The `StatsView` heading (`stats-view.tsx:73`) currently prints the single table's title. With N it
  prints `Statistics` and a `N tables` count; each table's own title stays on its panel.
- **Nothing changes for a single table.** One table renders exactly as today: one panel, open,
  its title in the heading. This is a rendering invariant, not a preference — see §6 G3.

**Deliberately NOT adopted:** tabs (Databricks/Dub, ruled out above) and an accordion where opening
one closes the others (it makes reading two tables together impossible, which is the whole point).

### D3 — migration is a no-op for all 27 native skills, and it is enforced

`test_skill_table_contract.py`'s `NATIVE` set is **27 skills**, not the ~18 the board carried
(the board's number predates Lane B). Every one attaches a dict; the union accepts a dict; **no
runner changes.** The guard's job is to keep that true rather than to be believed:

- `test_native_classification_matches_source` keeps grounding `NATIVE` in the source. Extended, not
  restated: a runner may now attach a dict **or** a list, and the classification is unchanged by
  which.
- `engine.frame_schema.validate_result_table` gains the list case: **every element** must be a
  well-formed `StatsTable` (non-empty `columns`, rectangular `rows`). A ragged table in position 2
  must fail exactly as loudly as one in position 1. `test_frame_schema.py:139` already runs this
  over every native-table skill and continues to.

**The `NATIVE_L3_BOTH` exception is dissolved by this change, but not in it.** `boxplot` and
`violin` are declared native-*and*-L3 with an explicit justification — *"the two sources cover
disjoint **runs**, not disjoint skills"* — and that disjointness exists **only because one table
fits**. Once two fit, a `pairs=` run can carry the native pairwise table **and** the L3 summary
together, and the exception has no reason left.

That is a follow-up slice (§7), and the ordering is a rule, not a preference: **the exception is
removed in the same change that makes it false, never before.** Until then `NATIVE_L3_BOTH` stays
exactly as it is.

**L3 synthesis does not become automatic for everyone.** `routers/_run.py:309` reads
`if table is None: table = synthesize_table(...)`. It would be a one-line change to *append* a
synthesized table to every native result, and that would be wrong: a "Computed by Selom" table under
every native table is noise at best, and at worst it prints a second, differently-derived set of
numbers beside the skill's own with no statement of which is authoritative. Synthesis stays
**fill-when-absent**, plus a **declared** opt-in for the skills that genuinely want both.

### D4 — no `role` / `kind` field; order is array order, and selection is by content

The board asked whether a table needs an explicit role so the FE can order N predictably. **No.**

- **Ordering** is array order, and the runner is the only thing that knows which table is primary.
  A `role` enum would be a *second* ordering authority that can disagree with the first — D1's
  option-B smell in a different costume.
- **Labelling** — `title` already exists, is already rendered in the panel header, and is already
  how a user tells `Enrichment results` from `Enrichment (up / down)`. A multi-table runner **must**
  title each table (§6 G4).
- **Selection by meaning** is a real need in the reproduction reader, and it is met by **content**,
  not by a role. The live reader is `extract/readers.py` (`panel_extractor` → `read_metric` →
  `_read_count` / `_read_named_cell` → `_table_parts`), and it selects by **heuristics over the
  table's own contents** — the first string column is the key, the first numeric column is the
  value, `_direction_col` guesses a header then votes on content. Generalized to N tables it tries
  them **in array order and takes the first that yields the metric**, which is deterministic and
  needs no new field. Where two tables would both answer, first-in-order wins; the spec names this
  rather than leaving it to discovery.

  > **Correction, 2026-08-05.** An earlier draft cited `reproduction/core.py`'s `table_extractor`
  > (a `key_col`/`value_col` selector) as the reproduction consumer. **It has no production caller
  > — only `tests/test_reproduction.py`.** The live path is `routers/reproduction.py` →
  > `reproduction/runs.py` → `drive.py:140` → `extract/readers.py`. Generalizing `table_extractor`
  > would have generalized a function nothing calls while leaving the real reader to crash. Recorded
  > rather than quietly edited, because "a plausible-looking function with a matching docstring and
  > no caller" is the trap, and the same one this session hit twice.

If a future consumer needs to select a table by *meaning* rather than by content or position, that
is when `role` earns its keep. Adding it now is speculative.

**Which skills actually want 2+** — the evidence-ranked list, and nothing beyond it:

| Rank | Skill | Second table | Why it is not a caption |
|---|---|---|---|
| 1 | `lollipop` | ranked values **+** pairwise p | Both are computed today and one is discarded. |
| 2 | `boxplot`, `violin` | summary **+** pairwise p | Same, via the L3 path. |
| 3 | `confusion` | agreement scalars (`n`, `p_o`, κ) as a 1-row table | A κ inside a title is invisible to CSV, diff, and the metric extractor. It is the number the figure is *for*. |
| 4 | `qq` | λ + verdict + N tests as a 1-row table | Same argument; λ is the reason the skill exists. |
| 5 | `ridge`, `slope`, `forest` | — | **Leave alone.** Their title text is genuinely a caption (a bandwidth disclosure, an exclusion note, a test name), and `ridge` already carries bandwidth as a *column*. Splitting these buys nothing. |

Ranks 3–4 introduce a shape the product does not yet have — a **one-row scalar table** — and it is
worth saying plainly that this is the honest home for a headline number, not a compromise: it
sorts, exports, diffs, and extracts like every other table, which a caption does none of.

### D5 — the legend and the caption read the **first** table

`companions/legends.build(spec, params, figure=figure, table=table)` derives caption facts from the
table (`_facts`). A caption is one sentence about one figure, so it reads `as_tables(table)[0]`
(`None` when empty) and is otherwise untouched. Named here because it is the one consumer where
"handle a list" has a non-obvious right answer and silently reading table 1 of 3 would look like a
bug later.

### D6 — persistence: no DB migration, but TWO Pydantic fields reject a list

The durable path is already list-safe **except in two typed models** — the storage layer needs
nothing, which is exactly the kind of thing a spec exists to establish before code:

| Seam | Shape today | Change |
|---|---|---|
| `db/schema.py:232` · `alembic/0002:171` — `table_stats` | `JSON`, nullable | **None.** A JSON column stores a list. **No DB migration.** |
| `routers/figures.py:113` — `FigureIn.table_stats` | `dict \| None` | **`dict \| list \| None`.** Pydantic **rejects a list today** — a two-table figure would 422 at save, so without this the feature is silently un-persistable. |
| **`reproduction/core.py:283` — `ReproRun.table`** | `dict \| None` | **`dict \| list \| None`.** The second one, and it lands on the **ledger**: `drive.py:142` builds every `ReproRun` with `table=table`, so a two-table skill fails validation mid-drive rather than at an API boundary. |
| `library/figures.py:23,36` | passthrough by key | None. |
| `library/import_state.py:77` | `table_stats=f.get("table")` | None. |
| `lib/projects/sync.ts:105,133` | `table_stats` ↔ `Figure["table"]` | Type widens with `Figure["table"]`; no logic change. |
| `lib/projects/types.ts:198` — `Figure.table` | `StatsTable?` | `StatsTable \| StatsTable[] \| undefined`. |

Reconcile keeps its rule: `table` is a **server** field, so reconcile stays authoritative for it
[[selom-reconcile-preserves-client-only-fields]] — this spec changes its type, not its ownership.

## Consumer inventory — every place the union is narrowed

Each entry calls its side's normalizer (D1). **This list is the implementation checklist, so treat
it as a starting point to re-derive rather than a proof of completeness** — the first draft called
itself complete, named a test-only function as the reproduction consumer, and missed
`extract/readers.py`, which is the reader actually on the score's critical path. Before building,
re-run the sweep (`grep -rn 'table' --include=*.py` over the backend plus the FE inventory below) and
confirm each hit is either here or genuinely table-free.

**Backend**
- `skills/contract.py:74,110,123` — `_execute` / `run_skill_with_table` / `run_bundle_with_table`:
  the return type widens to `dict | list | None`. `figure.pop("table", None)` is unchanged — the
  runner decides the shape, the contract just carries it.
- `routers/_run.py:309` — L3 fill-when-absent (D3), `:336` legend (D5), `:338` the response.
- `engine/frame_schema.py:156` — validate every element (D3).
- **`extract/readers.py` — the reproduction metric reader, and the one on the score's critical
  path.** `_table_parts:68` does `table.get("columns")`, so a list raises `AttributeError`;
  `_title_total:134` does `(table or {}).get("title")`, and a non-empty list is truthy. All of
  `panel_extractor` · `read_metric` · `_read_generic` · `_read_count` · `_read_named_cell` ·
  `_title_total` · `_direction_col` · `_table_parts` take `list[StatsTable]` after `as_tables`.
  **⚑ `read_metric:326` gates L3 synthesis on `if table is None and skill_id:` — under the
  normalizer that is permanently False**, which would silently kill synthesis for every tableless
  skill and land them on `NEEDS_RECIPE`, a verdict `readers.py:19` declares reproducibility-axis
  with zero Selom-confidence defects. So it must be restated in normalized terms —
  `if not as_tables(table) and skill_id:` — and `[]` must behave exactly as `None` did.
- **`reproduction/drive.py:140`** — `computed = panel_extractor(panel, figure, table)` sits
  **outside** the `try` that ends at `:138`, and `drive_bundle` builds its panels in a bare list
  comprehension. So an extraction failure aborts the whole paper drive instead of degrading to the
  honest `RUN_FAILED` this module is built around. Move the call inside the `try` in the same slice.
- `reproduction/core.py:853` `table_extractor` — **test-only, no production caller** (see the D4
  correction). Widen it for consistency, but it is not the live path.
- `jobs/queue.py:47`, `ai/execute.py:207` — pass-through; no narrowing needed.
- `scripts/render_skill.py:127` — prints `table.get('title')` / `len(table.get('rows'))`. Not
  product code, but it is the standing "look at a plot" instrument and would break on the first
  two-table skill: `as_tables` + one line per table.
- `skills/_result_cache.py` — stores `table` opaquely. **Note:** the cache key covers
  (skill+version, params, input), so a runner that starts emitting two tables **must bump its
  `skill.json` version** or a warm cache serves the old single-table result. This is the existing
  rule; it is written here because this is the first change that makes it bite invisibly.

**Frontend**
- `lib/skills/api.ts:129` — `table?: StatsTable | StatsTable[] | null`.
- `lib/projects/types.ts:198` — `Figure.table` (D6).
- `lib/lineage/figure-table.ts:10` — `figureTable()` returns `StatsTable[]`; the L3 fallback
  (`deriveTable`) yields a one-element list or `[]`.
- `lib/lineage/diff.ts:98` — `diffTables` stays **table-to-table** (its row alignment is a
  single-table algorithm). The *caller* pairs them by index and renders N diffs; a table present on
  one side only diffs against an empty one, which `diffTables` already handles.
- `components/project/views/stats-view.tsx` — renders the stack (D2).
- `components/project/project-workspace.tsx` — derives `table`/`labeling` in the composition root;
  passes the list.
- `components/extract/chart-extractor.tsx:250` — **unchanged**, out of scope (§Scope).
- `mocks/stub-bundle.ts` — the mock mirrors the contract in the same change
  [[mock-must-mirror-backend-contract]], and must carry **at least one two-table fixture** or the
  mock proves only the shape that already worked.

**Gene labelling.** `StatsLabeling.geneColumn` is a column index, so it is meaningful only against
one table. Rule: **labelling attaches to the first table only.** `volcano` and `deg` — the only
figures with `geneLabels` — emit exactly one table, so this changes nothing today and states the
answer for the run where it would otherwise be ambiguous.

## §6 Guards — what must be true, expressed as tests

Each extends an existing test file rather than adding a parallel one, per the ratchet ladder.

- **G1 — every element validates.** `test_frame_schema.py`: a list whose second element is ragged
  fails with the same code as a ragged first element. *(extends the existing result-seam test)*
- **G2 — one narrowing site per side.** A structural test in the shape of
  `lib/structure.guard.test.ts`, scoped to **every FE source root this spec's own inventory touches
  — `app/`, `components/`, `hooks/`, `lib/`** (the `stats-view` and `project-workspace` narrowing
  sites are in `components/`, so a `lib/`-only scan would miss the ones most likely to drift):
  outside `lib/skills/stats-tables.ts`, nothing narrows a `StatsTable` union inline. The backend
  twin asserts `as_tables` is the only definition of the three-case narrowing. Prevents D1's known
  failure mode from arriving one call site at a time.
- **G2b — the L3 synthesis gate survives the union.** A tableless skill with a synthesizer still
  yields an `L3`/`synthesized` reading after the normalizer lands, and `[]` behaves exactly as
  `None` did (extends `tests/test_readers.py`). Without this, D1 silently converts every tableless
  skill's score into `NEEDS_RECIPE` — a plumbing regression wearing the costume of an honest
  verdict, which is the one failure mode this product cannot tolerate quietly.
- **G3 — the single-table path is byte-identical.** For a one-table run: the wire is a bare object
  (not a one-element list), and the Statistics view renders one open panel with the table's title in
  the heading. This is the no-op claim of D3, made executable.
- **G4 — a multi-table runner titles every table.** A list whose elements are not all titled fails.
  Untitled tables under a stacked presentation are indistinguishable — the presentation and the
  requirement are the same decision.
- **G5 — a two-table run round-trips through BOTH typed models.** Save → load via
  `routers/figures.py` and get both tables back, **and** a two-table run survives `ReproRun` and
  comes back out of the persisted ledger intact. This is the test that would have caught D6's two
  Pydantic fields, and it is the reason to write it before the runner change rather than after.

## §7 Build slices (after review — not part of this spec's approval)

1. **The contract**: D1 normalizers + D6's **two** Pydantic widenings + the `extract/readers.py`
   consumer (including the restated L3 gate and moving `drive.py:140` inside its `try`) +
   G1/G2/G2b/G3/G5. No skill changes; the whole product behaves identically. *This slice should be
   provable as a no-op* — and the reproduction reader is the part of it most worth proving, because
   its failure mode is a silently lowered score rather than an error.
2. **The FE stack**: D2 + the mock fixture. Still no skill changes — driven by the fixture, then by
   a hand-built two-table response.
3. **`lollipop` unsqueezed** (rank 1): attach both, delete the swap, bump `skill.json` version.
   Verify in the browser — set `pairs=` through the real control and see **both** tables
   [[verify-on-real-data-not-mock]].
4. **`boxplot` / `violin`** (rank 2) + dissolve `NATIVE_L3_BOTH` in the same change (D3).
5. **`confusion` / `qq`** (ranks 3–4): the scalar table; κ and λ leave the title string.

Slices 3–5 are independent of each other and each is separately shippable.

## Open questions for the owner

1. **Slice 5 changes what a figure caption says** — `confusion`'s title currently *is* where κ is
   published, and a reader who has seen that figure will look for it there. Move it to a table and
   leave the title a plain description, or keep κ in both? Recommendation: **move it**, and let
   `companions/legends` put it in the caption if it belongs in the caption — one home per fact.
2. **Is a one-row scalar table the right shape for λ and κ** (D4 ranks 3–4), or should Selom grow a
   distinct "headline metrics" strip above the tables? A strip is a bigger, more design-led change
   and Mobbin has a clear precedent for it ([Dub's `Clicks / Leads / Sales`
   tiles](https://mobbin.com/screens/d0f6f9cb-db3a-43e1-ba0c-97950979f096)). Recommendation:
   **one-row table now** (it costs nothing and makes the numbers reachable today), strip later as a
   presentation-only change over the same data.

## What cnsplots contributes here — and what it does not

cnsplots emits **no tables at all**; its `add_pvalue` / statistics overlay paints numbers onto the
**axes**. So it is a source for *what numbers belong beside which figure* — and its
`_validation.py` named-refusal pattern is already the model for `confusion`'s "the label sets
differ, so no κ is defined" — but it is **no guide whatsoever to presentation**. There is no parity
to claim here, and the audit ledger (`docs/cnsplots-port/parity-audit.md`) should not grow a row
implying one.
