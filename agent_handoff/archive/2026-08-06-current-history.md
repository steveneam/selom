# CURRENT.md history — archived 2026-08-06

Write-once. Eight LIVE blocks lifted out of `agent_handoff/CURRENT.md` (sessions LANE-A-C
through DEG-PANEL, 2026-08-03 → 2026-08-06) when the board was pruned: it had reached 1083
lines / 165 KB, which a resuming session is told to read IN FULL and which no longer fit in a
single read. Per `agent_handoff/README.md` — "history moves to `archive/`, not by growing the
file". Nothing here is live; the authoritative record is the commit range each block names.

---

## ▸ LIVE · DEG-PANEL · 2026-08-06 02:02 +1000 (Sydney) · branch `main` (**LOCAL — the pushed BASE is `ea68c79`; several sessions now sit on top of it. Working tree clean. ⚑ NO AHEAD-COUNT HERE ON PURPOSE: a handoff commit cannot know its own SHA. Trust `git log --oneline origin/main..HEAD`, not this stamp. Owner pushes.**) · Claude (FE+BE, solo, lead)

- **The board's `#1(d)` is DONE**, spec-first, as one change (`docs/deg-panel/spec.md` → `3f102ea`).
  Detail is in the commit; what follows is what a next session needs and could not re-derive.
- **⚑ AN EIGHTH LAYER OF [[selom-shipped-not-reachable]], AND IT IS THE ONE NO GUARD CAN SEE.**
  `deg`'s runner honoured two params its `skill.json` never declared (`group_regex`, `label_val`):
  `_execute` merges unknown caller keys straight through, `validate_param_ranges` skips them, and
  `resolved_params` **records them into the provenance bundle**. So they work — and because every
  guard in this repo is driven by the DECLARATION (`API_ONLY_KNOBS` iterates the spec, the
  prose↔param guard compares against `param_spec`, `paramFieldsFromSpec` drops an overlay key with
  no spec entry), **not one of them can look down that arrow.** The previous seven layers were all
  *the user cannot reach it*; this is *the param works and nothing admits it exists*.
  **The guard for it is NOT built** — see NEXT#11, which is the highest-value item this session
  leaves behind.
- **⚑ A CONTROL PASS FOUND A FIGURE DEFECT, NOT JUST PROSE.** Two sessions running, reading a
  runner's body for a REACHABILITY job is what surfaced the honesty defect. Here the axis of the
  flagship DE skill named a quantity the figure does not contain, and the tell was on screen the
  whole time: **a "log2 fold-change" of 44.6**. Nine gates green, `skill-smoke` green, and the
  golden untouched — because the golden pins the STUB. **Render the figure and read the axis.**
- **⚑ `layout.meta` IS NOW THE DEFAULT ANSWER FOR ANYTHING `auto`, FOURTH USE.** `meta.significance`
  → `meta.adaptation` → `meta.clustered`/`meta.gsea` → `meta.deg`. If a param resolves at run time
  (from the file, from an alias list, from what is importable), the prose must read the runner's
  record. Expect this shape in `heatmap`/`integration`/`normalization_qc` too.
- **⚑ THE LEVEL WIDGET'S ONE JUDGEMENT CALL, so nobody re-opens it.** It does NOT fall back to
  `design.best_group` when several candidates exist. `best_group` genuinely IS the engine's deg
  contrast pick, and `questionnaire._obs_aliases()` imports `deg.run_real`'s own
  `_CONDITION_FALLBACKS` rather than shadow-copying them — so the two agree **whenever an alias
  column is present**. Where none is, the runner **raises** while `best_group` falls back to the
  lowest-cardinality candidate, so the picker would offer levels for a run the backend refuses.
  One rule with no exception beat two.
- **Two corrections against my own spec, written into it rather than quietly fixed.** D1's "under
  `auto` only the shared knobs render" would have **hidden controls that ship today** — a
  regression created by a reachability fix, the `fdr_threshold` lesson one level up. D6 had the
  stub's axis moving to meet its table; the table was the dishonest half, and moving it instead is
  more truthful AND moves no golden. **A spec's own decisions are re-checkable while building.**
- **⚑ RECORDED, NOT WORKED AROUND: `rpgrip1_merged.h5ad` (1.2 GB) CANNOT BE DRIVEN THROUGH THE
  BROWSER HARNESS.** The dev proxy drops the upload (`socket hang up`), the dataset is never
  inspected, and every data-derived control then degrades to text **through no fault of its own** —
  which reads exactly like a broken picker. It is the best-designed file in the corpus (`genotype`
  WT/C3/FS/PT · `sample` ×9 · `celltypes` ×7) and the engine detects all of it correctly when
  called directly. The picker check runs on `hani_irpe_subset` (131 MB) instead. **Anything needing
  a large-file browser path is blocked on this.**
- **Also worth knowing: `jev/retina_fadl.h5ad` has only TWO obs columns** (`n_genes`, `leiden`) —
  **no condition column at all.** The standard scRNA smoke file cannot exercise any design-derived
  control, and a check that assumes it can will fail on a correct fail-soft degrade.
- **Gates.** `verify.sh` **9/9 raw, exit 0, corpus set** · **skill-smoke 43 pass / 0 fail, no
  regression** · **browser-verify `deg-panel` 4/4** plus a 10/10 regression pass over
  `param-pickers`/`api-only-knobs`/`shared-vocab-knobs` (the shared merge + gate machinery changed).
  Every new pin confirmed RED first. **`wf-lint` was RED on `main` before I started** and is fixed
  in its own commit (`aba600b`) — upstream tagged `dorny/paths-filter`'s pinned commit `v3.0.3`, so
  the bare `# v3` comment stopped naming a version. It would have failed CI too.
- **⇒ NEXT SESSION.** `#1`–`#4` are closed. **`API_ONLY_KNOBS` is 52 across 10 skills · PROSE_SILENT
  untriaged is 131** — both MEASURED. In value order: **NEXT#11, the undeclared-param guard** (new,
  and the only one of these that closes a whole invisible class) · **`#2`'s remaining 131**
  (`heatmap`/`integration`/`normalization_qc` are the biggest blocks) · **`#5`'s JTBD backlog**.
  ⚑ **But read the strategic call in DEFERRED first — it is still unanswered, and its own
  recommendation was "do `#1(d)`, then pivot to P-E". `#1(d)` is now done.**

<!-- superseded — GSEA-KNOBS + LEDGER-PROVENANCE, kept for its findings -->
- **The board's `#3` and `#4` are BOTH DONE, in the owner's order.** Detail is in the two commits;
  what follows is what a next session needs and could not re-derive.
- **⚑ READING THE RUNNER'S BODY FOR A *CONTROL* PASS FOUND THREE PROSE LIES.** `#3` was scoped as a
  reachability job (13 knobs). Establishing what `gene_sets`/`gene_set`/`weight` actually MEAN
  required reading both runners end to end — and that read, not the guard, is what surfaced:
  `engine` defaults to `auto` and resolves from what is IMPORTABLE, yet the paragraph said
  "(gseapy.prerank)" and cited GSEApy on every run, including blitzGSEA's and the in-house engine's;
  `n_perm` was quoted RAW while both library engines floor it at 100 (`n_perm=0` → 1000); and
  Benjamini-Hochberg was claimed **and cited** on single-set and in-house runs that correct nothing.
  **The prose↔param guard was green throughout, because it checks a param is MENTIONED, not that
  the sentence is TRUE.** That is the guard's known blind spot and it is worth expecting again.
- **⚑ `VIA_OUTCOME` is now the default reach for anything `auto`.** All four fixes (three above +
  ssGSEA's `top_n` cap-quoted-as-a-count) are facts only the runner has, so they ride `layout.meta`
  and are lifted by `build_body` / `legends._facts` — the `meta.significance` pattern, third use.
- **⚑ A SHARED BLOCK'S OPT-IN DEFAULT SAVED A REAL BUG.** `geneSetLibrary(..., overridable=false)`:
  `enrichment` declares **no `gene_set` param at all**, and a gate naming an absent key never
  matches — sharing it unconditionally would have left `enrichment`'s library select **permanently
  disabled**. Verify what is actually shared before sharing it, again.
- **Mobbin ruled a pattern OUT twice, both recorded in code.** An override should be an EXPLICIT
  mode (Google AI Studio's preset dropdown; WRITER's segmented Upload/Paste-URL/Paste-text) — Selom
  cannot without a backend `mode` param, so the library select GREYS OUT instead. And Fey's
  Estimated-vs-Actual EPS **columns** cannot apply to the ledger, which holds ONE value per metric.
- **⚑ `#4`'s two corrected premises are the reusable part.** `PanelScore.provenance` was **already
  taken** (the deposited-source badge) → new field `reading_provenance`; and `run_panel` has **no
  production caller**, so only `drive.py` was stamped. Both found by reading, not by trusting the
  board [[verify-todo-not-already-shipped]].
- **⚑ THE LEDGER BADGE CANNOT APPEAR ON ANY PUBLISHED LEDGER, AND THAT IS CORRECT.** rpgrip1 · jev ·
  hani all ship as CAPTURED replays (`validate_panel(panel, entry["computed"])`, no readings), so
  all 29 panels are `""` and `fixture.ts` still matches a regeneration. **Do not read "the badge
  never shows" as a defect** — it fires on a LIVE `drive_bundle`, proven end-to-end by a tableless
  `cluster` panel (reader confidence 0.45: was VERIFIED/100, now VERIFIED/75 + badge). Spec §7.
- **New capability: vitest now includes `components/**/*.test.ts`** — a component PREDICATE ("does
  this badge appear at all") is testable without a DOM. The repo could not test any component
  before. [[compound-capability-each-task]]
- **⚑ MY OWN MISTAKE, WORTH NOT REPEATING: `git checkout <file>` to undo a temporary probe
  DISCARDED every uncommitted change in that file.** I had disabled one line to prove a guard bit,
  then reverted the file — losing seven edits to `reproduction/core.py`. Re-apply the probe in
  reverse, or copy the file first (which is what I did for the second such check).
- **Gates.** `verify.sh` **9/9 raw, exit 0, corpus set** on both commits · **skill-smoke 43 pass /
  0 fail, no regression** · **browser-verify `shared-vocab-knobs` 5/5** on real backend + real
  corpus. Every new pin confirmed RED first — **except one, and it is labelled as such**: the
  ssGSEA string-`"false"` zscore test passes pre-fix too, because `resolved_params` already casts
  by declared type. The defect I expected there was **not real**; it is kept as a contract pin.
- **⇒ NEXT SESSION.** `#1`–`#4` are closed. The board's remaining items, in value order: **`#2`'s
  166 untriaged prose waivers** (best blocks: `deg` 26 — which the board says belong WITH `#1(d)`'s
  spec, not piecemeal — then `heatmap`/`integration`/`normalization_qc`) · **`#1(d)` `deg` (16), the
  largest knob gap and the one that WANTS A SPEC** (fold NEXT#2's level widget in: `deg.reference`/
  `treatment` and `diff_abundance`'s 7 are the same "pick a level, not a column" shape) · **`#5` the
  fe-review JTBD backlog** (all feature gaps, not defects; copy-to-clipboard on a table is the
  cheapest — `components/methods/copy-button.tsx` is ready-made). `API_ONLY_KNOBS` is **73 across
  11 skills**. Do not open `facs_gating` (blocked on a real `.fcs`).

<!-- superseded — PROSE-TRIAGE, kept for its findings -->
- **The board's `#2` is done for the ERG family and for every result-changing param it named.**
  Detail is in the commit; what follows is what a next session needs and could not re-derive.
- **⚑ THE BOARD'S GUESS AT A BACKLOG'S SHAPE IS A CLAIM, NOT A FINDING.** It predicted ERG would be
  a confirmed-waive pass ("mostly pipeline-level/internal"). **26 of its 50 params decided what the
  figure CLAIMS**, and two of the defects were in the FIGURE (a title hard-coding "scotopic", a
  value axis hard-coding "log1p"), not the prose at all. The rule that found them is the same one
  the `normalize`/`pvca` block established: **read the runner's BODY.** A waiver list inherits the
  confidence of whoever wrote it, and nobody had read these.
- **⚑ THE VERDICT VOCABULARY IS THE REUSABLE PART, and `VIA_OUTCOME` is the one to remember.**
  A param that is **inert unless a data-dependent branch fired** must be described from the
  runner's RECORDED outcome, never from the param — only the runner knows whether the branch ran.
  `adaptation="auto"` resolves from the data; whether `violin` had to cluster the cells itself is a
  fact about the data. Both now ride `layout.meta` and are lifted by `build_body` as `_`-prefixed
  facts (the `meta.significance` pattern), **written only when they differ from the param-derived
  answer**, so a default run is byte-identical and no golden moves. Expect this shape again the
  next time a knob "usually does nothing". [[waiver-list-needs-a-verdict-per-entry]]
- **⚑ A COUNTED RATCHET MUST ASSERT EQUALITY, NOT `<=`.** `_UNTRIAGED_CEILING` is compared with
  `==`; with `<=` the backlog shrinks on paper while the ceiling stays slack and the next new param
  slides in under the old headroom. **It caught me leaving 211 in place when the count was 179**, on
  its first run.
- **`_pairwise_prose` is the one home for the significance sentence** — boxplot · violin ·
  erg_bwave_bar all draw brackets off `_stats.test_pairs`, so they get one sentence, and it carries
  the clause none of them had: **an overridden pair (`A~B:**`) was not computed, so neither the
  named test nor SciPy may be credited with it.** Related: I nearly wrote a THIRD copy of the pairs
  parser — `_stats.parse_pairs` already existed and is strictly more capable than the local
  `_parse_comparisons` I was moving. Grep before you extract.
- **Gates.** `verify.sh` **9/9 raw, exit 0, corpus set** (BE 1704 fast + 397 slow · FE 730 ·
  fe-build green) · **skill-smoke 43 pass / 0 fail, no regression**. 22 new pins, **all confirmed
  RED first** by stashing the fix and re-running.
- **⇒ NEXT SESSION IS SCOPED, owner-directed 2026-08-05: `#3` THEN `#4`.** Do `#3` first — it is
  small and self-contained, so it banks a gate-green commit before the big change starts — then
  `#4`, **spec written FIRST and then BUILT STRAIGHT THROUGH, no pause** (see the NEXT block; the
  only founder call is already made in [[DECISIONS #16]]). **If `#4` runs long, finish it rather
  than starting anything else**; the rest of `#2` (179 untriaged) and `#5` (the fe-review JTBD
  backlog) wait.

<!-- superseded — COMPARE-VERIFY, kept for its findings -->
- **The board's `#1` is CLOSED — the compare fix is verified in a browser, and verifying it found a
  second defect of the same family.** Detail is in the commit; what follows is what a next session
  needs and could not re-derive.
- **⚑ THE LESSON IS ABOUT THE TESTS, NOT THE BUG.** `diffTables` dropped every duplicate-labelled row
  and the unit suite was green, because **every fixture in `diff.test.ts` used a UNIQUE first
  column** — the pairwise one included, with a single row. The tests used the one shape that cannot
  exhibit the defect. **When a pin is written from the same mental model as the code, it inherits the
  blind spot; the browser had the real corpus and a second pair, and that is the whole difference.**
  Ask of any fixture: *is this the shape where the thing could go wrong, or the shape I had handy?*
- **⚑ A ONE-ELEMENT CASE CAN MAKE A CHECK VACUOUS.** BH on a single p-value returns it unchanged
  (rank n of n), so a one-pair `correction` sweep would have passed on the added `p (bh)` column
  alone — and gone on passing if the correction silently did nothing. The check uses **two** pairs so
  at least one adjusted value actually moves. Same trap anywhere a correction, a rank, a normalization
  or a dedup is exercised on a single item.
- **`sweepIntoCompare` is new harness capability** [[compound-capability-each-task]] — the fourth
  entry fixture. Compare needs SIBLINGS (`parentFigureId`); two runs of a skill are two unrelated
  figures, which is why the surface had never been driven. Any future compare/lineage/version check
  starts here rather than re-improvising.
- **Playwright: locate a control inside a wrapping `<label>` BY ROLE, not `getByLabel`** — getByLabel
  matches the label's `textContent`, which for a wrapped `<select>` sweeps in every `<option>`. The
  a11y name is correct; the locator algorithm is not the same thing. Cost one red run.
- **Gates.** `verify.sh` **9/9 raw, exit 0, corpus set** (BE 1682 fast + 394 slow · FE 730 ·
  fe-build green) · **browser-verify `compare-tables` green, `stats-view` 5/5 green.**
  ⚑ **A COMBINED `stats-view + compare-tables` pass FAILED at check 4** (`lollipop`, 180s timeout
  inside the Store install) **while the same check passes in 16.9s alone** — box contention, not a
  regression [[browser-suite-oom-looks-like-regression]]. No `ERR_CONNECTION_REFUSED`, the server
  survived, and check 5 passed straight after. **Run filtered passes on this box; a single slow
  failure mid-suite is the environment.**

<!-- superseded — STATS-TABLES-5, kept for its findings -->
- **`#4` IS CLOSED.** Slice 5 shipped, both milestone reviews ran over the whole `f5a47c0..HEAD`
  range, and the fix pass landed. Detail is in the three commit messages; what follows is what a
  next session needs and could not re-derive.
- **⚑ THE FINDING THAT MATTERS: a claim in an APPROVED decision can be false, and the decision still
  be right.** Decided-question 2 justified moving κ and λ into a table because a table "sorts,
  exports, **diffs in compare**, and is readable by the metric reader". Two of those four were
  untrue when written. Compare had been diffing `figureTables(a)[0]` only — for the whole of slices
  1–5 — under a card announcing *"The results tables are identical"*; and a WIDE one-row table is
  unreadable by `_read_named_cell` (it keys on a row's first string cell) while `_read_count`
  actively mis-reads it. **The decision was still correct** — the presentational half was real and
  the fix was to make the other half true. But the rationale went through a spec review, an owner
  approval and five slices without anyone running it. **Check the capability a decision RESTS on,
  not just the decision.** Both are recorded as correction blocks in `docs/stats-tables/spec.md`.
- **⚑ ORDER IS LOAD-BEARING WHEREVER A SCALAR TABLE EXISTS, and this will recur.**
  `extract.readers._read_count` answers ANY count-shaped metric (`n_*`, `*_total`) from the FIRST
  table that has rows, falling back to `len(rows)`. A one-row scalar table in position 0 therefore
  answers "how many?" with **1**, at confidence 0.5, on a reproducibility score. Both slice-5
  runners lead with the detail table and say so at the site;
  `test_g3_a_declared_multi_table_skill_leads_with_its_DETAIL_table` proves it by reading the
  REVERSED array. **Any future "attach a summary beside a detail table" change inherits this** —
  put the scalar last, or make the reader shape-aware first.
- **⚑ THE SEVENTH LAYER OF [[selom-shipped-not-reachable]] — and it is a new KIND.** 17 of 27
  native-table skills declared `outputs: [figure]` while attaching a table on every run, rendered on
  three surfaces and built by the live API from the same `skill.json`. The first six layers were all
  *the user cannot get to it*. This one is *the user is told it isn't there* — *nothing looks
  broken*, so nobody goes looking. Found only because regenerating the seed put two of them side by
  side. **Ask of any capability: does the catalog admit it exists?** Now `outputs` declares a table
  IFF the skill is NATIVE, both directions, on the existing native-classification guard.
- **The reviews earned their keep and the fix pass was most of the value.** gauntlet **13
  confirmed**, fe-review **16 confirmed + 23 JTBD**. Every finding re-verified in code before
  acting; several were correctly attributed by the verifier itself as pre-existing or mis-scoped.
  **Four independent lenses found the compare bug** and none of the nine gates could — reading index
  0 of an array is perfectly typed. **Run these at a milestone; they do not substitute for gates and
  gates do not substitute for them.**
- **Two of my own fixes were caught by the instruments they were meant to satisfy**, which is worth
  repeating rather than tidying away: the new `structure.guard` waiver list rejected one of its own
  two entries on its first run (`stats-view.tsx` never matched the pattern), and the browser suite
  went **3/5 RED** after the fix pass because the CSV `aria-label` I added collided with the
  panel-header locator. Neither would have been found by reading the diff.
- **Writing the `ALSO_SYNTHESIZE` route test cost two red runs, both worth pinning**: `pairs=` with
  the wrong SEPARATOR (`,` rather than `~`) and `pairs=` naming absent LEVELS are both
  indistinguishable from `pairs=` never being set — the run silently falls through to single-table
  L3 synthesis. **`pairs=` being SET is not the same condition as `pairs=` being TESTABLE.**
- **RECORDED, NOT FIXED — read this before picking up reproduction work.** `extract.readers`
  computes `Reading.layer` / `.source` / `.confidence` and `panel_extractor` **throws all three
  away** (`out[gold.metric] = r.value`); `MetricValue` carries only `{metric, value}`, so an L3
  synthesized read the reader itself rated 0.45 lands on the ledger as a VERIFIED / 100-Selom-
  confidence cell. **Verified end-to-end on the real drive**, but it is **pre-existing, not slice 4's
  doing** (the gauntlet's own verifier corrected that attribution: the `ALSO_SYNTHESIZE` append
  lives in `routers/_run.py`, and the drive uses `run_skill_with_table`, which never synthesizes).
  It also is not synthesis-specific — the score is blind to reader confidence at every layer. The
  provenance-badge half is defensible; **capping `selom_confidence` is a founder decision** because
  `Reading.confidence` ("did I read the right number") and `selom_confidence` ("is our reconstruction
  trustworthy") are different quantities. Related: the run API and the drive **disagree** about which
  tables an `ALSO_SYNTHESIZE` skill produces.
- **`PROSE_SILENT` is 261 params / 60 templates** (was 269/61 — `("methods","boxplot")` retired),
  split evenly legends 131 / methods 130. **The largest single block is the ERG family in methods —
  50 of the 130**, and NEXT#1(e) already rules those knobs pipeline-level/internal, so the triage
  likely starts with ~50 confirmed waives in one pass and a load-bearing bucket far smaller than 261.
- **Gates.** `verify.sh` **9/9 raw, exit 0, corpus set** on every commit (1672 fast / 394 slow) ·
  **skill-smoke 43 pass / 0 fail**, no regression · **browser-verify 5/5 stats-view + 9/9
  editor-chrome·artboard·zoom**, raw exit 0. Servers released (`:3152`/`:8152` free).
- **Not done, deliberately:** the compare fix is unit-pinned and guard-ratcheted but **has no browser
  check** — no spec drives a two-version family. That is the first thing to verify. Plus the
  `PROSE_SILENT` triage, `#1(c)`, `#10(b)` (which unblocks `violin`'s second table), and the
  fe-review JTBD gaps below.

## ▸ (superseded) LIVE · STATS-TABLES · 2026-08-05 13:00 +1000 (Sydney) · branch `main` (**PUSHED at the owner's request — range `f5a47c0..HEAD`, working tree clean, nothing local, `origin/main` == `HEAD`. CI run `30970426817` GREEN on all six jobs at `6be1fad`; the handoff commits on top of it are docs-only. Trust `git log`, not this stamp.**) · Claude (FE+BE, solo, lead)

- **`#4` slices 1→4 are DONE, in the board's order, with `#10(a)` interleaved exactly where the
  board put it (before slice 5).** Slice 5 (`confusion`/`qq` scalar tables) is the only one left,
  and `#10(a)` — its stated precondition — is now in place. Detail is in the five commit messages;
  what follows is what a next session needs and could not re-derive.
- **⚑ THE FINDING THAT MATTERS: a feature can be unreachable even when every layer of it works.**
  Slice 3 shipped `lollipop` attaching two tables — and `lollipop.pairs`, the knob that MAKES the
  second table exist, was in `API_ONLY_KNOBS`. A two-table result existed that no user could
  produce; it would have worked only from curl. That is the **sixth** layer of
  [[selom-shipped-not-reachable]] — 17 routes → 19 skills → 171 knobs → a slider that cannot reach
  its own value → a control silently overridden → **an unreachable contract capability**. The
  question to ask of any new capability is not "does it work" but "can a user get to it", and
  slice 5 has the same shape: `confusion`/`qq` scalars are only worth moving if the run that
  produces them is reachable.
- **The spec's instruction to RE-DERIVE its own consumer inventory rather than trust it was the
  highest-value line in it.** Four more narrowing sites, one a crash: `workrail.tsx` reads
  `figure.table.rows.length`; `project-workspace.tsx` had `!!figureTable(f)`, and **`!![]` is
  `true`**, so an empty result claimed to have statistics; `legends._facts` narrowed with
  `isinstance(table, dict)` and would have produced a caption with no facts and no error. Keep
  doing this — a spec inventory is a starting point [[verify-todo-not-already-shipped]].
- **⚑ PROVENANCE MUST FOLLOW THE DATA, NOT THE CODE PATH — the trap slice 4 opened and the one most
  likely to recur.** A synthesized table used to be *known* to be synthesized because of **where it
  was built** (only `read_metric`'s L3 fallback branch re-tagged). The moment a native table and an
  L3 summary share one list, that stops holding, and the appended table reads at **full native
  confidence** — a re-shaped value overstating its provenance on a reproducibility score, silently.
  It now reads the table's own `synthesized` flag, which every synthesizer stamps. **Any future
  "attach two things of different trust levels" change has this bug waiting in it.**
- **`violin` is NOT in `ALSO_SYNTHESIZE`, against the spec's own D3 prediction, and the reason is a
  blocker for someone else's item.** Its synthesized table is a PubMed marker call read back out of
  a figure ANNOTATION, and that annotation is a **live network lookup at run time** — so the table
  exists when the network answered and silently does not when it did not. Appending it would put a
  claim in the runtime no guard can check, and would make a network-dependent number MORE reachable
  by a reproducibility score **before** the provenance stamping NEXT#10(b) owes. `violin` joins the
  moment 10(b) lands; that is now a concrete unblock, not a vague backlog row.
- **`#10(a)`'s first red run is the backlog, and it is 269 params across 61 templates.**
  `PROSE_SILENT` is a RAW FIRST CAPTURE and says so in the file — it has **not** been triaged into
  "cosmetic, no sentence owed" (`erg_traces.band_color`, `scale_ms`) versus "changes the result, so
  the prose owes it a sentence". **That second bucket is load-bearing**: `deg.method` decides WHICH
  TEST ran, `proteomics_de.missing` decides an imputation that biases fold-changes toward zero,
  `boxplot.sig_test`/`correction` decide the stars drawn. The triage is the next session's work on
  this item. The ratchet's value does not wait for it: a NEW param must now be described or waived
  on purpose, which is exactly how both 2026-08-05 defects arrived.
- **It paid immediately: `methods._boxplot` held two MORE live printed-vs-computed lies**, both
  stated unconditionally — "box-and-whisker … whiskers extending to 1.5× the IQR" on a
  `style="strip"` run that draws **no box at all**, and "groups are ordered by descending median"
  when `order` puts the user's named categories first. `("methods", "boxplot")` is the first entry
  the ratchet retired, and the **stale-waiver** half is what forced it out.
- **Mobbin ruled out a decision the approved spec had already made** [[selom-fe-review-framework]].
  D2 specified a `Statistics · N tables` heading count; eight mature multi-section report surfaces
  and **not one** heads a group with a count of its sections. Recorded in the spec as a refinement
  of D2's presentation, not a reversal of its decision — **say so if that reading is wrong.**
- **New harness capability** [[compound-capability-each-task]] — **`e2e/browser-verify/stats-view.spec.ts`
  is the first browser check that opens the Statistics view at all.** The suite drove the editor, the
  params and the export menu and left the surface that renders a skill's computed numbers unproven,
  so "slice 1 is a no-op" was not checkable. It also encodes a product fact worth knowing: after
  Apply the work rail **auto-collapses** at this viewport, so the Statistics ROW does not exist until
  `Expand rail` is clicked. Slice 5 should extend this file rather than add another.
- **Every guard in this session was proven to bite by reverting the fix** — nine separate proofs.
  Worth continuing: G2's FE half fired in **`components/`**, the root the spec's own `lib/`-only
  instinct would have missed, and that is only visible because the revert was actually run.
- **Gates.** `verify.sh` **9/9 raw, exit 0, `SELOM_DATASETS_DIR` exported** on every commit (1664
  passed / 5 skipped) · **skill-smoke 43 pass / 0 fail**, no regression, run after slice 3 and again
  after slice 4 · **browser-verify 4/4 green**, all four new this session.
- **Not done, and deliberately:** slice 5 (`confusion`/`qq`) — but it was **SCOUTED** at the wrap
  and four of its assumptions turned out wrong, all written into the RECOMMENDED ORDER block: it is
  reachability-clean, it touches no figure or golden (the scalars are in the TABLE's title, not the
  plot's), **`confusion`'s real-corpus case IS the refusal case** rather than the value case, and a
  one-row table makes three call sites print *"1 rows"*. Also not done: the `PROSE_SILENT` triage,
  and `violin`'s append (blocked on 10(b)).
- **The `#4` MILESTONE BOUNDARY IS THE END OF SLICE 5** — run `review-gauntlet` + `fe-review` over
  `f5a47c0..HEAD` there, not per slice [[review-cadence-phase-not-task]].

## ▸ (superseded) LIVE · KNOBS-1 · 2026-08-05 00:47 +1000 (Sydney) · branch `main` (**PUSHED — `origin/main` = `23256ad`, working tree clean, nothing local; CI green on both pushes, runs `30920091848` + `30920304922`**) · Claude (FE+BE, solo, lead)

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

