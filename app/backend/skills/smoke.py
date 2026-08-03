"""Skill smoke matrix — the evidence behind "are all the skills working?".

Nothing in this repo could answer that question, so it got answered from impression. This module
is the answer: one declared case per registered skill, run against the **real** corpus
(``SELOM_DATASETS_DIR``), recording pass / fail / explicitly-skipped-with-a-reason plus runtime.

**Why it is not the golden test.** ``tests/test_skills_golden.py`` pins every skill's *stub* to a
committed snapshot — it proves the wire shape is stable with zero heavy deps, and by construction
says nothing about whether the real engine runs. This is its complement: the REAL engine, on REAL
data, with the honesty checks that a stub-shaped pass cannot give you.

**The honesty rules** (a smoke matrix that lies is worse than none):

* The run **refuses to start** unless ``SELOM_SKILLS_ENGINE=real`` + ``SELOM_UMAP_ENGINE=scanpy``
  are already pinned (:func:`pin_process`). Under the default ``auto`` a missing dep makes a skill
  silently return a fabricated stub figure (RISKS #11) — which would be recorded here as a pass.
  Pinned-real turns that into an honest ImportError instead.
* A figure whose title still says ``(stub)`` is a **failure**, not a pass — it catches an engine
  that fell back internally rather than through the ``_engine`` gate.
* A skill that cannot be smoked on the available corpus is an explicit :class:`Skip` **with a
  reason**, never a missing row: a silent skip reads as a pass.
* Every id in ``registry.list_skill_ids()`` must have an entry. A new skill with no case fails the
  ratchet (``tests/test_skill_smoke.py``) rather than quietly reducing coverage.

Run it: ``scripts/skill-smoke.sh`` (exit-code gated; writes ``docs/skill-coverage/matrix.md``).
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import time

# ---------------------------------------------------------------- statuses
PASS = "pass"
FAIL = "fail"
SKIP = "skip"          # declared: this skill CANNOT be smoked on this corpus, with a reason
NOT_RUN = "not_run"    # environmental: the corpus (or a file in it) is absent right now


@dataclasses.dataclass(frozen=True)
class Case:
    """One smokable skill: a real corpus file (path relative to ``SELOM_DATASETS_DIR``) + the
    params that make the real engine do genuine work on it. ``note`` says why this pairing is the
    honest one (which is the part a reader cannot re-derive).

    ``adapter`` names a declared, in-repo conversion applied to the corpus file first — the same
    conversion Selom's own ingest does (``engine.ingest`` reads a Diagnosys ``.TXT`` through
    ``skills._celeris``). It is recorded in the matrix so nobody mistakes an adapted input for a
    file that dropped straight in. ``requires`` lists backend-relative build artefacts the real
    engine needs on disk; a missing one is reported as NOT-RUN with the reason, never as a pass.
    """

    dataset: str
    params: dict
    note: str = ""
    adapter: str = ""
    requires: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Skip:
    """A skill that cannot be smoked here. ``reason`` is mandatory and is what gets published in
    the matrix — "skipped" with no reason is indistinguishable from "forgotten"."""

    reason: str


@dataclasses.dataclass
class Result:
    skill_id: str
    status: str
    seconds: float = 0.0
    dataset: str = ""
    detail: str = ""

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------- the matrix
# Dataset choices favour the SMALLEST real file that exercises the engine honestly — a 36-skill
# matrix is the heaviest job this box runs, and a 1.2 GB h5ad buys no extra truth over a 10 k-cell
# one. Two scRNA anchors do most of the work:
#   jev/retina_fadl.h5ad          8,699 x 18,223, ALREADY log-normalized, carries `leiden` + X_umap
#   hani/.../hani_irpe_subset.h5ad 10,000 x 64,591, RAW counts, carries `sample`/`batch` (4 batches)
# so `normalize` is set per file, not copy-pasted: the JEV matrix must NOT be normalized again.
JEV_SCRNA = "jev/retina_fadl.h5ad"
HANI_SCRNA = "hani/processed/hani_irpe_subset.h5ad"
RPGRIP1_SCRNA = "rpgrip1/processed/rpgrip1_merged.h5ad"
JEV_PROTEOME = "jev/proteome_matrix.csv"          # Protein x (DR1-5, PD1-5) log-intensity
JEV_PROTEOME_DE = "jev/proteome_de.csv"           # gene / logFC / P.Value / adj.P.Val
# The gene-set skills need a HUMAN symbol ranking: every license-clean library Selom ships (GO,
# WikiPathways, the curated panels) is human-symbol keyed, so the mouse JEV proteome overlaps almost
# nothing and gseapy legitimately refuses. These two are the human ALPK1 iRPE pair.
HUMAN_DE = "alpk1/irpe_rawcounts/DE_oracle_d311_limma.csv"        # limma oracle, ~21 k human genes
HUMAN_COUNTS = "alpk1/eyg29/EYG_29_iRPE_human_St7-TMM-K0_rawCounts.csv"  # symbols x 18 samples
ERG_WAVEFORMS = "erg-fig1e/erg_waveforms_long.csv"
ERG_METRICS = "erg-fig1e/erg_metrics_long.csv"

CASES: dict[str, Case | Skip] = {
    # ---- scRNA, on the already-log-normalized JEV retina matrix (leiden + X_umap present) -----
    "annotate": Case(JEV_SCRNA, {"groupby": "leiden", "embedding": "X_umap", "normalize": False},
                     "scores the retinal marker panel per stored leiden cluster"),
    "cepo": Case(JEV_SCRNA, {"group_key": "leiden", "n_genes": 4, "normalize": False},
                 "differential-stability markers over the stored clusters"),
    "cluster": Case(JEV_SCRNA, {"resolution": 1.0, "n_pcs": 20, "normalize": False},
                    "recomputes Leiden from scratch (PCA -> kNN -> leiden)"),
    "deg": Case(JEV_SCRNA, {"groupby": "leiden", "method": "wilcoxon", "top_n": 10,
                            "normalize": False},
                "scRNA mode: rank_genes_groups across the stored clusters"),
    "heatmap": Case(JEV_SCRNA, {"groupby": "leiden", "n_genes": 5},
                    "per-cluster marker heatmap, z-scored per gene"),
    "markers": Case(JEV_SCRNA, {"groupby": "leiden", "n_genes": 3, "normalize": False},
                    "dendrogram-ordered marker dotplot"),
    "pseudotime_genes": Case(JEV_SCRNA, {"groupby": "leiden", "top_n": 6, "normalize": False},
                             "DPT + Spearman gene-vs-pseudotime trends"),
    "trajectory": Case(JEV_SCRNA, {"groupby": "leiden", "embedding": "X_umap", "normalize": False},
                       "diffusion map -> PAGA -> DPT over the stored embedding"),
    "umap_scrna": Case(JEV_SCRNA, {"n_pcs": 20, "n_neighbors": 15, "color_by": "leiden",
                                   "normalize": False},
                       "the FULL scanpy pipeline (PCA -> kNN -> leiden -> UMAP), not the "
                       "stored-embedding fast path — the stub-vs-real question is about this path"),
    "violin": Case(JEV_SCRNA, {"groupby": "leiden", "normalize": False},
                   "auto-picked marker gene, one violin per cluster"),

    # ---- scRNA, on the RAW-count Hani iRPE matrix (4 batches -> the batch-aware skills) -------
    "integration": Case(HANI_SCRNA, {"batch_key": "sample", "n_pcs": 20, "n_hvg": 2000},
                        "Melody batch correction across the 4 iRPE batches (raw counts, so "
                        "normalize stays on)"),
    "mixing_metrics": Case(HANI_SCRNA, {"batch_key": "sample", "n_pcs": 20, "n_neighbors": 20},
                           "LISI/kBET-style mixing over the same 4 batches"),
    "normalization_qc": Case(HANI_SCRNA, {"groupby": "sample", "max_cells": 3000},
                             "per-cell QC needs RAW counts — the JEV matrix is already logged"),
    "diff_abundance": Case(RPGRIP1_SCRNA,
                           {"sample_col": "sample", "condition_col": "genotype",
                            "label_col": "celltypes", "reference": "WT", "treatment": "C3",
                            "min_cells": 10},
                           "the only corpus matrix carrying sample + condition + cell-type "
                           "labels together (9 samples, WT/C3/PT/FS) — 1.2 GB, the slowest row"),

    # ---- bulk / tabular ----------------------------------------------------------------------
    "volcano": Case(JEV_PROTEOME_DE, {"fc_threshold": 1.0, "fdr_threshold": 0.05, "top_n": 10},
                    "deposited limma EV-proteome DE table (JEV Table S6)"),
    "proteomics_de": Case(JEV_PROTEOME, {"group_a": "DR", "group_b": "PD", "log_input": True},
                          "log-intensity matrix, dim-reared vs photoreceptor-degeneration"),
    "pca": Case(JEV_PROTEOME, {"scale": True, "label_points": True},
                "samples x proteins PCA; groups inferred from the DR#/PD# sample names"),
    "corr_heatmap": Case(JEV_PROTEOME, {"axis": "samples", "method": "pearson", "cluster": True},
                         "sample-sample correlation, hierarchically reordered"),
    "ssgsea": Case(HUMAN_COUNTS, {"gene_sets": "all", "top_n": 15, "min_size": 5},
                   "per-sample enrichment across every library source at once (GO + WikiPathways "
                   "+ the curated panels)"),
    "gsea": Case(HUMAN_DE, {"gene_sets": "all", "n_perm": 200},
                 "pre-ranked GSEA on the deposited limma logFC ranking"),
    "enrichment": Case(HUMAN_DE, {"top_n": 10, "fdr_threshold": 0.05},
                       "hypergeometric ORA on the significant rows of the DE table"),
    "go_graph": Case(HUMAN_DE, {"top_n": 15, "fdr_threshold": 0.05},
                     "ORA drawn in the GO is_a/part_of hierarchy",
                     requires=("skills/go_graph/go_dag.json",)),
    "composition": Case("jev/deconvolution.csv", {"mode": "grouped", "orientation": "h"},
                        "published retinal cell-type deconvolution, DR vs PD"),
    "boxplot": Case(ERG_METRICS, {"group": "condition", "value": "b_wave_uv"},
                    "b-wave amplitude distribution per treatment arm"),
    "regression": Case(ERG_METRICS, {"x": "a_wave_uv", "y": "b_wave_uv"},
                       "a-wave vs b-wave OLS across every recorded eye x intensity"),
    "scorecard": Case("hani/hani_benchmark.csv", {"layout": "radar", "normalize": True},
                      "protocol x metric benchmark table"),
    "sankey": Case("hani/mmc2_markers_long.csv", {"max_links": 40},
                   "marker -> cell-type edge table (gene, cell_type) counted per pair"),
    "pvca": Case(ERG_METRICS, {"factors": "condition,eye,intensity_group", "pct_threshold": 0.6},
                 "apportions ERG metric variance across treatment / eye / flash intensity"),
    "upset": Case("hani/mmc2_markers_long.csv", {"mode": "distinct", "min_size": 1},
                  "marker-per-cell-type long table pivoted to the membership matrix the engine "
                  "documents ('top markers per cell type')", adapter="membership"),
    # venn shares upset's input EXACTLY (same adapter, same file) — the two are the small-n and
    # large-n views of one question, so smoking them on one table is what proves that claim.
    # The corpus table has more cell types than a Venn can draw, which exercises the "3 largest
    # of N" selection path rather than the trivial already-3-columns one.
    "venn": Case("hani/mmc2_markers_long.csv", {}, adapter="membership",
                 note="the same marker membership matrix upset smokes on — >3 sets, so the "
                      "largest-three selection + its title note are exercised"),
    "forest": Case(HUMAN_DE, {"top_n": 12, "sort_by": "significance"},
                   "limma oracle table: no CI columns and no stderr, so this smokes the "
                   "t-statistic derivation path (se = logFC / t) — the one that would silently "
                   "fabricate intervals if it were wrong"),
    "qq": Case(HUMAN_DE, {"top_n": 10},
               "~21 k human genes with a raw P.Value column — exercises λ, the Beta null band "
               "and the tail-preserving thinning at real scale"),

    # ---- ERG (proprietary) -------------------------------------------------------------------
    "erg_traces": Case(ERG_WAVEFORMS, {"role": "representative", "marks": True},
                       "rd10 AAV Fig-1E waveforms, 6 arms x 5 flash intensities"),
    "erg_bwave_bar": Case(ERG_METRICS, {"wave": "b", "intensity_group": "Group4"},
                          "device-marker b-wave amplitudes at one flash step"),
    "erg_intensity_response": Case(ERG_METRICS, {"value_col": "b_wave_uv", "fit": True},
                                   "Naka-Rushton fit per condition across the intensity ladder"),
    "erg_flicker": Case("diagnosys-erg/full-txt-exp8/"
                        "453_AAV_C1 - Long RK-PROM1-3’UTR-BPolyA_10+E9.TXT",
                        {"view": "waveform"},
                        "the only REAL flicker recording in the corpus (LA 10/30 Hz steps of a "
                        "Diagnosys Espion export)", adapter="celeris"),

    # ---- live-API skills ---------------------------------------------------------------------
    "pathway": Case(HUMAN_DE, {"top_n": 12, "fdr_threshold": 0.05},
                    "live Reactome over-representation (network-dependent by design)"),
    "string_network": Case(HUMAN_DE, {"max_genes": 30, "fdr_threshold": 0.05},
                           "live STRING PPI network (network-dependent by design)"),

    # ---- declared skips ----------------------------------------------------------------------
    "facs_gating": Skip(
        "no .fcs file exists anywhere in SELOM_DATASETS_DIR — the flow-cytometry engine "
        "(FlowIO/FlowUtils) parses FCS binaries and nothing else, so there is no honest real-data "
        "input to give it. Already recorded as a corpus gap in tests/test_flow_gating_honesty.py; "
        "unblocked the day a real .fcs is staged."),
}


def _corpus() -> pathlib.Path | None:
    from config import datasets_dir  # the ONE typed env home (structure guard M-002)

    return datasets_dir()


# The selectors the caller must export before smoking. They are NOT set here on purpose: env
# selection belongs to config.Settings (structure guard M-002), and a library that rewrites the
# process environment behind its caller's back is worse than one that refuses to run unpinned.
# `scripts/skill-smoke.sh` exports them; the pytest lane sets them in the test.
REQUIRED_ENV = {"SELOM_SKILLS_ENGINE": "real", "SELOM_UMAP_ENGINE": "scanpy"}


def pin_process() -> None:
    """Make this process safe to smoke in, or refuse. Two distinct lies are shut off:

    * **stub figures** — the engine selectors must already be pinned to the real engines, so a
      missing dep raises instead of returning a fabricated figure. Verified, not set: see
      :data:`REQUIRED_ENV`.
    * **cached figures** — the C1 result cache and C3 input cache are swapped for disabled ones
      in-process. A cache hit returns an earlier run's figure without executing the engine at all,
      which would turn a broken skill green in 0.00 s. Same reason ``tests/conftest.py`` disables
      them suite-wide.
    """
    import tempfile

    import engine
    from config import settings
    from skills import _engine, _result_cache

    unpinned = []
    if _engine.resolve_engine_policy() != "real":
        unpinned.append("SELOM_SKILLS_ENGINE=real")
    if settings.umap_engine().lower() not in ("scanpy", "real"):
        unpinned.append("SELOM_UMAP_ENGINE=scanpy")
    if unpinned:
        raise RuntimeError(
            "skill smoke refuses to run unpinned — every row could be a fabricated stub figure "
            f"wearing a PASS. Export {' '.join(unpinned)} first (scripts/skill-smoke.sh does)."
        )

    _result_cache.set_cache(
        _result_cache.ResultCache(root=tempfile.gettempdir(), mem_max=0, enabled=False)
    )
    settings.input_cache = "off"
    engine.clear_input_cache()


def _title(figure: dict) -> str:
    layout = figure.get("layout") if isinstance(figure, dict) else None
    title = (layout or {}).get("title")
    if isinstance(title, dict):
        return str(title.get("text", ""))
    return str(title or "")


def _axis_key(letter: str, anchor) -> str:
    """``('x', 'x2') -> 'xaxis2'`` — the layout key for the axis a trace is drawn against."""
    suffix = str(anchor or letter)[1:]
    return f"{letter}axis{suffix}"


def _numeric_string_axes(figure) -> list[str]:
    """Axes whose category values are numbers written as STRINGS but which do not declare
    ``type: "category"`` — the D2 defect, reported per axis.

    Plotly infers the axis type from the values it is given. Handed ``["0", "1", "10"]`` it decides
    the axis is LINEAR and lays the points out at their numeric values instead of at consecutive
    category slots, which silently mislays and reorders whole columns (parity-audit D2). Cluster
    ids reach a figure as strings on every scRNA path (``adata.obs[key].astype(str)``), so this is
    a class of bug, not one skill's.
    """
    layout = figure.get("layout") or {}
    offenders = []
    for trace in figure.get("data") or []:
        if not isinstance(trace, dict):
            continue
        for letter in ("x", "y"):
            values = trace.get(letter)
            if not isinstance(values, list):
                continue
            present = [v for v in values if v is not None]
            if not present or not all(isinstance(v, str) for v in present):
                continue
            try:
                [int(v) for v in present]
            except ValueError:
                continue  # ordinary text categories — Plotly cannot mistake those for a scale
            key = _axis_key(letter, trace.get(f"{letter}axis"))
            axis = layout.get(key) or {}
            if axis.get("type") != "category" and key not in offenders:
                offenders.append(key)
    return offenders


def check_figure(figure) -> str:
    """Validate one skill's output. Returns "" when it is a genuine editable figure, else the
    reason it is not. Mirrors the golden test's shape assertions plus the stub-leak check."""
    if not isinstance(figure, dict):
        return f"not a figure dict (got {type(figure).__name__})"
    data = figure.get("data")
    if not isinstance(data, list) or not data:
        return "empty `data` — the figure has no traces"
    if not isinstance(figure.get("layout"), dict):
        return "missing `layout`"
    try:
        if json.loads(json.dumps(figure)) != figure:
            return "figure does not round-trip through JSON (numpy / typed-array leakage)"
    except (TypeError, ValueError) as exc:
        return f"figure is not JSON-serialisable: {exc}"
    if "stub" in _title(figure).lower():
        return f"real engine fell back to the STUB (title: {_title(figure)!r})"
    bad_axes = _numeric_string_axes(figure)
    if bad_axes:
        return (
            f"{', '.join(bad_axes)} carries numeric-looking STRING categories without "
            'type: "category" — Plotly will infer a LINEAR axis and lay the categories out at '
            "their numeric values, reordering and mislaying them (parity-audit D2)"
        )
    return ""


BACKEND = pathlib.Path(__file__).resolve().parent.parent

# What to do when a `requires` artefact is missing — the fix, not just the fact.
ARTIFACT_FIX = {
    "skills/go_graph/go_dag.json":
        "gitignored GO-DAG build artefact. Install the staged copy with "
        "`scripts/skill-smoke.sh --install-artifacts`, or rebuild it with "
        "`uv run --with obonet python scripts/build_gene_sets.py` (network + obonet).",
}


def _adapt(kind: str, path: pathlib.Path, tmpdir: str) -> pathlib.Path:
    """Apply a declared adapter, returning the path the skill actually reads.

    ``celeris``    — Diagnosys Espion ``.TXT`` -> the canonical ``erg_waveforms_long`` CSV, via the
                     same ``skills._celeris`` reader ``engine.ingest`` uses for this format.
    ``membership`` — a long ``(element, set)`` table -> the wide boolean membership matrix the
                     UpSet engine documents as its input ("top markers per cell type").
    """
    import pandas as pd

    out = pathlib.Path(tmpdir) / f"{path.stem}.{kind}.csv"
    if kind == "celeris":
        from skills._celeris import read_celeris

        read_celeris(str(path)).to_csv(out, index=False)
    elif kind == "membership":
        df = pd.read_csv(path)
        element, group = df.columns[0], df.columns[1]
        pd.crosstab(df[element], df[group]).gt(0).to_csv(out)
    else:
        raise ValueError(f"unknown adapter {kind!r}")
    return out


def run_one(skill_id: str, entry: Case | Skip | None = None) -> Result:
    """Smoke one skill. Never raises — a broken skill is data, not a crash."""
    import tempfile

    from skills.contract import run_skill

    entry = CASES.get(skill_id) if entry is None else entry
    if entry is None:
        return Result(skill_id, FAIL, detail="no smoke case declared for this skill")
    if isinstance(entry, Skip):
        return Result(skill_id, SKIP, detail=entry.reason)

    corpus = _corpus()
    if corpus is None:
        return Result(skill_id, NOT_RUN, dataset=entry.dataset,
                      detail="SELOM_DATASETS_DIR is unset — no real corpus to run against")
    path = corpus / entry.dataset
    if not path.exists():
        return Result(skill_id, NOT_RUN, dataset=entry.dataset,
                      detail=f"corpus file absent: {path}")
    for artefact in entry.requires:
        if not (BACKEND / artefact).exists():
            return Result(skill_id, NOT_RUN, dataset=entry.dataset,
                          detail=f"missing {artefact} — {ARTIFACT_FIX.get(artefact, 'not built')}")

    with tempfile.TemporaryDirectory(prefix="selom-smoke-") as tmpdir:
        if entry.adapter:
            try:
                path = _adapt(entry.adapter, path, tmpdir)
            except Exception as exc:  # noqa: BLE001
                return Result(skill_id, FAIL, dataset=entry.dataset,
                              detail=f"adapter {entry.adapter!r} failed — "
                                     f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300])
        return _time_run(run_skill, skill_id, path, entry)


def _time_run(run_skill, skill_id: str, path: pathlib.Path, entry: Case) -> Result:
    start = time.perf_counter()
    try:
        figure = run_skill(skill_id, str(path), dict(entry.params))
    except Exception as exc:  # noqa: BLE001 — every failure mode is a matrix row, not a traceback
        return Result(skill_id, FAIL, round(time.perf_counter() - start, 2), entry.dataset,
                      f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300])
    seconds = round(time.perf_counter() - start, 2)
    problem = check_figure(figure)
    if problem:
        return Result(skill_id, FAIL, seconds, entry.dataset, problem)
    return Result(skill_id, PASS, seconds, entry.dataset,
                  f"{len(figure['data'])} traces · {_title(figure)[:60]}")


def skill_ids() -> list[str]:
    """The roster the matrix must cover — the registry, not a hand-kept list."""
    from skills.registry import list_skill_ids

    return list_skill_ids()


def run_matrix(only: list[str] | None = None) -> list[Result]:
    """Smoke every registered skill, in registry order. Serial on purpose: three lanes share
    6 vCPU and the scRNA engines are already multi-threaded internally."""
    pin_process()
    ids = only or skill_ids()
    return [run_one(sid) for sid in ids]


# ---------------------------------------------------------------- the committed matrix
ROOT = BACKEND.parent.parent
DOCS = ROOT / "docs" / "skill-coverage"
MATRIX_JSON = DOCS / "matrix.json"
MATRIX_MD = DOCS / "matrix.md"


def load_matrix() -> dict[str, dict]:
    """The committed matrix, ``{skill_id: row}``. Empty when it has never been generated."""
    if not MATRIX_JSON.exists():
        return {}
    return {r["skill_id"]: r for r in json.loads(MATRIX_JSON.read_text(encoding="utf-8"))["skills"]}


def regressions(results: list[Result], expected: dict[str, dict] | None = None) -> list[str]:
    """What got WORSE against the committed matrix — the thing the gate exits non-zero on.

    A skill recorded as passing that no longer passes is a regression. A skill that was skipped and
    now passes is not (coverage improved — regenerate the matrix). A skill missing from the roster
    entirely is a regression: it means a skill was deleted or renamed without updating the matrix.
    """
    expected = load_matrix() if expected is None else expected
    by_id = {r.skill_id: r for r in results}
    if len(by_id) < len(skill_ids()):
        # A deliberate subset (--only): compare just those rows, or every un-run skill would be
        # reported as a missing row. A FULL run keeps the both-ways roster check.
        expected = {k: v for k, v in expected.items() if k in by_id}
    out = []
    for sid, row in expected.items():
        if sid not in by_id:
            out.append(f"{sid}: in the committed matrix but no longer a registered skill")
        elif row["status"] == PASS and by_id[sid].status != PASS:
            out.append(f"{sid}: committed as PASS, now {by_id[sid].status.upper()} "
                       f"— {by_id[sid].detail}")
    for sid, res in by_id.items():
        if sid not in expected:
            out.append(f"{sid}: registered skill with no row in the committed matrix")
        elif res.status == FAIL and expected[sid]["status"] != PASS:
            out.append(f"{sid}: FAIL — {res.detail}")   # newly failing, and never recorded green
    return out


def _md_row(r: Result) -> str:
    mark = {PASS: "pass", FAIL: "**FAIL**", SKIP: "skip", NOT_RUN: "not run"}[r.status]
    seconds = f"{r.seconds:.2f}" if r.status in (PASS, FAIL) else "—"
    entry = CASES.get(r.skill_id)
    dataset = f"`{r.dataset}`" if r.dataset else "—"
    if isinstance(entry, Case) and entry.adapter:
        dataset += f"<br>*(via the `{entry.adapter}` adapter)*"
    note = entry.note if isinstance(entry, Case) else ""
    detail = r.detail if r.status != PASS else note
    return f"| `{r.skill_id}` | {mark} | {seconds} | {dataset} | {detail.replace('|', '/')} |"


def render_markdown(results: list[Result], *, stamp: str, elapsed: float) -> str:
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, SKIP, NOT_RUN)}
    lines = [
        "# Skill coverage — the smoke matrix",
        "",
        f"**{counts[PASS]} pass · {counts[FAIL]} fail · {counts[SKIP]} skipped (with a reason) · "
        f"{counts[NOT_RUN]} not run** — {len(results)} registered skills, "
        f"{elapsed:.0f}s wall-clock, generated {stamp}.",
        "",
        "Generated by `scripts/skill-smoke.sh` — **do not hand-edit**. Every row ran the REAL "
        "engine (`SELOM_SKILLS_ENGINE=real`) against a real file in `SELOM_DATASETS_DIR`, with the "
        "result caches off. Rationale, method and what the matrix does *not* prove: "
        "[`README.md`](README.md).",
        "",
        "| Skill | Status | Seconds | Real dataset | Case / detail |",
        "|---|---|---:|---|---|",
    ]
    lines += [_md_row(r) for r in results]
    lines.append("")
    return "\n".join(lines)


def write_matrix(results: list[Result], *, stamp: str, elapsed: float) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    payload = {"generated": stamp, "elapsed_seconds": round(elapsed, 1),
               "skills": [r.as_dict() for r in results]}
    MATRIX_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    MATRIX_MD.write_text(render_markdown(results, stamp=stamp, elapsed=elapsed), encoding="utf-8")


# ---------------------------------------------------------------- CLI (scripts/skill-smoke.sh)
def main(argv: list[str] | None = None) -> int:
    """Run the matrix, print it raw, and exit non-zero on any regression. ``--write`` regenerates
    the committed matrix instead of comparing against it."""
    import argparse
    import datetime

    ap = argparse.ArgumentParser(prog="skills.smoke", description="Selom skill smoke matrix")
    ap.add_argument("--write", action="store_true",
                    help="regenerate docs/skill-coverage/matrix.{md,json} from this run")
    ap.add_argument("--only", default="", help="comma-separated skill ids (default: all)")
    args = ap.parse_args(argv)

    only = [s.strip() for s in args.only.split(",") if s.strip()] or None
    start = time.perf_counter()
    results = run_matrix(only)
    elapsed = time.perf_counter() - start

    print(f"\n{'STATUS':9} {'SKILL':24} {'SECONDS':>8}  DETAIL")
    for r in results:
        print(f"{r.status.upper():9} {r.skill_id:24} {r.seconds:8.2f}  {r.detail[:110]}")
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, SKIP, NOT_RUN)}
    print(f"\n{counts[PASS]} pass · {counts[FAIL]} fail · {counts[SKIP]} skipped · "
          f"{counts[NOT_RUN]} not run  ({elapsed:.0f}s)")

    if args.write:
        if only:
            print("[smoke] refusing to --write a PARTIAL run (--only would drop every other "
                  "skill's row, which is exactly the silent-drop this matrix exists to prevent)")
            return 2
        stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
        write_matrix(results, stamp=stamp, elapsed=elapsed)
        print(f"[smoke] wrote {MATRIX_MD.relative_to(ROOT)} + {MATRIX_JSON.relative_to(ROOT)}")
        return 1 if counts[FAIL] else 0

    problems = regressions(results)
    if problems:
        print("\n[smoke] REGRESSIONS vs the committed matrix:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[smoke] no regression against the committed matrix.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
