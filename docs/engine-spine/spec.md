# Engine spine — spec (P1a, the keystone)

> **Status: DRAFT for owner sign-off** (session 43, 2026-06-21). The owner-picked
> first move from `docs/pillars/plan.md`: *name the structure before adding features.*
> This spec defines the **product-agnostic engine** — the canonical `DataBundle`, the
> ingest registry, and the spine contract that BOTH products call. It is design +
> decisions to confirm BEFORE code.
>
> Cross-lane (the engine lives in the backend; Claude covers both lanes while Codex is
> away — [[claude-covers-both-selom-lanes]]). Companions: `docs/pillars/plan.md`,
> `docs/reproduction-engine/live-reproduction-spec.md` (the reproduction consumer),
> `docs/table-synthesis/spec.md` (P2/L3), [[layered-deterministic-extraction]],
> [[unify-on-superior-framework]], [[compound-capability-each-task]].

## 1. Why (the problem this fixes)

Today the spine exists only as private plumbing inside paper-reproduction. Skills take a
raw `data_path` and each re-loads + re-sniffs the file internally; `extract/ingest.py`
produces a paper-centric `PaperBundle`; QC lives in `normalization_qc`; modality is never
named. So **Product A ("my own data") has no front door** — there is no single object that
says *"this is what the user gave us, here is what it is, here is whether it's clean."*

The fix is one named representation + one ingest path that both products share. Per
[[unify-on-superior-framework]]: we converge on a superior shared shape, we do not bridge
two mismatched ones.

## 2. The canonical `DataBundle`

One in-memory object for *any* tabular/omics input. Library, pure, no FastAPI.

```python
# app/backend/engine/databundle.py
@dataclass
class DataBundle:
    payload:   Any            # the loaded object: AnnData | pandas.DataFrame | dict-of-frames
    kind:      Kind           # canonical modality (see §3) — never None; "unknown" is honest
    source:    SourceRef      # filename, sheet, byte-size, sha — provenance, not bytes
    design:    Design | None  # conditions / batches / groups when discoverable (or attached)
    qc:        QCReport        # cleanliness verdict + honest problem flags (§5); empty == not-run
    meta:      dict           # free-form (n_obs, n_var, gene-id prefix, units, …)
```

- **`payload` is the loaded object, not a path.** Skills gain a `DataBundle`-aware entry;
  the existing path-based entry stays for back-compat (additive — D7).
- **`kind` is always set.** Detection (§3) assigns it; `Kind.UNKNOWN` is a legitimate,
  honest value that routes to "we're not sure → here are options" (P3c), never a crash.
- **`source` carries provenance, not bytes** ([[selom-figure-editor-architecture]] / I5
  discipline): a `DataBundle` is reconstructable from the original file, it is not the file.

## 3. Modality taxonomy (`Kind`) + detection

The small, closed set the router (P3) and skills key on. Start deliberately narrow; extend
per real data, never speculatively.

| `Kind` | Shape signature | Example real dataset |
|---|---|---|
| `SC_COUNTS` | AnnData / 10x-mtx, integer X, obs×var | GSE201356, RPGRIP1 scRNA |
| `BULK_COUNTS` | genes×samples integer matrix + a design | ALPK1, EYG_08 raw counts |
| `DE_RESULTS` | per-gene `logFC` + `p`/`padj` columns (no raw counts) | EYG_28 bulk DE-results |
| `PROTEOMICS` | proteins×samples intensities (MNAR missing) | Fidelle mouse proteomics |
| `METABOLOMICS` | features×samples intensities (pre-annotation) | (whitespace, no dataset yet) |
| `GENERIC_TABLE` | a table we can read but not yet classify | supplement sheets |
| `UNKNOWN` | nothing matched | — |

Detection is a **layered classifier** ([[layered-deterministic-extraction]]): L1 structured
(file extension + AnnData/10x markers + exact column signatures) · L2 recovery (sniff column
names: `log2FoldChange|padj` → `DE_RESULTS`; all-integer dense → counts; many-NaN intensity →
proteomics) · L3 fall through to `GENERIC_TABLE` (still usable) · L4 the Pro-AI classifier
(optional, never required). `kind` therefore degrades gracefully; it never blocks ingest.

## 4. The ingest registry

```python
# app/backend/engine/ingest.py
def ingest(src: PathOrBytes, *, hint: Kind | None = None) -> DataBundle: ...
```

A registry of **one loader per input type**, each `recognize(src) -> bool` + `load(src) ->
DataBundle`: `.h5ad` (anndata) · 10x-mtx dir · `.csv`/`.tsv` (pandas) · `.xlsx` sheet
(openpyxl) · ShinyCell export ([[selom-rpgrip1-real-data]] converter) · paper-supplement
table (subsumes `extract/ingest.py`'s `find_table`). New input types = new registry entries,
never edits to callers. `ingest` picks the first recognizer, loads, classifies (§3), and runs
QC (§5).

**This subsumes, not duplicates, `extract/ingest.py`.** `PaperBundle` becomes *paper text +
a list of `DataBundle`s* (1b): the paper PDF still yields `.text`/`.tables` for routing, and
each supplement sheet becomes a `DataBundle` — so reproduction's data-matching (P2/2d) joins
`DataBundle`s, identical to Product A.

## 5. "Is-my-data-clean?" (`QCReport`) — the native moat

```python
@dataclass
class QCReport:
    ok:     bool                 # safe to analyze with no caveats
    flags:  list[QCFlag]         # each: severity (info|warn|block) + human message + fix hint
    stats:  dict                 # n_cells/genes, % mito, % missing, library-size dist, …
```

Honest, modality-aware flags — the layer that earns "for non-bioinformaticians":
non-integer values where counts are required · NaN/missing fraction · degenerate shape
(1 sample, 0 genes) · **batch ≈ condition confound** ([[selom-scrna-batch-genotype-confound]])
· proteomics all-missing rows · all-zero features. `severity=block` stops a misleading
analysis with a fix hint; `warn`/`info` annotate but proceed. Reuses the adaptive-MAD / doublet
machinery already in `normalization_qc`; this packages it as a *verdict the user reads*, not a
silent filter (no silent caps — the reproduction L4 invariant, generalized).

## 6. The spine contract (the package boundary)

A new **`app/backend/engine/`** package holds the product-agnostic stages; reproduction and
the own-data workbench become **consumers**, not owners:

| Stage | Engine surface | Built? |
|---|---|---|
| INGEST | `engine/ingest.py` `ingest()` → `DataBundle` | **new (P1)** |
| classify / QC | `engine/databundle.py` `classify()` + `engine/qc.py` `run_qc()` | **new (P1)** |
| ROUTE | `engine/route.py` — wraps `extract/routing` (paper) **+** new raw-data router (P3a) | partial |
| JOIN / MATCH | `engine/match.py` — `DataBundle`↔skill matching + ledger merge (lift from `reproduction_drive`) | partial |
| ANALYZE | `run_skill(skill_id, DataBundle, params)` → `{figure, table}` (adds a `DataBundle` entry to the existing runner) | mostly |
| READ-BACK | `extract/readers.py` (L1/L2) + `extract/synthesize.py` (L3, P2) | partial |
| GRADE | `reproduction.py` (consumer-only; **Product B**) | done (floor) |
| OUTPUT | figure editor + L3 table + lit-synth methods | mostly |

Reproduction's `reproduce()` then reads as: `ingest → route → match → analyze → read-back →
grade` — i.e. it *calls the spine* and adds only the grade step. Product A calls
`ingest → (qc gate) → route → analyze → output` — the same spine, minus grading.

## 7. Invariants

- **E1 — One representation.** Every input becomes a `DataBundle` before any analysis. No skill
  re-sniffs a raw path on the product path.
- **E2 — `kind` never blocks.** Unknown modality is honest (`UNKNOWN`/`GENERIC_TABLE`) and routes
  to options, never a crash.
- **E3 — QC is a verdict, not a silent filter.** Cleaning the user can see and override; `block`
  stops a misleading run with a fix hint. (Generalizes the reproduction "no silent caps" rule.)
- **E4 — Additive (D7).** `DataBundle`-aware entries are added alongside path-based ones; existing
  skill outputs stay byte-identical until a caller opts in.
- **E5 — Both products call the same spine.** Reproduction = spine + grade; own-data = spine − grade.
  No reproduction-only fork of ingest/route/analyze.

## 8. Decisions to confirm (owner)

- **D-e1 — `payload` shape.** *Recommended:* `DataBundle` **wraps** the native loaded object
  (AnnData stays AnnData, tables stay DataFrames) + carries metadata — we do **not** coerce
  everything into one frame (that would lose scRNA structure). Confirm wrap-don't-coerce.
- **D-e2 — Package location.** *Recommended:* a new `app/backend/engine/` package (clean spine
  boundary), with `extract/` and `reproduction*.py` becoming consumers over time. *Alternative:*
  grow `extract/` in place (less moving, muddier boundary). Confirm new-package.
- **D-e3 — Refactor posture.** *Recommended:* **strangler, not big-bang** — add `DataBundle` +
  `ingest()` + QC first (net-new, zero regression), then migrate one consumer (the own-data
  workbench) onto it, then fold reproduction's `data_map`/merge into `engine/match.py`. Each its
  own scoped commit; the 4 ledgers + golden+registry suites guard every step. Confirm.
- **D-e4 — First `Kind` set.** *Recommended:* ship the 7 in §3 (the modalities we have real data
  for + `GENERIC_TABLE`/`UNKNOWN`); add `METABOLOMICS` detection now even though the skill is
  parked, so P3 can already route to "coming soon". Confirm the set.
- **D-e5 — QC `block` authority.** *Recommended:* `block` flags **warn + require an explicit
  override** rather than hard-refuse (the user owns their data). Confirm warn-and-override vs
  hard-block.

## 9. Build plan (phased — each its own scoped commit, gated)

1. **`DataBundle` + classify** — `engine/databundle.py` (model + `Kind` + the layered classifier),
   unit-tested against the real staged datasets ([[selom-real-datasets]]) so each known dataset
   classifies correctly.
2. **Ingest registry** — `engine/ingest.py` with the loaders, `ingest()` returning a classified
   `DataBundle`; subsume `extract/ingest.py`'s table-finding without breaking reproduction.
3. **QC** — `engine/qc.py` `run_qc()` + `QCReport`, modality-aware flags, reusing `normalization_qc`;
   verified on a clean dataset (ok) and a deliberately-broken one (block + fix hint).
4. **One consumer migrates** — point the own-data workbench (or a thin `POST /data/inspect`) at
   `ingest` → show the `QCReport`; proves Product A has a front door.
5. **Fold reproduction** — `reproduce()` ingests via the registry; `data_map`/merge move to
   `engine/match.py`; re-verify all 4 ledgers' scorecards unchanged (the regression guard, P5c).

**No new infra.** Pure library + the existing inline path; ASK before any Redis/arq/Docker
([[ask-before-docker-wsl]]).
