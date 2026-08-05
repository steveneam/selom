# Reading provenance on the reproduction ledger

_2026-08-05. Implements `agent_handoff/DECISIONS.md` **#16** (owner-decided 2026-08-05). Board item
`#10(b)` + the ledger provenance gap — one seam, so one spec._

> **Status: written first, then BUILT STRAIGHT THROUGH in the same session — owner-directed
> 2026-08-05, no approval pause.** The only founder call this needed is already made in #16. This
> document is the design record the owner reads beside the shipped result, not a gate.

## 1. The defect

`extract.readers.read_metric` returns a `Reading` that already carries its own provenance —
`layer` (L1 / L2 / **L3**), `source` (`table` / `figure` / **`synthesized`**) and a `confidence`
the reader computed for itself. `panel_extractor` then throws all three away:

```python
out[gold.metric] = r.value          # extract/readers.py:379
```

So a metric the reader itself rated **0.45**, annotated *"count of N table rows (lower bound if
capped); via L3-synthesized table"*, renders on `/reproduction/<slug>` — a **top-level sidebar
surface**, not a dogfood path — as **VERIFIED / 100 Selom-confidence**, indistinguishable from a
number read straight off the engine's own Statistics table.

That contradicts three things already on the record:

| Record | What it says |
|---|---|
| table-synthesis **D-t2** | a synthesized table is *"flagged so the scorecard can show it as synthesized-derived"* |
| table-synthesis **S3** | a synthesized table is *"never silently passed off as a native table"* |
| `Reading`'s own docstring | the value + where/how it was read *"drives the honest scorecard"* |

The scorecard is the one consumer that never received it.

**Attribution correction (from the `#4` gauntlet):** this is **pre-existing**, not slice 4's doing.
Slice 4 made synthesized tables more reachable, which is what surfaced it.

## 2. Scope — deliberately narrow

**In scope:** a read whose `source == SRC_SYNTH` is badged on the ledger and caps
`selom_confidence`.

**Explicitly NOT in scope:** the broader blindness — *the score ignores reader confidence at every
layer*. A native L2 read at confidence 0.5 also scores 100 today. Fixing that re-baselines every
published ledger number and deserves a deliberate pass with its own before/after. #16 says so in
as many words. Recorded here as **NEXT**, not silently left out.

## 3. Premises re-derived before building

[[verify-todo-not-already-shipped]] applies to a spec's own rationale, not just its inventory —
two of decided-Q2's four claimed capabilities did not exist, through review, approval and five
slices. So every premise the board handed down was checked against the code first:

| Board premise | Verdict |
|---|---|
| `Reading` carries `layer`/`source`/`confidence` | ✅ `extract/readers.py:51-59` |
| `panel_extractor` discards them | ✅ `extract/readers.py:379` |
| `reproduction.core.MetricValue` is the carrier | ✅ `core.py:216` — two fields today |
| populate at `drive.py:150-152` | ✅ `drive.py:152` builds `MetricValue` from a bare dict |
| `_metric_score` already caps for `substituted` | ✅ `core.py:773` — `92 if substituted else 100` |
| surface on `PanelScore` | ⚠️ **corrected — see below** |

Two corrections, both found by reading rather than trusting:

- ⚑ **`PanelScore.provenance` is ALREADY TAKEN.** It holds the +/− *source* badge (`"ST6+ Fig4e−"`,
  which deposited sources backed the panel) and is populated from `panel.provenance`. Reusing it
  would overwrite a live field with an unrelated meaning — the `normalize`/`pvca` collision one
  level up. The new field is **`reading_provenance`**.
- ⚑ **There are TWO `MetricValue` construction sites, not one** — `drive.py:152` and
  `core.py:938` (`run_panel`). Only `drive.py` is on a production path: `run_panel` has **no
  production caller** (only `tests/test_reproduction.py:220` and two docstrings), the same
  "plausible name, matching docstring, no caller" shape as `reproduction/core.py`'s
  `table_extractor`. So the stamp goes on the drive path, and `MetricValue`'s new fields default to
  `None` so `run_panel` keeps working unchanged rather than being half-migrated.

## 4. Design

### D1 — `panel_extractor` returns Readings; a thin wrapper keeps the value contract

`validate_panel(panel, computed: dict[str, value])` compares `computed.get(metric)` against the
golden with `classify_metric`. Returning `Reading` objects from `panel_extractor` would break that
comparison at every call site, so the split is explicit:

```python
def panel_extractor_readings(panel, figure, table) -> dict[str, Reading]   # NEW — the rich one
def panel_extractor(panel, figure, table) -> dict                          # values, unchanged
```

`panel_extractor` becomes `{k: r.value for k, r in …}`. Its existing contract — *an unreadable
golden is omitted, never set to `None`* — is preserved **in the rich function**, so the two cannot
drift on the rule that separates "read a value" from "needs_recipe".

**Rejected: re-reading via `panel_readings`.** It already returns `list[Reading]` for every golden,
so the provenance could be recovered by calling it a second time. But `read_metric` *performs L3
synthesis*, so a second call re-synthesizes every tableless panel — paying the whole cost twice to
recover a value the first call already had, and inviting the two calls to disagree.

### D2 — the provenance rides `MetricValue`, and reaches the score via `ValidationResult`

`score_panel` iterates `validation.results`, not the run's `computed`. So the synthesized fact has
to reach `ValidationResult`. `validate_panel` gains an optional `readings` argument (`dict[str,
Reading]`); when supplied, each result carries the reader's `layer`/`source`/`confidence`. Omitted
→ byte-identical to today, which is what keeps `run_panel` and every existing test unchanged.

### D3 — cap `selom_confidence`, following the `substituted` pattern exactly

`_metric_score(verdict, blame, *, substituted)` gains `synthesized: bool = False` and caps the
**second** element — the Selom-confidence axis — where `substituted` caps the **first**:

```python
if verdict == EXACT:
    return (92 if substituted else 100), (SYNTH_CONFIDENCE_CAP if synthesized else 100), ATTR_SELOM
```

**`SYNTH_CONFIDENCE_CAP = 75`.** The cap applies to every verdict's confidence, not just `EXACT`,
because a synthesized read is no more trustworthy when it lands CLOSE than when it lands EXACT.

Why cap and not badge only: **a badge is disclosure a reader can miss while the headline number
still says 100.** The cap is also the existing pattern in the same function, so this introduces no
new concept — and it is a *cap*, never a floor, so a read that already scores lower for a better
reason keeps its lower number.

Why the confidence axis and not reproducibility: the two axes split precisely so the colour is
never accusatory. *Whether the figure can be regenerated* is a property of the paper and its data;
*how Selom read the number back* is Selom's own. A synthesized read is entirely our business.

### D4 — the badge

`PanelScore.reading_provenance: str = ""` — empty for a native read, `"synthesized"` when any
metric on the panel was read from a synthesized table. A panel takes the **worst** of its metrics
everywhere else, so it takes the badge if *any* metric earned it.

## 5. Invariants (each gets an executable guard)

| # | Invariant | Guard |
|---|---|---|
| G1 | A synthesized read caps `selom_confidence` at 75 even on an EXACT verdict | `test_reproduction_provenance.py` |
| G2 | A native read is **byte-identical** to today — same score, empty badge | same |
| G3 | `panel_extractor` still omits (never `None`s) an unreadable golden | extends `test_readers.py` |
| G4 | The two extractors agree on values — the wrapper cannot drift | same |
| G5 | The cap is a CAP: a lower score for another reason is not raised to 75 | `test_reproduction_provenance.py` |
| G6 | The badge reaches `PanelScore` and the FE type | guard + `lib/reproduction/types.ts` |

## 6. What this does NOT change

- No golden moves: a native run's numbers are identical, which G2 asserts by equality.
- No FE score arithmetic — the FE renders what the backend sends.
- `run_panel` keeps its current behaviour (new fields default `None`).

## 7. ⚑ The three published ledgers do NOT exercise this — and that is expected

Checked against the real engine after building, not assumed:

```
rpgrip1      panels= 10  reading_provenance values=['']
jev          panels= 11  reading_provenance values=['']
hani         panels=  8  reading_provenance values=['']
```

All three ship as **captured replays**: `drive_captured` calls `validate_panel(panel,
entry["computed"], …)` with values recorded from verified observations and **no readings**, so no
reader runs and nothing can be synthesized. `""` is the correct answer for every one of them, which
is why `lib/reproduction/fixture.ts` — *real engine output, regenerated not hand-authored* — carries
`reading_provenance: ""` throughout and still matches what a regeneration produces.

The defect #16 describes fires on a **live** drive (`drive_bundle` → `panel_extractor_readings`),
the path a real paper drive takes. Proven end-to-end there by
`test_the_whole_path_end_to_end_on_a_really_synthesized_read`: a tableless `cluster` panel, no
Statistics table, L3 synthesis reconstructing the table off the bar trace at confidence **0.45** —
formerly VERIFIED / **100**, now VERIFIED / **75** + `synthesized read`.

Recorded because the alternative reading — "the badge never appears, so it does not work" — is
wrong and would cost someone an afternoon.

## 8. NEXT (deliberately not done here)

The score still ignores reader confidence at every OTHER layer: a native **L2** read at confidence
0.5 scores 100 exactly as an L1 read at 1.0 does. #16 rules that out of scope on purpose — it
re-baselines every published number and needs its own before/after pass.
