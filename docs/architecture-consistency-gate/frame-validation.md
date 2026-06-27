# D2 — Frame-validation at the stage seams

_Last updated: 2026-06-27 — Claude. Companion to `roadmap.md` (Task D, D2) and
`skill-input-contract.md` (D1)._

## The problem

The run path is a pipeline — **ingest → clean → skill** — each stage handing a frame to the
next. D1 ([`skill-input-contract.md`](skill-input-contract.md)) gates the *semantic* contract:
does the dropped data carry the right **modality / named columns** for this skill? But D1 checks
**presence** by column-name synonym. A column can be present by name yet carry no usable data:

> a DE table whose `log2FoldChange` column exists but is **entirely empty** (every cell blank).

That frame passes QC (the p-value column gives it numeric data), passes D1 (both column names
exist), and slips into the runner — where `df[fc_col].to_numpy(dtype=float)` yields an all-NaN
array and the volcano draws a **silently-degenerate figure** (or, in another runner, a downstream
crash). The owner's acceptance:

> A malformed clean→skill handoff fails at the **seam** with a clear **400**, not a downstream
> crash.

## The three layers (one source of truth each)

| Layer | Question | When | Result |
| --- | --- | --- | --- |
| **QC** (`engine.qc`) | *Is the data clean?* (coarse, whole-frame: empty / negative counts / …) | `/data/inspect` + `/run` | a block flag → 422 `data_check_failed` |
| **D1** (`engine.compat`) | *Are the named columns / modality this skill needs present?* | `/run`, before the runner | 422 `data_contract_failed` |
| **D2** (`engine.frame_schema`) | *Do those present, required columns carry usable data?* | `/run`, after D1, before the runner | **400 `frame_validation_failed`** |

The layers are complementary, never overlapping: D2 only ever inspects columns **D1 has already
confirmed present**, so a *missing* group is D1's 422 (D2 never double-reports it), and an empty
frame is QC's block (D2 never re-checks it). Each layer owns one question.

## The check (`engine.frame_schema.check_skill_input`)

For each required column group in a skill's D1 contract (`compat._SCHEMA`), resolve the actual
column and flag a **positively-determined** structural defect:

* **`empty_column`** — every value missing (or, a text column, every cell blank).
* **`non_numeric_column`** — a required *numeric* group (fold-change / significance) whose column
  has no value that parses as a number. A column with ≥1 parseable number is **not** flagged — the
  runner coerces it (honest, no false block).
* **`duplicate_column`** — the required name appears twice, so the single-column read selects a
  2-D frame and mis-shapes downstream.

The numeric groups are **derived** from the classifier synonym sets (`databundle._LOGFC` / `_PVAL`),
so the column vocabulary stays single-sourced with D1 — D1 reads a group's *presence*, D2 reads the
*usability* of the same resolved column. The check is `lazy` by default (every defect collected so
one 400 lists them all; `lazy=False` stops at the first).

Honest, like D1 and the matcher: only a *certain* defect blocks, it is **overridable**
(`override=true`, the same escape hatch as the QC + D1 gates), and any column it can't evaluate is
left alone (never a guessed block). The FE already surfaces a typed gate's `detail.message` as-is
(the D1 path), so the user reads *"the fold-change column 'log2FoldChange' is empty…"*, not a stack
trace.

## Dependency-free (no pandera)

The roadmap named `pandera` as the obvious schema tool, but it is a new venv dependency on the
EDR-fragile hand-sewn venv. Following the C1 "no `diskcache`" precedent and
[[selom-uv-sync-footgun]], D2 is a lightweight `lazy`-style collector built on the pandas/numpy the
engine already imports — same expressive shape (a named schema, every violation reported at once),
no new dependency.

## The result seam (a named schema, guarded)

`validate_result_table(table)` is the schema for the **output** seam: a well-formed `StatsTable` has
a non-empty `columns` list and rectangular `rows` (each as wide as `columns`). It is not wired as a
raising gate (a malformed *output* is a runner bug, not a user 400) — instead a test
(`test_frame_schema.py::test_native_result_tables_are_rectangular`) asserts every native-table skill
emits a rectangular table, the ratchet that keeps a runner from shipping a ragged table the FE
Statistics node would choke on.

## Guards (the ratchet)

* `tests/test_frame_schema.py` — the unit contract: empty / non-numeric / duplicate detection, lazy
  vs strict, missing-column-is-D1, the single-sourced numeric-group derivation, the result-seam
  schema + the native-table ratchet.
* `tests/test_frame_validation.py` — the endpoint behaviour: an empty required column → **400** at
  the seam (the acceptance), a well-formed table → 200 (no false block), `override=true` bypasses, a
  missing column is D1's 422 (not D2), an uncontracted skill is not seam-checked.

## Not in D2 (documented scope)

* Cleaning is **advisory** today (`engine.cleaning` returns a *plan*, "used as-is" — it does not
  transform the payload), so the frame at the skill seam *is* the ingested frame. When cleaning
  becomes an applied transform, the same `check_skill_input` validates the post-clean frame at that
  seam with no change.
* The `jobs` path (`POST /skills/{id}/jobs`) is not seam-checked here — it already wraps runner
  errors into the job's `error` field (no 500 leak); the gate can extend there if a clearer
  submission-time message is wanted.
* Broadening the column rules beyond the DE-table consumers is a fill-in-the-blanks follow-up — add
  a `compat._SCHEMA` entry and D2 picks it up (one declaration, both layers).
