# Selom — CURRENT (Live State)

> ## ▶ BOOT: Steven types **`gogogo`** — that IS the whole resume prompt.
>
> **Agent, on `gogogo` (or any greeting with no task): do this, unprompted.**
> He cannot copy text out of the terminal, and he may be sending it from a
> Telegram topic on his phone (the swordfish hermes relay cold-starts this
> session in tmux — no one types `claude` first). So there is no prompt for him
> to paste: **the prompt is this file.** Read, in order, then act:
> 1. this whole file (newest SESSION slot → the live pointers below it)
> 2. `CLAUDE.md` + `agent_handoff/README.md` (the coordination home) and memory
> 3. `git log --oneline -8` and `git status` — trust the repo, not the stamp
>
> Then **state the next action in one sentence, say what you are starting, and
> start it.** Do not ask "shall I?" — the next action IS the standing approval.
> Stop only at a founder gate (spend · irreversible · anything the protocol
> names a founder decision).
>
> _Boot block added 2026-07-13 at the founder's direction, so a relay-cold-started
> session resumes with no chat history (mechanism: the Swordfish hermes relay).
> Keep it at the top when you overwrite this file in place._

> Thin, slot-based pointer — **overwrite in place, never append** (README "CURRENT.md shape" + hard
> rule 1). Per-session NARRATIVE lives in commit messages + `archive/`, not here.

## ▸ SESSIONS  (newest first — scan here; detail = the commit range + git log)

| Tag | Date | SHA range | One-line |
|---|---|---|---|
| **KNOBS-1** | 2026-08-05 | `main` `9a05608..a2dee4a` (**local — not pushed**) | **NEXT#1's first pass: `API_ONLY_KNOBS` 171 → 148, 36 skills → 27, and the "no overlay at all" count 18 → 15.** Worked by what a knob DECIDES. **`volcano` first** — the panel said *"Tune the options"* and offered one text box for a gene-set panel while `fc_threshold` · `fdr_threshold` · `top_n` were API-only. `proteomics_de` took the same three plus its preparation knobs, `missing` above all: the default per-protein mean impute biases real MNAR fold-changes toward zero, so it moves a result further than the choice of test does. **The three over-representation skills share ONE declared pair of cutoffs** (`GENE_LIST_CUTOFFS`) rather than three retyped copies, because the same two keys mean something *different* there than on a volcano — they select the QUERY genes, they do not filter the terms drawn, and they are inert on a bare gene list. `pathway` · `go_graph` · `sankey` had no overlay whatsoever; **`sankey` is the one to remember — `max_links` is its ONLY knob, so that skill rendered a literally EMPTY parameter panel**, and nothing about a blank panel distinguishes "no options" from "options nobody wired". **The one judgement call: `fdr_threshold` is deliberately NOT a slider.** Its range is 0–1 while every value anyone uses (0.05 · 0.01 · 0.001) sits in the first tenth of that track, so a linear slider would make the conventional cutoffs fiddly and 0.001 unreachable at any usable step — a new reachability gap created by the fix for a reachability gap. **Two guards added in the same change, about the layer BELOW coverage — a control that renders but cannot express its knob:** a slider must be bounded by the backend spec (an absent min/max silently becomes HTML's **0–100**), and its default must land ON a step. The second **found a real defect on its first run**: `qq.max_points` (min 200, step 500, default 6000) drew its thumb at **5700** while the readout beside it said 6000. **Three harness capabilities**, each needed here and none a one-off: **`setRange`** (Playwright's `fill()` refuses `input[type=range]` outright, so every threshold knob was undrivable — it walks there by KEYBOARD rather than assigning `.value`, which would only prove React's handler works when called), **`overrideDataCheck`** (the QC block card's "Review & run anyway", a first-class path no check had ever taken; opt-in so an unexpected block still fails loudly), and **`/p/[id]` + `/store` added to route warming** — the warm-routes file already documents this exact class and names three false timeouts it fixed, but the route every check navigates to and the heaviest compile in the app **was never in the list**, and it cost three more 180s timeouts in one session. **Recorded, not worked around:** sankey's own corpus file is `gene,cell_type`, so QC blocks it with *"No numeric data to analyze"* and by its own rule is right — while being wrong about sankey, whose values are the pair COUNTS it derives itself. Gates: `verify.sh` **9/9** (raw, exit 0, **with the corpus set** — the first run had `SELOM_DATASETS_DIR` unset and said so) · **browser-verify 23 green / 2 skipped / 0 failed** across filtered passes, incl. the 2 new. |
| **REACHABILITY-SWEEP** | 2026-08-04 | `main` `18c8cbd..<head>` (**pushed**) | **NEXT#1 closed on all three bullets, and the sweep found a THIRD layer of the same class.** The board asked for three things and each one turned up something bigger than itself. ⚑ **171 of 313 backend knobs render no control at all** — 37 skills, **18 with no presentation overlay whatsoever**. `paramFieldsFromSpec` iterates the OVERLAY, not the backend spec, so a skill without one renders zero controls and the panel says *"Runs with smart defaults — ready to apply"*, which reads as a product decision and is usually just an absent overlay. The sharpest case is **`volcano`, the flagship**: the panel says *"Tune the options"* while `fc_threshold` · `fdr_threshold` · `top_n` — the three knobs deciding what a volcano SHOWS — are API-only. That is now `API_ONLY_KNOBS`, a **named waiver list exact in BOTH directions** (a new knob cannot join it quietly; a knob that gains a control must leave it), the `test_reachability_guard.py` shape. **The progression is the point: 17 unreachable routes → 19 unrunnable skills → 171 untouchable knobs**, each invisible to every gate, each found by asking *can a user reach this* rather than *does it work*. **The seed is GENERATED, not refilled** — the board said "refill `seed.ts`", but refilling a hand-maintained mirror of a live registry only resets the clock, so `scripts/gen-catalog-seed.mjs` writes the Selom half from the backend's own `skill.json` and the drift guard re-runs the generator in memory. It found a live divergence at once: the seed named `umap_scrna` *"UMAP (single-cell)"* while the backend serves *"scRNA UMAP"* — and a test was pinning the seed's string, asserting a name **no user ever saw**. **`runFromWorkbench`** is new harness capability (Store install → real file → intake → **params set through the real controls** → Apply → rendered figure); `lollipop` · `slope` · `ridge` · `line` all reach a real figure on `erg_metrics_long.csv`. **Two defects the browser found in the SERVER LOG, which nobody had been reading:** (1) **5 requests died with a 500 on every cold start** — three repos each called `metadata.create_all` from a lazily-built constructor, and `checkfirst=True` reflects-then-CREATEs non-atomically, so the first concurrent burst against a fresh DB lost with `table analysis_jobs already exists`; hidden because the FE re-fetches and the retry finds the schema built. Fixed via `db.engine.ensure_schema` (lock + a post-condition-checked catch for the cross-process case), regression-tested with **threads on a barrier** because a race is a timing fact a mock cannot express. (2) A Radix **Select mounted uncontrolled and flipped to controlled on every upload** (`data-type-strip` passed `value={undefined}` until `qc.profileCode` landed) — not cosmetic, since Radix keeps its own selection while uncontrolled and silently overwrites an override chosen in that window. **The last board's `catalog.name` footnote was 21 skills, not one**: every one a lossy re-brand of the title it shadowed ("Box / strip plot" → "Selom Box Plot"), dropping exactly the searchable words; `title` is the one display name now and the key is **refused** rather than merely unread. Also: **`venn`/`upset` PASS smoke through a `membership` adapter no user path provides** (unlike `celeris`, which mirrors a real ingest) — recorded in `smoke.py`, not fixed, because a reshape step is a feature. Gates: `verify.sh` **9/9** (raw, exit 0 — BE 1571 fast + 392 slow, FE 704, fe-build green) · **browser-verify 21 green / 2 skipped by precondition / 0 failed**, but **only across two passes** — the shared box OOM-kills the Next dev server mid-suite, so a single 23-check run has not completed; see the LIVE block. |
| **PICKERS** | 2026-08-04 | `main` `5aa9190..<head>` (**pushed**) | **NEXT#1 shipped: a column knob is a picker over the columns that exist, and `pairs=` is a row-list of real level names — and the live browser verify found a bug far bigger than the feature.** ⚑ **`getSkill(id)` read the STATIC SEED alone, so 19 of the 44 live skills were unreachable**: installed from the Store, they rendered in the Workbench as their **raw id, badged "Queued", with Apply DISABLED**. That is `boxplot` · `slope` · `lollipop` · `ridge` · `confusion` · `line` · `regression` · `qq` · `venn` · `forest` — **every plot type built in the preceding sessions** — plus cepo/pathway/ssgsea/pvca/diff_abundance/facs_gating/go_graph/mixing_metrics/pseudotime_genes. `registry.ts` already declared "the backend is the source of truth for what runs now", but only the **Store** honoured it (`useCatalog`); the ~20 other surfaces went through `getSkill`. **Invisible to all 9 gates** — the backend serves them, the param specs merge, the FE overlays exist — and visible in the first real browser [[selom-shipped-not-reachable]]. Fixed via `lib/catalog/live-skills.ts` (a shared cell so `getSkill` stays synchronous at 20 call sites and seed↔registry stays acyclic) + `useLiveSkills()` on the Workbench, whose Apply is gated on the tier `getSkill` returns; ratcheted into `registry-completeness.test.ts` (which already reads the real `skill.json` files) and **proven to bite — reverting `getSkill` fails it with all 19 named**. **The picker itself:** `paramFieldsFromSpec(id, spec, ctx?)` gains ONE optional input — the dataset's own schema, already fetched by `/data/inspect` and already persisted — so it stays the single place dataset knowledge enters and `visibleParamFields`/`isFieldDisabled` stay pure. `column`/`pairs` are **resolved** widgets: emitted only when the vocabulary exists, else byte-identical to the old text field (pinned by a test that a context perturbs *nothing else*). **The pair picker deliberately has NO fallback while the group column is blank** — blank means the backend's auto-detect, a dtype rule the FE cannot evaluate, and on the real ERG table it picks `sample_id` while `best_group` is `condition`, so a guess would offer levels from a column the run is not grouping by. **One backend change was needed and the board's premise was half wrong**: `design.group_candidates` was **empty for `generic_table`** — the exact kind a long-form CSV lands in, i.e. the only kind that uses `pairs=`. `engine/questionnaire._table_hints` fills it **without claiming a design** (`needs_design`/`source` untouched, or every dropped CSV grows an intake confirm-card). Mobbin was unanimous on the row-list (beehiiv · Confluence · ClickUp · Braintrust · AutoSend · Glide) and **ruled OUT** the drag-a-field-into-a-well pattern (Fibery/Sigma/Deputy) and Databricks' per-channel popover — both need a second surface. **Two more defects only the browser could show:** every control's accessible NAME swept in its whole help paragraph (implicit `<label>` wrapping), making two fields mutually ambiguous; and long arm names clip in a narrow select. Gates: `verify.sh` **9/9** (raw, exit 0) · **browser-verify 17/17** (14 + 3 new, real backend + real corpus) · **skill-smoke 43 pass / 0 fail**. |
| **PLOT-ROWS-DONE** | 2026-08-04 | `main` `9dd24ce..26af5a9` (**pushed**) | **§3.2 is CLOSED: `lollipop` · `ridge` · `slope` · `confusion` shipped, and this is the first row in five where the "missing" premise HELD** — no engine existed for any of them, so the grep-first rule cost minutes and correctly said *build*. The content is what each carries beyond its shape. **`lollipop`**: a bootstrap CI on the **median**, because `bar_figure` is mean±SEM *by construction* and a non-parametric interval could not ride a golden-pinned parametric spine; seeded, so it redraws byte-identically. A **pre-aggregated** table (one row per category — how a ranked list actually arrives) is n=1 everywhere, so it gets no interval, no brackets, **and no CI column header**, rather than `n/a` under a "95% CI" heading. **`confusion`**: two labellings of the SAME rows — how an annotation gets validated. Agreement + Cohen's κ **only when the label sets match**; against Leiden ids there is no diagonal, so it NAMES that instead of computing a number from an alignment nobody declared, and that refusal is the real-corpus path. **`slope`**: cnsplots draws this geometry and **computes nothing** — so Selom tests it, and tests it **paired** (`_stats.compare_paired`), because an unpaired Welch compares marginals and throws away the structure the picture is built on; it reports the **up/down split**, the finding a flat mean conceals, and refuses to guess `subject`/`condition` (the wrong guess pairs the wrong rows and still looks right). **`ridge`**: hand-rolled Gaussian KDE + Silverman so the dependency-free **stub draws the same curve as the real engine** (pinned against scipy), and it **discloses its bandwidth** — a curve is exactly as bimodal as its smoothing allows. **⚑ THE SESSION'S REAL YIELD IS THE THREE DEFECTS RENDERING FOUND, all of which passed every assertion**: (1) **the D2 numeric-string class lives in the ANNOTATION layer too** — `type:"category"` fixes the *trace*, but Plotly coerces a numeric-looking string annotation coordinate to a number and a category axis reads it as a **slot index**, so `confusion`'s cell counts scrambled across a correctly-laid-out heatmap and one label drew clean **off the plot**; (2) `lollipop`'s **stem took the next colourway slot**, rendering one mark as two unrelated series; (3) `ridge` went **entirely grey** when the outline was pinned — a `fill:"toself"` scatter derives its **fill from the line colour**. Classes 1 and the `marker.size` area-vs-diameter trap are now **standing invariants in `smoke.check_figure`** (every skill, every run, zero false positives across 43); 2 and 3 are named defect tests. **`scripts/render_skill.py`** turns the loop into one command with `pin_process()` — the render cache twice served the pre-fix figure at 0.00s, which is indistinguishable from the fix not working. Gates: `verify.sh` **9/9** (true exit 0, read raw), **skill-smoke 43 pass / 0 fail** (was 39). |
| **STRIP** | 2026-08-03 | `main` `62e2bcc..1d1176a` (**pushed**) | **§3.2 row 9 `strip` was the FOURTH wrong premise** — Plotly's own box trace draws a strip (`boxpoints="all"` + a hidden box) and `boxplot` already exposed the points knob, so it is a **`style` mode, not a skill**. Mode for a concrete reason: a strip must keep the shared categorical vocabulary (`order` · `add_count` · `pairs` + brackets from `_stats.py`), and a sibling skill would have had to re-import all of it and could then drift from the box it is the companion to. **The bug worth knowing: hiding the box with a transparent LINE COLOUR renders the panel completely empty** — a box trace's points inherit the trace colour, so the markers vanish with it; correct axes, correct `n=` labels, not one point drawn, and every spec assertion still green. Hide it by zero **width** instead. Pinned by a named defect test. Retitled "Box / strip plot" for discoverability (same fix `regression` needed). Golden byte-identical. `verify.sh` **9/9**. |
| **SCATTER-LINE** | 2026-08-03 | `main` `c63275d..88ae4b1` (**pushed**) | **Lane B continued, and the review's premise was wrong twice more.** `scatter` (§3.2 row 5, "the most-requested shape Selom cannot draw") **already existed as `regression`** — x/y/group/label were all there; only the mandatory OLS separated it from a generic scatter. So it became a `fit` flag, not a second skill that would have duplicated the column resolution, grouping, labelling and point cap for one boolean. **The bug found on the way is the real content**: `group` emitted `transforms:[{type:groupby}]`, which **Plotly removed in plotly.js 3 / plotly.py 6** — this repo runs plotly.js 3.6.0 and plotly.py 6.8, and the latter *refuses the key outright* — but skills return raw dicts so nothing validated it. The figure shipped, rendered, and drew **every point one flat colour**: an advertised knob that silently did nothing. That is a CLASS (valid JSON, correct-looking, encodes nothing), so `smoke.check_figure` now fails any trace carrying a removed-from-Plotly key, on every skill every run — the same treatment the numeric-string-axis class got, with a test asserting both directions. `regression` also had **no FE overlay at all** (API-only knobs, the `boxplot` gap again) and is retitled so a user searching "scatter" finds it. `line` (row 6, "the ERG skills each hand-roll one") was **also already built** — `_charts.line_figure` is explicitly "the line analogue of `bar_figure`" and is not ERG-specific; only a CSV front end was missing. It now shares the ERG grid's exact spread vocabulary because it is the same code, takes long-form x/y/series where repeated rows ARE replicates, never auto-detects `series` (the one guess that changes what the figure MEANS), and carries **n per point** — the number that tells a reader whether to believe the band and which is nowhere on the canvas. Gates: `verify.sh` **9/9**, **skill-smoke 39 pass / 0 fail** (was 38). |
| **SLOW-GATE-LANE-B** | 2026-08-03 | `main` `ced7f31..454b974` (**pushed**) | **The slow lane is gated, then Lane B shipped its three plot types.** **STEP 0**: the `slow` lane was enforced NOWHERE — 385 of 1907 tests. The blocker was *assumed*: "slow" reads as "needs the real corpus", which would have made it a real question about what CI can run. Measured in a throwaway venv built with CI's own light closure, corpus-free: **352 pass / 21 skip / 0 fail in 16s** — the 21 skips are the omics-gated tests, and they skip cleanly rather than error. So it needed no new extras, no new job, no nightly, no self-hosted runner: one step in the existing backend job, plus `be-slow` in `verify.sh` (8 gates now, 70s → 95s), because gating only CI would leave the pre-commit gate of record still green on the exact class of breakage it exists to catch. **Proven to bite**: a failing assertion injected into a slow-marked test leaves the fast lane green at exit 0 (1511 passed) while `be-slow` goes red and `verify.sh` exits 1. `!cancelled()` on the CI step so a fast failure cannot hide a slow one. **Lane B**: `venn` · `forest` · `qq`, each closing all seven §5 wiring points. `venn` takes the SAME membership matrix as `upset` and draws circles as **filled traces, not `layout.shapes`** — a shapes-only diagram renders identically and fails `check_figure`'s non-empty-`data` rule, correctly, because it would be a picture rather than an editable figure; above 3 sets it refuses and names `upset`. `forest`'s interval IS the plot, so its provenance is never silent: explicit CI columns → standard error → **t-statistic (`se = effect/t`, the limma identity)**, with the table stating which, and a raise rather than an invented bar when none exist. `qq` carries λ + the Beta(i, n−i+1) null band and catches what a volcano *hides* — an inflated test makes a volcano look better. **λ forced the one real contract decision**: every DE runner wants the adjusted p and `resolve_significance` is tiered to guarantee it, but an adjusted p is a monotone transform whose quantiles are not uniform, so λ would read "conservative" no matter how inflated the test — the raw-first read went into `engine/columns.py` as `pick_raw_significance` beside its twin, not forked in the skill (the drift guard caught that fork and was right). **Rendering found what no assertion did**: `qq` drew `y = x` to `max(observed)`, so on real data (λ=2.14: observed 12.6 vs expected 4.5) the line trailed into an empty half and stretched the x-axis; and the first re-render looked byte-identical because **the C1 cache served the pre-fix figure** — `smoke.pin_process()` exists for exactly that. **Two pre-existing gaps found while wiring**: the golden list was hand-maintained *and duplicated* in `regen_golden.py` (a new skill could ship unpinned, silently) — it lives once now with a completeness test; and that test immediately found **`umap_scrna`, the flagship P0 skill, has never had a golden** (its own `SELOM_UMAP_ENGINE` selector was never pinned by the fixture, so it hit the real scanpy engine and raised). Gates: `verify.sh` **8/8**, **skill-smoke 38 pass / 0 fail** on the real corpus (was 35). |
| **LANE-A-C** | 2026-08-03 | `main` `3565e51..d75de27` (**pushed**) | **STEP 0 cleared, then Lane A and Lane C built solo on main — no worktree lanes, because Lane A turned out to be a shared-module change and Lane C is cross-cutting.** `0b`: the `slow` suite runs again — two lines in `conftest.py` (`string_storage="python"` + `allow_write_nullable_strings`); either alone still fails. **Lane A**: the board said `pairs=` is "nowhere", but `_charts.py` already had `sig_stars`/`compare_groups`/`sig_brackets` — ERG-scoped and *bar*-shaped (it derives the bracket baseline from `means`/`his`/`pt_y`, which a box has not). So it was a **generalization**, not a build: `skills/_stats.py` is now the leaf home for the statistics, the correction, the geometry, `n=` labels and the order contract; `_charts` imports FROM it and re-exports, so the ERG goldens are **byte-identical**. Two things the move made possible: `bracket_shapes` takes a **`span`** (sizing the gap off the data TOP is only right for a zero-anchored bar — a box of values around 100 has a span of ~1 and would have thrown brackets ~12 units off the plot), and **multiple-comparison correction** (bonferroni + BH, hand-rolled so a figure never needs scipy to be honest about its own multiplicity, **pinned against `scipy.stats.false_discovery_control`**). Correction drives the **drawn stars**, not just the table — correcting one and not the other makes the figure lie. **`composition` deliberately takes the ordering half only**: it holds ONE value per category×condition cell, so a pairwise test is n=1 vs n=1 and every bracket would read "ns" regardless of the data. The table contract needed a real decision — box/violin are declared L3 and the guard asserts native∩L3=∅, but a pairwise p exists nowhere in the figure except as a star, so a declared `NATIVE_L3_BOTH` now models "disjoint **runs**, not disjoint skills", with a guard that makes each entry PROVE it. **Reachability**: `boxplot` had **no FE overlay at all** (even `points`/`orientation` were API-only) — all three skills now carry one, mirrored into the `dev:mock` fixture, with tests that the merge YIELDS the controls. **Mobbin ruled the intended affordance OUT**: Rows/Glide/Databricks/Hex all use a repeatable row-list of typed selects with `+ Add`, never a typed mini-DSL — but `ParamField` has no list widget and a param control cannot see the dataset's categories at render time, so `pairs=` stays a text field and the gap is recorded where someone building the picker will look. **Lane C**: **deny-by-default** — `enforce_auth` on the app + a named public allow-list, so a route is private unless written down; a throwaway route is mounted in the guard to PROVE a new one is born private. No-op in `dev` (DevVerifier never raises), so 0 existing tests changed. Then the **actual leak**: `/artifacts/{id}/table` served the exact matrix a skill consumed to whoever held the id. Keys are now `artifacts/{owner}/{id}` — and the content-addressing trap is the subtle part: the id IS the content hash, so two tenants uploading the same table derive the same id and **cross-tenant dedup IS the leak**. Reproduction runs + `uploads/local` scoped too; the latter now **refuses to exist** on S3. **Two bugs the new tests caught while being written**: `_owner_seg("..")` passed through unchanged (dots are legal *inside* an id, so `..` fullmatched), and a blank owner **silently no-opped** because `put`/`get_meta` absorb `ValueError` by design. **⚑ And 7 broken tests read GREEN** — `test_reproduction_runs.py` matches the `test_reproduction` slow prefix, so `-m "not slow"` deselected it. **`verify.sh` AND CI both run only the fast lane, so ~280 slow tests are enforced NOWHERE** (the same blind spot that hid the h5ad breakage). Gates: `verify.sh` **7/7**, **full suite incl. slow 1895 pass / 0 fail**, `skill-smoke` **35 pass / 0 fail**. |
| **PHASE-F1-F2** | 2026-08-03 | `main` `8520466..5157733` (**pushed**) | **The owner's "our plots look worse than cnsplots" is answered with a measurement, and the answer was not the one the charter predicted.** `F1`: five plot types through Selom's own skills on the real corpus, then the **identical arrays** fed to cnsplots 0.6.0 in a throwaway venv, both on one canvas (6×4.5in @ 200dpi — typography only compares in points). Result: 24 named differences with PORT/REJECT/CHECK verdicts (`docs/cnsplots-port/parity-audit.md`). **But three of the five plot types were BROKEN, not merely ugly**, so `F1.5` went first: `enrichment` passed the raw gene count to `marker.size` with `sizemode:"diameter"` → dots **1–3 PIXELS** across and no size key at all (matplotlib's `s` is an *area*, which is why it looked fine on the other side and hid the bug) · `heatmap`'s cluster axis was numeric-looking **strings in lexicographic order**, so Plotly inferred a LINEAR axis and **7 of 17 clusters were unreadable** with cluster 10 sitting between 1 and 11 · and the house font `Inter` was **bundled by nothing**, with the FE and BE stacks falling through to *different* faces (measured by ink width: 517px DejaVu vs 466px Liberation) — so the figure on screen and the figure exported were **different typefaces**. The axis-type bug was a *class*, so the sweep became a standing invariant in `smoke.check_figure` (every skill, real data, every run); it found exactly one more (`cluster`, where the 6-cluster stub renders identically either way and hid it perfectly). Then `F2` ported **10 of the 14 PORT rows** as style tokens — gridless, bold title, black spines/ticks at cnsplots' geometry, flattened title ramp, legend density, and diverging matrices finally putting HIGH at the **red** end (`heatmap`/`corr_heatmap`/`cepo` all had it inverted; verified by sampling rendered pixels). FE defaults moved in step so an editor-made figure matches a skill-made one. `verify.sh` **7/7**, full smoke **35 pass / 0 fail**, **browser-verify 14/14** (F2's D5 acceptance — a real figure restyled and still editable). |
| **SPRINT-3** | 2026-08-02 | `main` `01e3736..<head>` (**pushed**) | **`A1` closed for real, then Parallel Sprint 3 ran 3 lanes and the train.** `A1`: a figure exported from the editor's Export menu to a **real Google Drive and a real Dropbox**, each downloaded back and confirmed a valid 1600×1200 PNG, then deleted — and it found a live defect a mock cannot see: Drive returns the resumable session URI on a 200 **or a 308**, and with `follow_redirects=True` httpx **re-POSTs the 17-byte metadata** to the session URI in a loop, so the figure's bytes never left the box. Fixed + guarded. (The Dropbox non-ASCII fear does **not** fire — `json.dumps` already escapes; now executable.) Lanes: **A** `paper-outputs` (R-01+R-03 — the lit-synthesizer and the **Reproducibility Score** finally have a surface: a 4th `Write-up` stage in the Paper shell) · **B** `jobs` (R-02+R-06 — a run-activity dock; refused a progress bar because `Job.public()` carries no percentage) · **C** `skills` (the **36-skill smoke matrix**). Train run **B → A → C** with `verify.sh` **7/7 on each rebased result**; the expected `test_reachability_guard.py` waiver conflict resolved by hand. Also specced **P-E auth** (and found the plan's "backend is ready" is **half wrong** — 39 of 78 routes take no `AuthContext`, and `GET /artifacts/{id}/table` serves any tenant's matrix bytes to whoever has the id) and **Phase F**, the cnsplots figure-quality port. |
| **CLOUD-EXPORT** | 2026-08-02 | `main` `1c4a6f4..01e3736` (**pushed**) | **Track E built end-to-end: figures can be sent to Google Drive / Dropbox.** Spec first (`docs/cloud-export/spec.md`), then `E-1` real uploads (Drive resumable · Dropbox simple + chunked session above its 150 MB ceiling; both CREATE, never overwrite) · `E-2` `/export/cloud` takes **either** a `dataset_id` **or** a rendered figure · `E-3` "Save to Drive/Dropbox" in the export menu. Key design (D1): `push_path` became the connector primitive and `push_from_store` a shared wrapper — that is what let a figure export without inventing a scratch object in the store. **Three real defects found:** figure export required a DATABASE (`Depends(_uploads_repo)` at the signature, 503 on any box without one) · the export menu carried a hardcoded disabled "Coming soon", the exact client-side pattern the frozen contract forbids and the A20 failure it exists to stop · and Mobbin ruled a pattern OUT — Drive's own folder-picker modal is impossible under `drive.file`, so there is deliberately no picker. **⚑ `E-3` is BUILT, NOT DONE — every test is a mock and no byte has reached a real account.** Also wrote **`docs/build-plan-2026-08/plan.md`**, the master sequencing doc for the autonomous run. Gate 7/7 on every commit. |
| **ERG-MOCK** | 2026-08-02 | `main` `92d6f2e..288e07d` (**pushed**) | Owner-requested mock Fig 1E dataset for laying out the ERG intensity-response figure — `docs/records/erg-module/mock-fig1e/` (+ `n3/`). Simulated b-wave table (all 210 individual points, so mean/SEM is recomputable, not taken on trust) + a trace grid whose **waveform shapes are the real decoded recordings**. Three requested departures from the printed figure: CMV-GFP pulled to a clean null, RK-PDE6B a partial rescue, and the two rescue arms separated only *slightly* (`*`, p 0.02–0.03 at **both** 1.0 and 1.9 log). Plus the rd10 **threshold**: only the WT Control responds below flash 1.0. **The generator self-checks and exits non-zero WITHOUT writing if a retune breaks the biology** — it caught four real defects during the build (null curves running *downward* with intensity from a flat noise term; rescue arms flipping at the noise floor; a too-strict rank check below threshold; a monotonicity tolerance that did not scale with amplitude). Welch t-test is hand-rolled (stdlib has no t-distribution) and **validated against scipy to 1.5e-15**. Side effect worth knowing: pushing swept up **the 6 previously-unpushed EDITOR-ROOM commits**. Answered an owner question with code, not memory: **figures cannot be exported to Drive today** → new **Track E** on the board. |
| **EDITOR-ROOM** | 2026-07-25 | `main` `92d6f2e..f98bdbd` (**pushed**) | **Worked the board top to bottom: `W-1` · `Q-1`/`Q-2` · `V-1` · `W-2` · `V-2` all DONE, browser-verify 14/14 and `verify.sh` 7/7.** **The 1280 width defect is fixed — the plotting area went 90px → 571px**, and every checked width clears §D's 506px target (1280→571, 1440→727, 1920→718), which turned the long-red `D-5 (also-confirm)` gate green. `W-1` first: a figure never reflowed when its CONTAINER resized (only the window), so collapsing a rail bought the plot **zero** pixels and every other remedy was invisible. Then the inspector dock got a collapse control + a tab-icon spine, both rails auto-collapse on a narrow viewport, and zoom/Fit landed in the strip that was an inert hint line. **Three findings the browser produced that no gate could:** `/extract`'s editor **overflowed its band and painted the figure through the Statistics table** while every per-element number read PASS (`EditorWorkspace` needs a flex parent; `CanvasShell` gave it one, `chart-extractor` did not) · the **OAuth cloud-import path was unreachable in the UI** — the menu's loader cancelled its own connections request, so no provider ever showed an import form · and the spec's own 1280 threshold was **wrong**, since at 1440 the plot was 247px, *worse than a collapsed 1280*. **⚑ FOUNDER DECISION OWED: Selom cannot see files the user already has** — Drive is `drive.file`-scoped and Dropbox is an App Folder, so it reads only what it created, and the menu's "copy the share link" hint is impossible to follow. Options + recommendation in `docs/cloud-providers-contract/spec.md` §Scope. |
| **BROWSER-VERIFY** | 2026-07-25 | `main` `ff9705d..b0fc61b` (**pushed**) | **Built the browser-verify harness and answered the §D list in a real browser.** `scripts/browser-verify.sh` boots a real backend + frontend and drives the one path that opens the editor (new project → real EYG_28 CSV → the engine's recommended skill); checks are specs, not scripts. **It found a blocking crash on the primary flow before running a single check** — `datasets.qc` holds two shapes and the mapper cast whichever arrived into the FE's `QcReport`, so **dropping any real file took the whole app to the error overlay**; invisible to every gate because `dev:mock` skips the upload path. **D-5: A24 confirmed FIXED** (`overflow=0`, `card = stageClient − 32` exactly at 1280/1440/1920); keep the `min-h-[20rem]` floor; the `88rem` cap is unreachable. **NEW FINDING: the hero is starved of WIDTH at 1280** — 90px of plotting area, not §D's assumed 506, because fixed columns take 70% of the viewport. D-4/D-1/D-7/D-3/D-9/D-10 all PASS (§D's "Legend overflows" prediction disproven); 2 founder calls. Gate 7/7. |
| **SPRINT-2-MERGED** | 2026-07-25 | `main` `ba0de8c..698381d` | **Phase 0 done → 3 lanes forked, driven and MERGED in one session.** Owner cleared all four founder gates; `main` pushed (`60df628..dddf5d6`) and `campaign/parallel-lanes` deleted. Built the missing groundwork: **`scripts/verify.sh`** (first single gate of record — 7 gates at CI parity incl. the `fe-build` the plan omitted, ~70s) · **`scripts/worktree-setup.sh`** (lane provisioning was **PowerShell-only**, so no lane could have been forked on Linux) · the **frozen `GET /cloud/providers`** contract · **the reachability ratchet**, which found **17 of 61 routes with no FE call site** where the whole milestone review had found 2. Then **launched and drove all three lanes autonomously** (thalon's tmux procedure — the owner no longer drives) and ran the merge train `L1→L3→L2` myself: 16 lane commits, full gate **7/7 green on every rebased result**. Lane 2 found the sprint's worst bug: **`config.py` never read `app/backend/.env`**, so the server pointed at the dead `localhost:3003` while `preflight.sh` validated the live broker **from the same unread file** — a green guard checking a file the server never read. Reachability **17 → 16**. Also wrote the **annotation-layer remediation spec** (the owed plan) and recorded the icon decision + on-hold triage. |
| **REVIEW-MERGE** | 2026-07-25 | `main` `60df628..bee9e66` (**pushed**) | Milestone review of the whole campaign branch (`review-gauntlet` 30 confirmed / 3 blockers + `fe-review` 24 confirmed, 31 of 35 user tasks with no affordance) → fix pass → **owner approved → `main` FF-merged**, gates re-run on merged main. **Both blockers fixed:** WS3.1 had flipped DE significance from adjusted p to RAW p across 5 runners while the axis/table/methods still said "adjusted" (`b73bd9b`, 2835 vs 1008 significant genes on the real EYG_28 export; the guard test had been inverted to bless it) · a gene-label click deleted the user's annotation (`b1a49e8`). HIGH honesty set fixed (`1d2aa81`): FACS cites FlowIO+FlowUtils not the absent FlowKit + states the real compensation outcome · assemble records lineage · GSEA's bare `t` no longer matches `entrezgene_id` · Nango ELv2 recorded. **Annotation layer DEFERRED pending a proper plan** (owner intent, clarified 2026-07-25 — *not* shelved: the flag `NEXT_PUBLIC_ANNOTATION_LAYER` is the holding mechanism while a real plan is written, and ~20 findings are parked with it, owed a plan not a flag flip). **Google Drive + Dropbox cloud connections now LIVE + verified** end-to-end. |
| **LAUNCH-CAMPAIGN** | 2026-07-23 | `60df628..e90203a` — **merged into `main` 2026-07-25** | Owner-directed parallel launch campaign. **Committed:** WS3.1 skill-runner vocab converge (`7440f56`) · Pillar-2 figure-editor **canvas shell** slice-0 (`3db8f0b`) + **annotation/drawing** slice-5 (`d06a28b`) · **ERG** OP+PhNR+flicker-FFT+robust-a/b (`a84636c`) · fe-review drops `frontend-design` (`5ab0103`) · **cloud-storage + self-host Nango** foundation (`8fb2bad`) · **multi-sample scRNA assemble** (`11a115f`) · **FACS `facs_gating` now REAL, IN-PROCESS on pandas-3.0** — clean-room FlowIO+FlowUtils (FlowKit dropped, bokeh/tornado gone from the lock), RISKS #12 **RESOLVED**, `e90203a`. **Nango is LIVE** at `nango.swordfish.cfd` (syd2, swordfish-provisioned) — loading Google/Dropbox integrations blocked ONLY on the env **secret key** (asked swordfish in ASK-BACKS). **ERG Fig-1E n=5 mean±SEM** figure+data staged; delivery is via the Nango cloud channel (owner's choice — not rclone/export). |
| **HOST-PORTABILITY / W-003** | 2026-07-19 | `c512dbc..96d7296` | First session on **Linux host syd4**. Host-portable: review workflows resolve `git` from cwd; `config.py` reads `SELOM_DATASETS_DIR`/`SELOM_PAPERS_DIR`; hygiene-scan 5th class (drive-paths). Closed W-003 (M-007/M-008). Pushed to `origin/main`. |
| **PORT-MERGED** | 2026-07-09 | `24c6797..2cb4cb9` | PR #1 FF-merged to `main`; two `ci.yml` trigger-event fixes. [[verify-ci-in-its-target-event]]. |
| older | — | `git log` / `archive/` | ENG-PORT · CI-GREEN · PARALLEL-SPRINT-1 · RESTRUCTURE 01–08 · AWS materialization · deploy backbone. |

## ▸ LIVE · KNOBS-1 · 2026-08-05 00:29 +1000 (Sydney) · branch `main` (**2 commits LOCAL, not pushed — `f7d5756` + `a2dee4a` on top of `origin/main` = `9a05608`; working tree clean**) · Claude (FE+BE, solo, lead)

- **NEXT#1's first pass is done: 171 → 148 untouchable knobs, 36 → 27 skills, 18 → 15 with no
  overlay.** Ranked by what each knob DECIDES, per the board. Detail in the SESSIONS row; what
  follows is what a next session needs and could not re-derive.
- **⚑ THE FINDING THAT MATTERS: the layer below coverage is a control that RENDERS but cannot
  express its knob.** `mergeField` takes `min`/`max` straight from the backend spec and hands them
  to `<input type="range">`, which **silently falls back to 0–100** when either is absent — so a
  float knob bounded 0–1 would render a slider whose whole meaningful range is the first 1% of the
  track. Same class as the API-only knob (the user cannot reach the value), one layer further in,
  and invisible to every gate because the field object is perfectly well-typed either way. Now two
  guards, and the step one **found a live defect immediately**: `qq.max_points` (min 200, step 500,
  default 6000) put its thumb at **5700** while the readout said 6000. Expect more of this shape —
  the question "can the widget express the value?" has only just started being asked.
- **`fdr_threshold` is a typed number, not a slider, and the reasoning generalizes.** 0–1 range,
  conventional values 0.05 · 0.01 · 0.001 all inside the first tenth. A slider there would have
  created a NEW reachability gap while closing one. **When a knob's useful values cluster at one end
  of its declared range, the slider is the wrong instrument** — that is the rule, not the incident.
- **The over-representation trio share one declared pair of cutoffs and that was not tidiness.**
  `fdr_threshold`/`fc_threshold` on `enrichment`/`pathway`/`go_graph` select the QUERY GENE LIST;
  the identical keys on `volcano`/`proteomics_de` ARE the significance test and are drawn as dashed
  lines. Same names, opposite jobs. Retyping the help three times is how those two get conflated, so
  `GENE_LIST_CUTOFFS` is the one home. Both are also **inert on a bare gene list** (no adjusted-p
  column to filter on) and the help says so, rather than leaving a control that silently does
  nothing on half the inputs.
- **⚑ `sankey` PASSES skill-smoke on a file the real user path GATES — the venn/upset note again,
  a second instance.** Its corpus case is `hani/mmc2_markers_long.csv`, which is `gene,cell_type`:
  two text columns. QC blocks it with *"No numeric data to analyze"* and **by its own rule it is
  right**; it is wrong about *sankey*, whose values are the pair COUNTS the engine derives itself —
  an edge table has no numeric column by construction. smoke passes because it calls the engine
  directly and never meets the ingest gate. The browser check takes the UI's own "Review & run
  anyway", which is the honest user path here. **Not fixed:** whether QC should know a skill derives
  its own numeric column is a real question, and bigger than this change.
- **Three harness capabilities** [[compound-capability-each-task]] — `setRange` (keyboard-driven
  sliders; `fill()` refuses `input[type=range]`, so every threshold knob was undrivable, and
  assigning `.value` would only prove React's handler works when called), `overrideDataCheck` (the
  QC block card's escape hatch, opt-in so an unexpected block still fails loudly), and **`/p/[id]` +
  `/store` in route warming**.
- **⚑ READ THIS BEFORE BELIEVING A BROWSER-VERIFY FAILURE — it is NOT the OOM signature.** Three
  180s timeouts this session, in three different checks (`param-pickers` ×2, `cloud-export`'s Drive
  leg ×1), **each on the FIRST check of its run, each dying at `getByLabel("Project name")` right
  after navigating to `/p/<id>`, and every later check in the same run passing.** That last part is
  what rules out the OOM mode (there, everything after dies in ~200 ms with
  `ERR_CONNECTION_REFUSED`). Cause: `next dev` compiles per route on first request and **`/p/[id]`
  was never in the warm list** — the route every check drives to. Fixed; the first check passes now.
- **A SECOND, still-open harness flake, distinct from the above.** Once, in `openWorkbench` step 1:
  `clickWhenLive(page, install, …)` spent its whole 180s clicking the Store's **Install** toggle
  without `installed.count()` ever going > 0. Installs are account-wide + localStorage-backed, so
  the toggle should already read "Installed" for every spec after the first, and the `count() === 0`
  read appears to race the hydration that flips it. **One occurrence, not reproduced** — recorded
  with the exact location (`fixtures.ts` step 1) rather than fixed blind, because guessing at a fix
  for a race seen once is how a real cause gets papered over. Re-running the spec alone cleared it.
- **`hasParamControls` is a DEAD EXPORT** — no call site anywhere; the workbench's "Runs with smart
  defaults" copy branches on `schema.length`, not on it. Its test used to pin `go_graph` as the
  false case, so giving that skill an overlay failed a test whose subject is the function, not the
  backlog. It names an unknown id now. Left in place (one small pure function, legitimate question),
  but a next session working this backlog should decide whether it earns its keep.
- **Gates.** `verify.sh` **9/9 raw, exit 0** — and note the first run said *"SELOM_DATASETS_DIR is
  unset — real-data tests SKIPPED, so be-test is a weaker gate than CI's."* It was re-run with the
  corpus exported (1571 passed / 5 skipped, vs 1565 / 11). **Export it; the gate tells you when you
  have not.** browser-verify **23 green / 2 skipped / 0 failed** across filtered passes.

## ▸ (superseded) LIVE · REACHABILITY-SWEEP · 2026-08-04 23:35 +1000 (Sydney) · branch `main` (**PUSHED — `origin/main` = `7b9c73c`+, working tree clean, nothing local**) · Claude (FE+BE, solo, lead)

- **NEXT#1 is closed on all three bullets, and the sweep found more than it was sent for.** The four
  newest plot types are driven to a rendered figure by a real user path; the seed is generated
  instead of hand-listed; and the "what else is unusable?" question has a number and a guard.
- **⚑ THE FINDING THAT MATTERS: 171 of 313 backend knobs render NO control at all** — 37 skills,
  18 of them with no overlay whatsoever. `paramFieldsFromSpec` iterates the presentation OVERLAY,
  not the backend spec, so a skill without one shows zero controls and the panel says *"Runs with
  smart defaults — ready to apply"* — which reads as a product decision and is usually just an
  absent overlay. **The sharpest case is `volcano`, the flagship**: the panel says *"Tune the
  options"* while `fc_threshold`, `fdr_threshold` and `top_n` — the three knobs that decide what a
  volcano SHOWS — are unreachable. Now a named, two-directional waiver list (`API_ONLY_KNOBS`) so it
  can only shrink and nothing new joins it silently. **This is the third layer of the same class:**
  17 unreachable routes → 19 unrunnable skills → 171 untouchable knobs. Each was invisible to every
  gate and each was found by asking "can a user actually reach this?" rather than "does it work?"
- **The seed is GENERATED now, not refilled.** The board said "refill `seed.ts` from the live
  registry", and refilling by hand would only reset the clock — a hand-maintained mirror of a live
  registry goes stale again, which is the lesson rather than the incident. `npm run gen:seed` writes
  the Selom half from the backend's own `skill.json`; the drift guard re-runs the generator in memory
  and fails on any difference. **It caught a live divergence immediately:** the seed named
  `umap_scrna` "UMAP (single-cell)" while the backend serves "scRNA UMAP" — and a test was pinning
  the seed's string, i.e. asserting a name no user ever saw.
- **Two defects the browser found that no gate could — again, and this time in the SERVER log rather
  than on screen.** Both were sitting in plain sight in `browser-verify` output that nobody read:
  1. **5 requests died with a 500 on every cold start.** `UploadRepo`/`LibraryRepo`/`SqlJobStore`
     each called `metadata.create_all` from their own lazily-built constructor, and
     `create_all(checkfirst=True)` reflects-then-CREATEs non-atomically — so the first burst of
     concurrent requests against a fresh database raced and lost with `table analysis_jobs already
     exists`. Invisible because the frontend re-fetches and the retry finds the schema built. Fixed
     with `db.engine.ensure_schema` (lock + a post-condition-checked catch for the cross-process
     case); the regression test uses **threads on a barrier**, because the race is a timing fact a
     mock cannot express.
  2. **A Radix Select mounted uncontrolled and flipped to controlled on every single upload.**
     `data-type-strip` passed `value={undefined}` until `qc.profileCode` landed. Not cosmetic: while
     uncontrolled Radix keeps its own selection, so a data-type override chosen in that window is
     silently overwritten when the prop takes over. `""` is Radix's own "no selection".
- **`runFromWorkbench` is the new harness capability** [[compound-capability-each-task]] — Store
  install → real file → intake → **set params through the real controls** → Apply → a rendered
  figure. `openWorkbench` stops before Apply and `openRealFigure` cannot set a parameter, so neither
  could make the claim "this skill ships" in full. Params are set by ACCESSIBLE NAME, so a knob whose
  widget never renders fails the check instead of being silently defaulted.
- **The `catalog.name` note from the last board turned out to be 21 skills, not one.** Every one was
  a lossy re-brand of the title beneath it ("Box / strip plot" → "Selom Box Plot", "Ridge plot
  (joyplot)" → "Selom Ridge Plot"), and the dropped words were the searchable ones. Removed; `title`
  is the one display name, and the key is now REFUSED rather than merely unread — an unread key that
  still parses invites someone to re-add one and wonder why the title does not move.
- **`venn`/`upset` PASS the smoke matrix through an adapter no user path provides.** The `membership`
  crosstab has no equivalent in `engine.ingest` or the frontend, unlike `celeris` which mirrors a real
  ingest. So that PASS proves the engine and says nothing about reachability; `smoke.py`'s docstring
  claimed parity for both adapters and now distinguishes them. Not fixed — a reshape step is a
  feature, not a patch.
- **⚑ ENV, NOT CODE — but read this before trusting a browser-verify number.** `verify.sh` is a
  clean **9/9** (raw, exit 0). The 23-check browser suite is **21 green / 2 skipped / 0 failed**,
  and that is a UNION OF TWO PASSES, not one run: **syd4 OOM-kills the Next dev server partway
  through**, and it did so twice at different points (once at check #4, once at #18). The signature
  is unmistakable and worth recognising instantly — one check dies slowly (a 37 s or 3 min timeout
  while the server is going), then **every remaining check fails in ~200 ms with
  `ERR_CONNECTION_REFUSED`**, and the log shows Next's `[?25h` cursor-restore where the process
  exited. **Those are not 20 failures; they are one.** Re-running the survivors as a smaller filtered
  pass cleared all of them. The box is shared (a thalon dev server holds 1.6 GB, plus
  chrome-devtools-mcp and several agent sessions) and sits on ~2–3 GB of swap; nothing of mine is
  orphaned — `:3152`/`:8152` are released on exit. **So: split the suite when the box is loaded, and
  never read a wall of fast failures as a regression without checking for the server's exit first.**
  The 2 skips are correct and pre-existing: V-2's cloud imports skip unless
  `SELOM_BV_GDRIVE_REF`/`SELOM_BV_DROPBOX_REF` name a file, because both providers are sandboxed to
  what Selom itself created, so there is nothing to discover [[selom-cloud-scope-sandbox]].
- **NEXT#3 also landed (`6bf12a6`) and is VERIFIED IN CI**: zizmor pinned at 1.29.0 in both blocking
  gates, `@latest` moved to a weekly drift job, `hygiene-scan` given the cross-file check so the two
  pins can never drift apart silently. **`main` is pushed and CI is green** — run `30914180768`, all
  six jobs, `workflow-lint` 12s at the pin; the drift job was dispatched by hand (`30914228111`,
  8s green) instead of waiting for Monday, which is what proved its minimal `contents: read` is
  actually sufficient [[verify-ci-in-its-target-event]]. Detail in NEXT#3.
- **Two things I got wrong mid-session, both caught by the guards I was writing.** The
  `API_ONLY_KNOBS` list was first derived with a regex over `params.ts` and was wrong for
  `erg_traces` — the stale-waiver direction of my own guard caught it, which is the argument for
  making it exact in both directions. And a `git checkout` to revert an experiment silently wiped an
  uncommitted test in the same file; **revert an experiment with a targeted edit, never `git
  checkout <path>` on a file that has uncommitted work.**

## ▸ (superseded) LIVE · PICKERS · 2026-08-04 19:17 +1000 (Sydney) · branch `main` · Claude (FE+BE, solo, lead)

- **NEXT#1 is DONE and reachable.** Column pickers on `boxplot` · `slope` · `lollipop` · `ridge` ·
  `confusion` · `line` · `regression` · `qq` · `composition`; the pair row-list on `boxplot`. Both
  surfaces carry it — the Workbench (run a skill) and Figure-data (re-run with different columns),
  so changing a column on an existing figure is the same gesture as choosing it the first time.
- **⚑ THE FINDING THAT MATTERS MOST IS NOT THE FEATURE: 19 of 44 live skills could not be run at
  all.** Detail in the SESSIONS row. Three things to carry:
  1. **A green `verify.sh` says nothing about reachability.** All 9 gates passed while ten shipped
     plot types sat behind a disabled button. Only driving the real Workbench in a real browser
     showed it.
  2. **The previous board predicted this and it was not acted on.** STRIP's LIVE block says
     *"reachability was verified against a live backend… **I did not click through the Store in a
     browser** — the contract half is proven, the visual half is not."* The visual half was broken.
     **When a wrap says a half is unproven, that IS the next action, not a footnote.**
  3. **The seed is still hand-maintained.** `getSkill` now prefers the live registry so the drift
     cannot hide, but `lib/catalog/seed.ts` still lists only 25 Selom skills. The guard makes that
     safe, not correct — a backend-down session shows the seed, and it is 19 skills stale.
- **The premise pattern is 5-for-6 now, and this time it was MY board note that was half wrong.**
  NEXT#1 said the pair vocabulary was already client-side because `design.group_candidates[].levels`
  is persisted. True in general, **false for `generic_table`** — where it was empty, which is the
  only kind that uses `pairs=`. **Grepping the FE was not enough; the payload had to be run.** One
  `uv run python` against the real file settled in seconds what the note had asserted.
- **Three defects came out of writing the tests and driving the browser, not from design:** a column
  whose every value is distinct passes the cardinality cap but groups nothing; `sample_id` sat
  *exactly* on the 12-level cap so it needed the deg alias rule, not the cap; and every param
  control's accessible NAME included its whole help paragraph, which made "Group column" and
  "Compare groups" mutually ambiguous to `getByLabel` — and to a screen reader.
- **`openWorkbench` is new harness capability, not a one-off** [[compound-capability-each-task]] —
  it drives Store-install → project → real file → intake → skill SELECTED, stopping one step short
  of `openRealFigure` because a param panel only renders while a skill is selected and un-applied.
  Any future check about *inputs* (rather than the figure) starts here.
- **`dev:mock` cannot show the pair picker, and that is correct.** The mock is header-only, so it has
  no row values to derive levels from; it returns no group candidates rather than inventing any
  [[mock-fallback-never-fabricates-data]]. The COLUMN picker does work there (real header). Recorded
  in `mocks/data-inspect-fixture.ts` so it is not debugged as a regression.
- **Small finding, not fixed (out of scope):** `catalog.name` in `skill.json` overrides `title`, so
  the STRIP session's retitle to *"Box / strip plot"* never reached the Store or the Workbench —
  both display **"Selom Box Plot"**. Discoverability survives only because the summary contains
  "strip plot" and the search covers it.

## ▸ (superseded) LIVE · PLOT-ROWS-DONE · 2026-08-04 16:27 +1000 (Sydney) · branch `main` · Claude (FE+BE, solo, lead)

- **§3.2 is fully closed.** Rows 7/8/10/11 (`confusion` · `ridge` · `slope` · `lollipop`) are built,
  wired through all seven §5 points, reachable, and green. `docs/cnsplots-port/source-review.md`
  §3.2 now has only rows **12 (`hist`/`kde`/`dist` as one skill)** and **13 (`donut`/`pie`, low
  scientific value)** left, both explicitly ranked last.
- **The premise pattern has ENDED — and knowing that is itself the result.** It was wrong four times
  running (`pairs=`, `scatter`, `line`, `strip`: capability existed, reachability didn't). This time
  the grep took minutes and said *build*: nothing in `_charts.py` does a stem, a paired line, a
  contingency table or a 1-D KDE. **Keep grepping first — the rule is cheap and it now has a
  negative result to calibrate against, not just four positives.**
- **⚑ THE FINDING THAT SHOULD CHANGE THE NEXT BUILD: three of this session's defects were invisible
  to every gate and visible in the first render.** Not a new lesson in kind, but the *sharpest*
  instance yet, because two were in code that had just been written to fix a rendering problem —
  the grey-ridge bug was CAUSED by a fix for the stacking order. **Render after every visual change,
  including the ones that are themselves visual fixes.** `scripts/render_skill.py <skill>` is now
  one command and turns the caches off.
- **The annotation-layer D2 finding generalizes beyond these four skills.** Any skill that labels
  cells or points on a category axis by NAME is exposed, and cluster ids reach a figure as numeric
  strings on every scRNA path. `check_figure` now fails it everywhere, but **existing skills were
  only proven clean by the 43-skill smoke run** — if a new labelled-matrix skill appears, this is
  the first thing to check.
- **The render cache cost two debugging rounds.** It served the pre-fix `confusion` twice at 0.00 s
  while I inspected `theme.py` for a rewrite that never happened. `smoke.pin_process()` is the fix
  and it is now baked into `render_skill.py`; the documentary form (a board note from the `qq`
  session) did **not** hold, which is why it became a script.
- **One contract limit found, not fixed:** `contract.run_skill_with_table` returns `StatsTable |
  None` — exactly ONE table. So `lollipop` with `pairs=` swaps its ranked-values table for the
  pairwise p-values (the same trade `boxplot` makes) rather than showing both. Recorded below.
- **⚑ CORRECTION, same session (2026-08-04): I recorded the live-schema column picker as "ruled
  out / impossible" and that was WRONG — it is the premise pattern again, this time in my own note.**
  Databricks · Confluence · Better Stack · Glide · GitHub Insights all populate column pickers from
  the dataset's live schema, and I wrote that `ParamField` cannot see the dataset's columns. It
  can — or rather, the data is already there and nobody threads it:
  - `POST /data/inspect` **already** returns `data_fit.columns` (every column + `n_numeric_cols`)
    and `design.group_candidates[]`, **each carrying its `levels`, `n_levels` and a
    `reference_guess`**. Both are **persisted on the dataset** in the FE store
    (`lib/projects/types.ts` → `dataFit` / `design`) and survive reload.
  - **`components/project/workbench-panel.tsx` already holds `route.dataFit` in its props (line ~49)
    and calls `useSkillParams` at line ~103.** The columns are in scope in the very component that
    renders the controls.
  - The ONLY real blockers are (a) `paramFieldsFromSpec(id, spec)` is pure over the backend spec, so
    nothing threads a data context into the merge, and (b) `ParamField` has no repeatable-list
    widget (needed for `pairs=`, not for a single-column select).
  **So `pairs=` is not blocked on data either** — pairs are between LEVELS, and levels are exactly
  what `group_candidates[].levels` carries. The stale "impossible" claim has been corrected in
  `lib/catalog/params.ts` at both notes; do not re-derive it from an older comment.
  What still transfers from Mobbin regardless: GitHub Insights' explicit "(optional)" convention
  **inverted** — `slope` marks its REQUIRED columns, because a text field that silently fails at run
  time is the worst of both. That marking stays useful after the picker ships.

## ▸ (superseded) LIVE · STRIP · 2026-08-03 · branch `main` (**PUSHED — `origin/main` = `1d1176a`, nothing local**) · Claude (FE+BE, solo, lead)

- **NEXT#0 and NEXT#1 are DONE, and Lane B continued into rows 5-6.** The slow lane is gated in
  CI *and* `verify.sh`; `venn`/`forest`/`qq`/`line` are built, wired and reachable, and `scatter`
  turned out to be `regression` with a dead knob. Detail in the two newest SESSIONS rows.
- **⚑ THE PATTERN THAT SHOULD CHANGE HOW THE NEXT ROWS ARE APPROACHED: the plot review's "missing"
  premise has been wrong three times running** — `pairs=`, `scatter`, `line`. In every case the
  ENGINE existed and only the REACHABILITY was missing. Grep for the engine before writing one;
  budget the work as wiring, not building.
- **The slow gate is verified in its target event** [[verify-ci-in-its-target-event]] — run
  `30834926456` on `c8ddbbb`, backend step 7 *"Slow test gate"* → **361 passed, 21 skipped in
  8.65s** (faster than the local 16s: CI runs `-n auto` on its own runner). Not inferred; read off
  the run.
- **⚑ `ci` was ALREADY RED on `main` before this session's work** — the two preceding doc-only
  commits (`ced7f31`, `8de5e39`) both failed, so the last board's "CI green" assumption was stale.
  Cause: **zizmor `ref-version-mismatch`** on all five `actions/checkout` uses. The SHA pins were
  correct — the SHA is an annotated-tag object dereferencing to the commit tagged **v5.0.1** while
  the comment said `# v5`. Fixed in `c8ddbbb`; `ci` is green now.
- **⚑ AND HOW IT HID — now CLOSED in the gate, not in a note.** `zizmor` starts OFFLINE unless it
  finds a token, and that audit needs the API to resolve tags → SHAs, so a local run said *"No
  findings. Good job!"* while CI (which sets `GH_TOKEN`) reported five. **No new credential was ever
  involved** — `gh` was authenticated throughout; zizmor just does not look. `verify.sh` now carries
  a **`wf-lint`** gate that resolves `GH_TOKEN` (falling back to `gh auth token`, exported not
  passed as argv) and reports **NOT RUN with the fix** when it can't, never a pass. Proven both
  ways, and reverting one `# v5.0.1` → `# v5` turns it FAIL (exit 13) — CI's exact failure,
  reproduced locally. **9 gates now.**
- **⚑ OWNER CALL OWED (small, no spend): the `workflow-lint` job runs `zizmor@latest`,** so a new
  audit in a new zizmor release turns `main` red with **no repo change** — which is exactly what
  happened here. Pinning it makes the gate reproducible but stops new audits arriving for free.
  Both are defensible; it is a policy choice, so it is not being made unilaterally.
- **Reachability was verified against a live backend, not inferred**: `GET /skills` serves all three
  as `verified`/`production` and `GET /skills/{id}` serves their `param_spec`, which is what the
  panel merges with the FE overlay. **I did not click through the Store in a browser** — the
  contract half is proven, the visual half is not.
- **The lesson worth carrying: a "cheap gate we can't afford" was never measured.** The slow lane
  was written off as corpus-dependent for long enough to hide a real breakage; it was 16 seconds.
  Measure the blocker before designing around it.

## ▸ (superseded) LIVE · LANE-A-C · 2026-08-03 21:55 +1000 (Sydney)

- **STEP 0 is cleared.** `0a`: the owner asked mid-session, so `main` was pushed —
  `46d5c6c..f608feb`, all 31 commits. Phase F, the ERG corrections and cloud-export are on
  `origin` now; that loss-risk is closed. `0b`: the `slow` suite runs (detail in the SESSIONS row).
- **The board's three-lane fork was NOT used, deliberately.** Lane A turned out to be a change to a
  shared module (`_charts.py` → `_stats.py`) and Lane C touches every router — both are the class
  of work that is *worse* in a worktree, and B depends on A's validators. Built sequentially on the
  main checkout instead. **Lane B (venn/forest/qq) is untouched and is the obvious next slice.**
- **Lane A is done, and its premise was wrong in a useful way.** `pairs=` was not "nowhere" — it
  existed, ERG-scoped and bar-shaped. The work was generalization, so the ERG figures are
  byte-identical and every categorical skill now speaks one vocabulary. Correction is default-`none`
  everywhere, so no existing figure moved.
- **Lane C steps 1–3 are done.** Deny-by-default + tenant-scoped artifacts / reproduction runs /
  `uploads/local`. **Authentication and authorization were closed separately and in that order** —
  step 1 alone would have reduced the artifact leak from "anyone on the internet" to "any logged-in
  user", which is a reduction, not a fix. Steps 4–7 (the frontend half) are **blocked on Clerk keys**
  and stay batched to the owner.
- **⚑ THE FINDING THAT OUTLIVES THIS SESSION: the `slow` test lane is enforced NOWHERE.**
  `.github/workflows/ci.yml` runs `pytest -m "not slow"` and `verify.sh` does the same, so **385 of
  the 1907 tests have no gate at all.** It is how the pandas-3/pyarrow h5ad breakage survived, and
  this session it let **7 tests broken by a signature change report PASS**.
  **Run `uv run pytest` with no `-m` before trusting a green gate on any signature change.**
- **The fix is small, and my first read of it was WRONG — measured 2026-08-03, trust the number.**
  I assumed "slow" meant "needs the real corpus", which would have made this a real decision about
  what CI can run. It does not. `env -u SELOM_DATASETS_DIR uv run pytest -m slow -n 2` gives
  **373 passed, 12 skipped, 0 failed in 16s** — the same 12 skips as with the corpus. The lane is
  mostly *heavy-import* tests (scanpy, pydeseq2), not *real-data* tests.
  **So: add a corpus-free `pytest -m slow` step to the EXISTING backend CI job** (which already has
  a 20-minute budget) — not a new job, not a nightly, not a self-hosted runner. It would have caught
  this session's 7 breakages exactly, since `test_reproduction_runs.py` needs no corpus.
  Be honest that it is a WEAKER gate: with the corpus that same lane takes ~7½ min because the real
  engines chew on real matrices, so this catches breakage, not numerical regression —
  `scripts/skill-smoke.sh` + a local full run stay the deeper check. CI triggers on `push: [main]`
  and `pull_request`, so it self-verifies on the next push [[verify-ci-in-its-target-event]].

## ▸ NEXT

0. ~~Gate the `slow` lane~~ · ~~Lane B~~ · ~~§3.2 rows 5/6/9~~ · ~~rows 7/8/10/11~~ ·
   ~~the column / pair picker~~ · ~~sweep the reachability class~~ · ~~pin zizmor + the drift job~~
   — **all DONE, and #3 is verified in its target event** (CI `30914180768` green, drift
   `30914228111` green). §3.2 is closed except rows 12–13. **Nothing is carried forward.**
1. **⇒ KEEP WORKING DOWN `API_ONLY_KNOBS` — first pass done 2026-08-05 (`f7d5756`): 171 → 148,
   36 skills → 27, 18 → 15 with no overlay.** `lib/catalog/registry-completeness.test.ts` holds the
   list, exact in both directions. ~~`volcano`~~ · ~~`enrichment`/`pathway`/`go_graph`~~ ·
   ~~`proteomics_de`~~ · ~~the cheap ones~~ **all DONE.** What is left, still ranked by what the
   knob DECIDES:
   - **`deg` is now the largest single gap by far (16 knobs)** and the most consequential —
     `method`, `mode`, `group_col`/`group_val`, `covariate_col` change the RESULT, not the drawing.
     It wants a spec, not a drive-by overlay. (`reference`/`treatment` are `diff_abundance`'s, also
     API-only, and are NEXT#2's level-widget shape rather than a text box.)
   - **The 15 skills with no overlay at all** are where the remaining bulk sits: `cepo` ·
     `corr_heatmap` · `diff_abundance` · `facs_gating` · `gsea` · `markers` · `mixing_metrics` ·
     `normalization_qc` · `pca` · `pseudotime_genes` · `pvca` · `ssgsea` · `string_network` ·
     `trajectory` · `upset`. Several are one obvious knob (`upset.sort_by`, `pca.scale`,
     `corr_heatmap.method`) — same shape as the cheap ones just closed.
   - **Do NOT just add overlays to hit zero.** Some knobs are genuinely internal (`erg_*`'s
     `ab_detector`, `manual_marks`). Waiving those *with a reason* is the right answer; the list is
     a backlog, not a defect count.
   - **The new sibling guards are the thing to extend, not restate**: a slider must be BOUNDED by
     the backend spec and its default must land ON a step. Both live in the same describe block. If
     a knob has no min/max in `skill.json`, render it as a `number` — do not give it a slider and
     inherit HTML's silent 0–100.
2. **⇒ EXTEND THE PICKER WHERE IT STILL DOESN'T REACH** (small, additive, all fail-soft today):
   - **A multi-column widget** — `venn.sets` (2–3 column names) and `heatmap.annotations` are
     comma-separated LISTS of columns, so the single-select `column` type does not fit. The row-list
     built for `pairs` is most of the answer.
   - **A level widget for the ones that take a level, not a column** — `slope.levels` ("which two,
     in order"), `deg.reference`/`treatment`. `group_candidates[].levels` already carries these, and
     `resolvePairsField` is the pattern; `slope.levels` is an ORDERED two-of-N, so it is its own
     shape, not a pair.
   - **`violin` stays text on purpose** — its clusters do not exist before the run. If that ever
     changes, the honest source is a completed `cluster` run's own output, not `design`.
3. ~~**PIN ZIZMOR + ADD THE WEEKLY DRIFT JOB**~~ — **BUILT 2026-08-04** (`6bf12a6`). Both blocking
   gates pin **1.29.0** (confirmed off this session's own gate output, not taken from the board);
   `.github/workflows/zizmor-drift.yml` runs `@latest` Mondays 02:00 UTC, `contents: read` only, and
   is **not** in `ci`'s `needs:`, so it can never gate a merge. **One judgement call worth knowing:
   the drift job DOES fail its own scheduled run on a finding.** "Non-blocking" is easy to implement
   as "always exit 0", which is a report nobody reads and violates the repo's own rule that a guard
   is a ratchet only when enforcement rides on the exit code. So the failure is a NOTIFICATION, never
   a gate. Say so if that reading is wrong.
   - **hygiene-scan gained the cross-file half**: the two pins must be explicit AND equal, matched on
     the invocation (`uv tool run zizmor@…`) so prose neither trips nor satisfies it, plus an
     intra-file check that catches verify.sh's `--help` echo drifting from the gated command. All
     three fail by name at exit 1 (proven).
   - **The original reproduction still holds under the pin**: reverting one `# v5.0.1` → `# v5` fails
     zizmor 1.29.0 with `ref-version-mismatch` at **exit 13**. `verify.sh` 9/9.
   - **✔ VERIFIED IN ITS TARGET EVENT** [[verify-ci-in-its-target-event]] — not inferred, read off
     the runs. Push `5aa9190..7b9c73c` → **run `30914180768` green on all six jobs**, `workflow-lint`
     passing in **12s at the pin**. And `zizmor-drift` was **dispatched by hand** (run
     `30914228111`, green in 8s) rather than waiting for Monday — which is the half a local check
     could not answer, because **zizmor catches too-many permissions and never too-few**: its
     `contents: read` is now *proven* sufficient to check out, install uv and run zizmor online.
4. **⇒ SPEC THE MULTI-TABLE `StatsTable` CONTRACT — owner-directed 2026-08-04, spec FIRST.**
   Write `docs/stats-tables/spec.md` and **pause for review before code** (playbook: consequential
   contract change → forcing-questions → spec). Owner note: **"continue learning from cnsplots and
   Mobbin to refine the spec as well"** — both are inputs, not afterthoughts.
   - **The problem:** `contract.run_skill_with_table` → `StatsTable | None` and
     `lib/skills/api.ts` `table?: StatsTable | null`. Exactly ONE table, so `lollipop` with
     `pairs=` must SWAP its ranked values for the pairwise p-values (the trade `boxplot` already
     makes). `slope` and `confusion` have the same latent squeeze.
   - **Decisions the spec owes:** D1 wire shape (`StatsTable | StatsTable[] | null` is
     backward-compatible and the obvious candidate — say why, or why not) · D2 **how the FE renders
     N tables — stacked vs tabbed vs accordion. This is the Mobbin question**, and the standing rule
     applies: look at how mature tools present several result tables under one figure before
     choosing · D3 migration for the ~18 skills in `NATIVE` (must be a no-op for every one that
     attaches a single table) · D4 which skills actually want 2+, and whether a table needs an
     explicit `role`/`kind` so the FE can order them predictably.
   - **cnsplots input:** it emits **no tables at all** — its `add_pvalue`/statistics overlay paints
     numbers onto the AXES. So it is a source for *what numbers belong beside which figure* (and
     `_validation.py`'s named-refusal pattern), NOT for the presentation. Say that in the spec
     rather than implying parity where there is none.
   - **Ratchet to extend, not restate:** `tests/test_skill_table_contract.py` already partitions
     every skill into native ∪ L3 ∪ L4-only and proves `NATIVE` against source. Whatever shape D1
     picks, that guard must still ground the classification in code.
5. **The audit's open rows 21–23** — long category labels colliding with the axis title, point-label
   collision on scatter/volcano (neither side applies `adjustText`), axis title vs long ticks under
   `automargin`. **Selom's own defects, which cnsplots does not solve either**, so this is where
   Selom can beat the reference rather than match it. Row 21 is now *visible on shipped output*:
   `slope`'s grouped x-axis rotates six long treatment-arm names, and `lollipop` defaults to
   horizontal partly to dodge it.
   **Verify with `scripts/render_skill.py slope lollipop confusion` — the collision is a render
   fact, not a spec fact, and there is no assertion that can see it.**
6. **§3.2 rows 12–13, if wanted**: `hist`/`kde`/`dist` as ONE skill with a mode (the review's own
   framing) — and `ridge` already ships the KDE + Silverman bandwidth to build it on, so this is a
   genuine reachability job now, not a build. Row 13 (`donut`/`pie`) the review itself rates low
   scientific value — build last or not at all.
7. **The isolation-coverage guard** — spec §5's strongest form, and the one piece of Lane C not
   built. Enumerate private routes by AST, subtract the allow-list, and **fail on any private route
   with no isolation case**, carrying a NAMED shrinking backlog (the `test_reachability_guard.py`
   waiver shape). Turns "39 unaudited routes" into a tracked list instead of a memory.
8. **F3 (the fit-scored SKILL picker)** — a different picker from the column one: that chooses a
   *column*, this one chooses a *skill*. Specced in source-review §6; Mobbin ruled OUT abstract
   illustration tiles. Run `fe-review` at the end. **F4** = the rest of the plot gaps.
   **Note it now has ~47 skills to sort**, and the four added today are all general-purpose chart
   types with no omics gate — exactly the case §6 says the flat Store list stops serving.
9. **`OH-01`** (arq + Redis job store) — unblocked; contract is `docs/jobs-surface/spec.md` §4.

**Owed follow-ups still open:** ~~the one-table `StatsTable` limit~~ **decided 2026-08-04 → NEXT#4
(spec first, cnsplots + Mobbin as inputs)** · ~~the `zizmor@latest` pin policy~~ **decided
2026-08-04 → [[DECISIONS #14]], built at NEXT#3** · ~~the `pairs=` **pair-picker**~~ **BUILT 2026-08-04.** Note the correction to the correction:
the levels were persisted for scRNA/bulk but **not for `generic_table`**, the only kind that uses
`pairs=` — that needed a backend change (`_table_hints`) · there
is **no run-scoped legends route** (`/papers/{slug}/legends` is published-paper scoped;
`compose_ledger_legends(ledger)` already does the work) · **`mocks/handlers.ts` has no handlers for
the six newer routes** (harmless — MSW bypasses) · the audit's CHECK rows 13/24 need **each
journal's own author guidelines**, not cnsplots.

## ▸ DEFERRED

### ⚑ Batched for the owner — NEXT WEEK (owner-directed 2026-08-02: "anything that needs me")

- **Clerk keys** (publishable + secret + issuer URL) — the only thing blocking P-E's frontend half.
- **The route split** — does the app move to `/app` so `/` can be public? Recommended in
  `docs/auth-multitenancy/spec.md` D5; **owed to Thalon's landing-page build** and much cheaper
  before that ships.
- **A real `.fcs` file** staged into `SELOM_DATASETS_DIR` — the ONLY reason `facs_gating` is the one
  skill the smoke matrix cannot run. The engine is real; the corpus is the gap.
- ~~Push `main`~~ **DONE 2026-08-03.** The 31-commit backlog *and* this session's Lane A + Lane C
  went to `origin` at the owner's direct request; `origin/main` = `d75de27`, working tree clean,
  nothing local. The long-standing unpushed-backlog risk is closed.
- ~~The CI slow-lane *decision*~~ — **BUILT 2026-08-03** (`6c2e334`), in CI and in `verify.sh`.
  Re-measured against CI's own light closure, not just the local full env: 352 pass / 21 skip /
  0 fail in 16s.
- **Phase F, one product call:** should Selom ever add a *static-render* skill class for plots that
  are better as publication images, at the cost of editability? Recommendation is **no**
  (`docs/cnsplots-port/plan.md` §2). Nothing depends on the answer.
- **Phase F, a second product call (audit row 17):** should a figure export on a **transparent**
  background (cnsplots' default — it composites cleanly into a multi-panel) or stay white (safer for
  someone who just downloads it)? Best answer is probably *offer both at export*; nothing is blocked
  on it. Row 2 (title centred vs left) is the same shape — a per-journal-pack decision, not a global
  one, and it lands with the journal packs.
- **Selom cannot see files the user already has** — the `drive.file` / App-Folder scope decision
  (`docs/cloud-providers-contract/spec.md` §Scope), still open from EDITOR-ROOM.

### Standing

- **OneDrive/Microsoft** cloud provider (owner on hold until a machine that logs into Azure cleanly).
- **Public Selom backend on syd2** (swordfish scoping note, FROM-SWORDFISH top): needs a backend **Dockerfile + GHCR image-CI** (mine) + 5 data-plane answers (DB/object-store/datasets-mount/heavy-jobs/auth). Owner-gated on any syd2 resize (spend). Reply in ASK-BACKS.
- WS6 AWS deploy — owner chose **"this box first, AWS later"**. Owed WS1/restructure reviews fold into the campaign milestone review.

## ▸ ENV / landmines (Linux · syd4)

- **selom-data IS here** at `/home/deploy/migration/selom-migration-staging/selom-data/` → `SELOM_DATASETS_DIR`. **Docker installed** — in a fresh shell use `sudo docker` until the `deploy` docker-group login refreshes.
- **Gate of record = `scripts/verify.sh`** (**9 gates**, ~100–160s, raw + exit-code gated). **It cannot see reachability** — all 9 were green while 19 skills sat behind a disabled Apply. For anything user-facing, `browser-verify` is the second half of the gate, not an optional extra. Do NOT hand-assemble gates and do NOT pipe it through `| tail` — a pipe returns tail's status and discards the failure [[read-gate-output-raw-not-piped]]. Servers: backend `uv run uvicorn main:app --reload`; frontend `npm install --legacy-peer-deps` **in the MAIN checkout only**. Derive the FE dev-lane port (Selom FE=3152) to avoid the shared-box `:3000` collision; `:8000` is eamos — never bind it.
- **Look at a plot = `uv run python scripts/render_skill.py <skill> [<skill>…]`** (in `app/backend`,
  needs `SELOM_DATASETS_DIR` + `SELOM_SKILLS_ENGINE=real SELOM_UMAP_ENGINE=scanpy`). Renders each
  skill's declared real-corpus smoke case to PNG with **`pin_process()`: engines pinned real, C1 +
  render caches OFF**. Use it after ANY visual change — including a change that is itself a visual
  fix, which is how the grey-ridge defect got in. A stale cache hit is 0.00 s and looks exactly
  like the fix not working.
- **Browser checks = `scripts/browser-verify.sh`** (needs `SELOM_DATASETS_DIR`; **23 checks**, 2 of
  which skip unless `SELOM_BV_GDRIVE_REF`/`SELOM_BV_DROPBOX_REF` name a file). **On a loaded box,
  run it as two filtered passes** — `scripts/browser-verify.sh <spec-filter> …` takes several — because
  the Next dev server gets OOM-killed partway through and every later check then fails in ~200 ms
  with `ERR_CONNECTION_REFUSED`. That wall of fast failures is ONE failure (the server), not many;
  look for Next's `[?25h` exit marker in the log before believing a regression.
  **A slider is driven by KEYBOARD** (`setRange` — `fill()` refuses `input[type=range]`), and a
  QC-blocked input needs `overrideDataCheck: true` to take the block card's "Review & run anyway".
  **Three** entry fixtures: `openRealFigure` drives to a rendered figure in the EDITOR;
  **`openWorkbench` stops one step short** — Store-install → project → real file → intake → skill
  SELECTED — the only state in which a skill's param panel renders; and **`runFromWorkbench` goes all
  the way** — the same drive plus params SET THROUGH THE REAL CONTROLS (by accessible name, so an
  API-only knob fails the check) plus Apply plus a rendered figure. That last one is the instrument
  for "is this skill reachable", as distinct from `skill-smoke`'s "does this engine work".
  Adding a check is a new `.spec.ts`.
  It owns its servers
  (BE `:8152` + FE `:3152`) and stops them on exit, and **resets its own SQLite store each run** —
  without that, reconcile drags every prior figure spec in and the drive blows the 180s timeout.
  **Serve the dev app on `localhost`, NEVER `127.0.0.1`:** Next 16 blocks its own dev resources
  cross-origin and trusts only `localhost`, so on `127.0.0.1` the page renders and every control
  looks clickable but **React never hydrates** — no handler fires, no error, nothing works.
- Every commit runs `.githooks/pre-commit` (hygiene-scan, 5 classes). `git user.email` MUST stay the noreply (`282747725+steveneam@…`) or Vercel blocks deploys [[selom-git-commit-email-vercel]].
- **Cloud OAuth creds** staged in `app/backend/.env` (gitignored): `GOOGLE_*` ✓ · `DROPBOX_*` ✓ · `MS_*` empty (on hold). The syd4 **Nango dev copy** (`deploy/nango/`) is **STOPPED** as of 2026-07-25 — containers + volumes intact, restart with `sudo docker compose -f deploy/nango/docker-compose.yaml start`. A dead `localhost:3003` is EXPECTED; the live broker is swordfish's on **syd2** (`nango.swordfish.cfd`) and is unaffected. Verify any time with `bash deploy/nango/preflight.sh`.
- **Worktree lanes share deps by SYMLINK** (`scripts/worktree-setup.sh`): never `npm install` in a lane (it writes through the link and clobbers the main tree — `guard-worktree-install.mjs` refuses it), and a lane needing a new BE dep **re-plans** rather than syncing, because `uv run` auto-syncs the SHARED `.venv`. Turbopack cannot run in a lane at all, so `next build`/`next dev` and browser checks belong on the main checkout.
- **The agent cannot marshal binary/large files through chat** (base64 reproduction corrupts, even ~20 KB) — deliver files via a real channel (scp/SFTP/rclone/the cloud integration), never by pasting base64 into a tool call. Emailing via the Gmail MCP is draft-only + attachment-limited; Drive `create_file` needs valid inline base64 (same wall).

## ▸ READ FIRST

**`docs/auth-multitenancy/spec.md`** (**the entry point — steps 1–3 of §4 are DONE; steps 4–7 are the
frontend half and are blocked on Clerk keys. §5's route-enumerating isolation guard is the one piece
NOT built — see NEXT#7**) · **`docs/cnsplots-port/parity-audit.md`** (F1+F2 ledger; its §3 table is
the remaining styling work, rows 21–23 are NEXT#5) · `docs/cnsplots-port/source-review.md` §3.2 +
§5 (**Lane B's three plot types and the seven-point wiring checklist they must close**) ·
`docs/cnsplots-port/{plan,spec}.md` · **`docs/skill-coverage/matrix.md`** (35/36, re-run with
`scripts/skill-smoke.sh`) · **`docs/reproduction-engine/skill-table-contract.md`** (now documents the
one declared native∩L3 overlap) · **`docs/jobs-surface/spec.md`** §4 (the contract `OH-01` must meet)
· `docs/paper-outputs/spec.md` · `docs/build-plan-2026-08/plan.md` (master sequencing) ·
`docs/next-session-plan/plan.md` (older board — Tracks W/Q/V/E DONE) ·
**`agent_handoff/lane-wraps/lane3.md` §RESULTS** · **`docs/integration-robustness/proposal.md`**
(awaiting owner reaction) · **`docs/cloud-providers-contract/spec.md`** (FROZEN — read before
touching cloud) · **`docs/milestone-review-2026-07-25/findings.md`** (54-finding backlog) ·
`agent_handoff/DECISIONS.md` (#12 = lucide stays) · `docs/on-hold/README.md` ·
`docs/next-session-plan/lane-mechanics-from-thalon.md` · `docs/restructure/plan.md` ·
`docs/fe-review/spec.md` · CLAUDE.md · `deploy/nango/`. Memory: [[parallel-agent-lanes]] ·
[[selom-machine-migration]] · [[ask-before-docker-wsl]] · [[selom-fe-review-framework]] ·
[[verify-on-real-data-not-mock]] · [[selom-git-commit-email-vercel]] ·
[[verify-ci-in-its-target-event]] · [[selom-shipped-not-reachable]] ·
[[read-gate-output-raw-not-piped]].

## Codex — Last Task & Resume

Codex is away; Claude covers both lanes ([[claude-covers-both-selom-lanes]]). Keep the BE handoff drop-in-ready. Last Codex-lane state of record = `docs/restructure/plan.md` + `plans/v2-backend.md`.
