# LANE 1 WRAP — Backend integrity sweep

_Written 2026-07-25, worktree `/home/deploy/work/selom-lane1`, branch `agent/backend-integrity/l1`._
_Deliberately left **untracked**, like `LANE-KICKOFF.md` — lane-local scaffolding must not ride the
merge train._

**Status: COMPLETE. All 9 rows DONE. Nothing blocked. 5 commits on the branch, not pushed, not
merged, not rebased.**

---

## Status per ID

| ID | Finding | Status | Commit |
|---|---|---|---|
| L1-01 | A10 (HIGH) | **DONE** — gene SELECTION is tiered (exact → strong-substring); `GENE` stays the presence set | `dd14870` |
| L1-02 | A19 | **DONE** — one `engine.columns.resolve`; six `_pick` forks deleted; drift guard upgraded to lock the RESOLVER + an AST re-fork scan. **One residue, see below.** | `dd14870` |
| L1-03 | A14 | **DONE** — `join` defaults to `inner` (no fabricated count); `gene_overlap()` verdict on `uns` + `summarize()` | `ad7c054` |
| L1-04 | A21 | **DONE** — `engine.ingest.is_10x_dir` / `load_unit`; assemble has no reader of its own | `ad7c054` |
| L1-05 | A15 | **DONE** — `t` anchored to `transform_t` → `$PnR` → 262144, recorded in `layout.meta.transform` + the methods prose | `8312447` |
| L1-06 | A16 | **DONE** — `parse_gates` returns `(gates, dropped)`; population table gained a `status` column; no root-mask parent fallback | `8312447` |
| L1-07 | A17 | **DONE** — unmeasurable OPs return `None` + `measurable:False` + `reason`; `op_group_mean()` excludes them | `474ef7d` |
| L1-08 | A18 | **DONE** — `landmarks()` records `detector` + the noise-gate outcome; all 3 ERG methods templates disclose it | `474ef7d` |
| L1-09 | — | **DONE** — OP · PhNR · flicker-Fourier reach the statistics table via 3 declared params, all default OFF | `3b6ded8` |

`docs/next-session-plan/plan.md` §Lane 1 and `docs/milestone-review-2026-07-25/findings.md` both
carry the full detail; each Status flip landed in the same commit as its fix, and every commit
message names its ID.

---

## Verify result — the ledger, run raw

```
export SELOM_DATASETS_DIR=/home/deploy/migration/selom-migration-staging/selom-data
export SELOM_PYTEST_WORKERS=2
./scripts/verify.sh --be
```

```
======================= 1366 passed, 6 skipped in 25.05s =======================
[verify] GATE be-test PASSED

==============================================================================
[verify] LEDGER  (31s)
==============================================================================
  PASS  hygiene
  PASS  be-lint
  PASS  be-test
  SKIP  frontend gates (--be)
  NOTE  Running inside a git WORKTREE. Measured on this box: fe-lint, fe-types and fe-test all
        resolve correctly through the shared node_modules symlink, but fe-build CANNOT run --
        Turbopack rejects it. So fe-build is a MERGE-TRAIN gate on the main checkout.

[verify] RESULT: PASS -- every gate that ran passed.
```

Baseline on the forked `main` was `1316 passed, 6 skipped`; the lane adds **50 tests** and no
skips. Exit code checked directly (`EXIT=0`), never through a pipe.

---

## Real-dataset verification — what was actually run, and the one gap

Every row was exercised against `SELOM_DATASETS_DIR`, not a fixture, **except FACS** — read the gap.

| ID | Real dataset | What it showed |
|---|---|---|
| L1-01 · L1-02 | `eyg28/raw/…RUVge-K4…DEGs_All_PDE6B_FS_d180…csv`, `alpk1/ro_irpe/DE/*.csv` | The real limma/biomaRt exports resolve to **exactly the same columns as before** (`GeneID` · `external_gene_name` · `logFC` · `FDR`). The A10 hazard built from those same rows (`gene_biotype,logFC,FDR`) now resolves to `None` → frame-index labels; before, `protein_coding`/`lncRNA` went onto the figure. |
| L1-03 · L1-04 | `hani/geo` GSE201356 per-sample 10x triplets | 2 real samples assemble identically (48923 cells × 64591 genes) and now report `ok`. The documented `GRCh38_`-prefix reference mismatch reports 31053 of 98129 genes shared — **67 076 gene columns that used to be assembled as fabricated zeros, in silence.** Read through the ingest registry. |
| L1-07 | `diagnosys-erg/reduced-csv/dr1.CSV` | A 20–20.5 ms operator OP window now reads *NOT MEASURABLE (analysis window carried too few samples)* where the old code reported **SumOP = 0.0**; a 20–25 ms window is a genuine measured 0.0. 21 real segments (7 `.iwxdata` + 14 Diagnosys) are all measurable and byte-identical. |
| L1-08 | `iwx/*.iwxdata` (CMRI mouse scotopic) | The robust detector's b-wave differs from windowed on **7 of 7** real segments (157.8→192.5, 225.0→147.7 µV …) and **7/7 a-waves + 5/7 b-waves** were measured by the near-floor fallback. None of that was disclosed before. |
| L1-09 | `iwx/*.iwxdata` + `diagnosys-erg/full-txt-exp8/453_AAV_C1….TXT` | Trace grid reports ΣOP 201–451 µV / 4 OPs / PhNR BT 102–165 µV per segment with the a/b columns **and the figure** unchanged. The real flicker export reports a 4.81 µV fundamental at 10.7 Hz and 1.05 µV at 28 Hz alongside its N1→P1. |
| L1-05 · L1-06 | **none available — see gap** | Verified on a synthetic FCS instead. |

### ⚠ Gap the founder should know about: there is no `.fcs` anywhere on this box

`find /home/deploy/migration/selom-migration-staging -iname "*.fcs*"` returns **nothing**. The
corpus has scRNA, bulk DE, ERG and paper assets — no flow cytometry. So L1-05/L1-06 were verified
against an FCS written by FlowIO's own writer, which is the strongest evidence available in-tree
but is not the real-dataset clause the kickoff asks for.

What the synthetic run did prove, quantitatively: with the OLD data-anchored `t`, **one saturating
event moved a gate's population count from 0 to 7** between two otherwise-identical files; with
`$PnR` it is 7 on both. **Ask: a real acquisition (any panel, any instrument) would close this
properly.** Until then, treat the FACS numbers as guard-verified, not data-verified.

---

## Things the lead must know at the train

1. **Behaviour change with a Lane 2 follow-up.** `assemble_scrna` now defaults to `join="inner"`,
   so `/data/assemble-scrna` returns the gene INTERSECTION. `routers/data.py` (Lane 2's territory)
   exposes **no `join` form field**, so `"outer"` is currently unreachable over the API. It is one
   `Form(...)` parameter. Not a blocker — `inner` is the honest default and the verdict is already
   carried in the `X-Assemble-Summary` header with no route change.
2. **Two table shapes changed** (additively, at the end, so leading columns are stable):
   `_flow.population_table` gained a `status` column; the ERG tables gain OP/PhNR/Fourier columns
   **only when the new params are on**. No golden moved — the FACS golden covers `data`+`layout`
   only, and the ERG params default OFF. If Lane 3 or the FE asserts on FACS table width anywhere,
   that is the one place to look.
3. **`layout.meta` gained three sibling keys** next to the frozen `significance` /
   `compensation_applied`: `transform`, `gates_unresolved` (FACS) and `ab_detector` /
   `oscillatory_potentials` (ERG). **Nothing was renamed** — the freeze held.
4. **Three files outside the declared territory glob, deliberately, each disclosed:**
   - `app/backend/engine/test_vocab_drift_guard.py` — the existing home for the fork guard. CLAUDE.md
     requires a new invariant to extend an existing guard test in the *same* change, and no other
     lane touches `engine/`. It now locks the RESOLVER by identity (not just the vocabulary) and adds
     an AST scan that fails on a re-forked matcher under `skills/**`.
   - `app/backend/tests/test_enrichment_columns.py` — **mechanically forced**: it imported
     `skills.enrichment.run_real._pick`, which L1-02 deletes. Leaving it would have left the gate
     red. Rewired to `engine.columns.resolve`, nothing else. No other lane owns this file.
   - `docs/next-session-plan/plan.md` + `docs/milestone-review-2026-07-25/findings.md` — the Status
     ledgers the definition of done requires.
   `tests/test_contract_cloud_providers.py` and `tests/test_reachability_guard.py` were **not
   touched** (verified against the branch diff). `pyproject.toml` / `uv.lock` were **not touched**,
   so the shared `.venv` is unmutated. No `npm install`, no dev server, no browser, no git-config
   change.
5. **Residue on A19, recorded not hidden.** The finding also asks that `engine/qc.py:162` (which
   resolves the p column by EXACT tuple membership, a third semantics) route through
   `engine.columns.resolve`. `engine/qc.py` is **outside** this lane's territory glob, so it was not
   done. It is a genuine open item — QC and a runner can still read different columns from the same
   table (a `padj_bh` header matches in the runner, misses in qc). It is a ~5-line change once
   someone owns that file; the resolver it needs now exists.
6. **The new FACS guards are deliberately NOT `@slow`.** `tests/test_flow_smoke.py` carries a
   module-level `pytest.mark.slow`, so it is excluded from `pytest -m "not slow"` — i.e. from
   `scripts/verify.sh`. A claim guard that never runs in the gate of record is not a ratchet, so the
   honesty guards went into a new `tests/test_flow_gating_honesty.py` (in-glob, unmarked). Worth
   knowing generally: **the whole FACS smoke suite is invisible to `verify.sh` today.**
7. **The re-fork detector is proven to fire.** `engine/test_vocab_drift_guard.py` carries the three
   spellings of the deleted `_pick` as fixtures and asserts the detector catches all of them, plus a
   negative case proving it stays quiet on ordinary skill code. A guard nobody has seen go red is not
   a ratchet.

---

## Not done (and why)

Nothing in `L1-01`…`L1-09` is outstanding. The two items above (§5 `engine/qc.py`, §1 the Lane 2
`join` form field) are **out-of-territory follow-ups**, not unfinished lane work — both are recorded
in the findings ledger and the plan so they cannot be lost.

**Protocol observed:** committed as I went with named paths (never `git add -A`), each fix and its
Status flip in the same commit, no merge, no push, no rebase. The pane is now idle.
