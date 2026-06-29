"""RPGRIP1 (Loi 2025) — the first REAL reproduction ledger, driven end-to-end through the engine.

This is the first end-to-end integration of the Reproduction Engine (build-plan R0+R1+R2+R3)
on a real paper. It hand-encodes the RPGRIP1 ledger — the structured form of
``docs/records/rpgrip1-figrepro.md`` + ``D:/tmp-thl/rpgrip1_target_spec.md`` (until R4's extraction
subsystem generates it from the PDF) — and drives it through the full loop:
verdict (D4) -> sweep (stage 9) -> oracle (stage 7, gated) -> revalidate -> findings-first
scorecard (D10). It exercises the deterministic core (``reproduction.py``), the blame
instruments (``sweep.py`` / ``oracle.py``), and their glue together on real data.

Two drive modes:

* :func:`drive_captured` — pure-Python, **no heavy deps, no real data**: replays the verified
  dogfood observations (logged in ``D:/tmp-thl/{fig5,fig6}-real/``, sessions 11-12) through the
  engine so the scorecard the engine *produces* is asserted to equal the verdicts reached by
  hand. CI-safe; the regression artifact + the first complete real scorecard.
* :func:`drive_live_fig5` — re-runs the Fig 5 signature-count loop on the real **GSE293982**
  deposit through the actual engine code (``sweep.signature_count`` on Selom's real DE rows ->
  ``sweep_panel`` -> the gated **edgeR oracle** -> ``revalidate_panel``), and checks it matches
  captured. The live proof that run+sweep+oracle+revalidate compose on real data.

ADR 0002: the oracle is validation-only + gated (``SELOM_ORACLE`` off by default) — without it
the blame degrades to ``delta-unmeasured`` honestly, exactly as the product profile does (D9/D12).

Dev/validation entrypoint (not a product endpoint; the engine is library-only, D12):

    # captured drive (anywhere): build the ledger -> scorecard -> save ledger.json
    python -m reproduction_rpgrip1

    # live Fig 5 proof on the real deposit (oracle gated; add --oracle to upgrade blame)
    SELOM_ORACLE=r python -m reproduction_rpgrip1 --live-fig5 --oracle \
        --fig5-dir D:/tmp-thl/fig5-real \
        --counts C:/Temp/selom-geo/GSE293982/GSE293982_dedup_countTable_geneName.tsv.gz
"""

from __future__ import annotations

import pathlib

import reproduction as R
from oracle import OracleUnavailable, run_edger_signature
from reproduction import (
    Golden,
    Inconsistency,
    Ledger,
    MethodSub,
    Panel,
    Paper,
    Sweep,
)
from sweep import signature_set, sweep_panel

PAPER_ID = "rpgrip1"

# --- golden target VALUES (printed in the paper; D:/tmp-thl/rpgrip1_target_spec.md) ----------
# The figures + results text say signature = 78 (methods says 181 — flagged inconsistency);
# 49 down-in-both. Gene magnitudes are normalized-expression % changes vs Control-1.
GOLD_UNIVERSE = 1133            # deterministic RPGRIP1-associated GO union (reproduced exactly)
GOLD_SIGNATURE = 78            # figures/results count (methods 181 -> methods_vs_numbers)
GOLD_SIGNATURE_METHODS = 181
GOLD_DOWN_BOTH = 49            # signature genes down in BOTH LCA-1 & MS-VUS

# --- captured Selom outputs + oracle values (sessions 11-12 dogfood; see the *_oracle.log) ---
# Each value here is a real, logged observation — not a guess. drive_captured replays them
# through the engine; drive_live_fig5 re-derives the Fig 5 ones on the real deposit.
SEL_SIGNATURE = 19            # universe ∩ adj-p<0.05 (MS-VUS) — Selom pyDESeq2 (= edgeR's 19)
SEL_DOWN_BOTH = 13            # down in both at adj-p<0.05 — Selom (= edgeR's 13)
ORA_SIGNATURE_ADJ = 19        # edgeR signature.adj on GSE293982 (edger_oracle.log)
ORA_DOWN_BOTH_ADJ = 13        # edgeR down_both.adj on GSE293982

# Fig 6E enriched-GO-term counts: golden totals 102/119/74 (Rod1/2/3). gseapy.prerank is far
# more conservative than the paper's fgsea (RISKS #10); the fgsea oracle on the SAME Cepo
# rankings recovers comparable totals -> the count gap is an engine-delta, while the 52-term
# shared core is unreachable even with fgsea -> upstream-delta. (fgsea_oracle.log.)
GOLD_ROD2_TERMS = 119
SEL_ROD2_TERMS = 36           # gseapy.prerank, FDR<0.05
ORA_ROD2_TERMS = 95           # fgsea on the identical ranking
GOLD_ALLTHREE_CORE = 52       # terms shared by all three rod subtypes
SEL_ALLTHREE_CORE = 0
ORA_ALLTHREE_CORE = 0         # fgsea also recovers no shared core -> upstream, not engine

TERM_COUNT_TOL = 0.30          # engine-sensitive term counts declare a wide close band (D4)


# --- ledger construction (the structured target spec; R4 will auto-generate this) ------------


def _fig5_panels() -> list[Panel]:
    edger_sub = MethodSub(
        paper_tool="edgeR TMM + glmLRT",
        selom_tool="pyDESeq2 + TMM size factors (Wald)",
        reason="edgeR/LRT not shippable; TMM reuses the shipped deg.run_real path",
        delta_measured="near-exact vs edgeR oracle: signature.adj 19=19, down_both 13=13",
    )
    return [
        # The numeric heart: the signature counts (the paper-irreproducible headline).
        Panel(
            paper_id=PAPER_ID, figure="5", panel="sig", chart_form="count", skill_id="deg",
            data_source="GSE293982 (bulk featureCounts)",
            params={"normalization": "tmm", "reference": "Control1", "treatment": "MSVUS"},
            method_subs=[edger_sub], weight=2.0,  # the figure's central quantitative claim
            golden=[
                Golden(metric="universe", value=GOLD_UNIVERSE, source=R.SOURCE_METHODS,
                       deterministic=True,
                       note="RPGRIP1-associated GO union — reproduced byte-exact"),
                Golden(metric="signature.count", value=GOLD_SIGNATURE, source=R.SOURCE_FIGURE,
                       note=f"figures/results say {GOLD_SIGNATURE}; methods say "
                            f"{GOLD_SIGNATURE_METHODS} (internal inconsistency)"),
                Golden(metric="signature.down_both", value=GOLD_DOWN_BOTH, source=R.SOURCE_FIGURE,
                       note="signature genes down-regulated in BOTH LCA-1 & MS-VUS"),
            ],
        ),
        # 5A/5B: form/claim panels — reproduced visually; no printed number to match.
        Panel(paper_id=PAPER_ID, figure="5", panel="A", chart_form="dotplot", skill_id="gsea",
              data_source="GSE293982", golden=[],
              note="GSEA: retinal/photoreceptor/cilium terms negatively enriched, stronger in "
                   "LCA-1 (MS-VUS alone clears 0 at FDR<0.05) — form+claim, no printed value"),
        Panel(paper_id=PAPER_ID, figure="5", panel="B", chart_form="pca", skill_id="pca",
              data_source="GSE293982", golden=[],
              note="PCA of the 78 signature genes: 3 clusters, MS-VUS separates — form+claim"),
        # 5C: the quantified down-regulation magnitudes (normalized-expression %).
        Panel(
            paper_id=PAPER_ID, figure="5", panel="C", chart_form="heatmap", skill_id="deg",
            data_source="GSE293982", method_subs=[edger_sub],
            golden=[
                Golden(metric="RHO.pct_LCA1", value=-71, unit="%"),
                Golden(metric="RHO.pct_MSVUS", value=-34, unit="%"),
                Golden(metric="PRPH2.pct_LCA1", value=-53, unit="%"),
                Golden(metric="PRPH2.pct_MSVUS", value=-18, unit="%"),
                Golden(metric="RPGR.pct_MSVUS", value=59, unit="%"),
            ],
        ),
        # 5D/5E/5F: wet-lab — not derivable from RNA-seq (guard 7, out-of-scope).
        Panel(paper_id=PAPER_ID, figure="5", panel="D", chart_form="ihc", scope=R.WET_LAB,
              golden=[Golden(metric="PRPH2.ihc", value=1, note="PRPH2 immunostaining")]),
        Panel(paper_id=PAPER_ID, figure="5", panel="E", chart_form="qpcr", scope=R.WET_LAB,
              golden=[Golden(metric="rtqpcr", value=1, note="independent RT-qPCR")]),
        Panel(paper_id=PAPER_ID, figure="5", panel="F", chart_form="imaging", scope=R.WET_LAB,
              golden=[Golden(metric="proteostat", value=1, note="PROTEOSTAT aggresome assay")]),
    ]


def _fig6_panels() -> list[Panel]:
    annot_sub = MethodSub(
        paper_tool="Seurat label-transfer vs Swamy 2021 ref",
        selom_tool="marker-score annotation (scanpy score_genes)",
        reason="Swamy reference expression matrix unavailable",
        delta_measured="recovered 6/7 non-rod types; RGC<->RPE set delta",
    )
    glmpca_sub = MethodSub(
        paper_tool="negative-binomial GLM-PCA (Townes 2019)",
        selom_tool="Harmony batch integration on standard PCA",
        reason="glmpca unavailable; un-integrated PCA is batch-confounded",
        delta_measured="6D direction reproduces post-Harmony; magnitude structurally limited",
    )
    fgsea_sub = MethodSub(
        paper_tool="fgsea (R), ranked by Cepo DS",
        selom_tool="gseapy.prerank over MSigDB C5",
        reason="fgsea is R-only; gseapy is the shipped GSEA engine",
        delta_measured="engine-delta measured vs fgsea oracle on the same ranking (RISKS #10)",
    )
    return [
        Panel(paper_id=PAPER_ID, figure="6", panel="A", chart_form="umap", skill_id="annotate",
              data_source="GSE293984 (scRNA)", method_subs=[annot_sub],
              golden=[Golden(metric="n_cell_types", value=9, source=R.SOURCE_FIGURE,
                             note="9 types; Selom set differs by {RGC missing, RPE appears}")]),
        Panel(paper_id=PAPER_ID, figure="6", panel="C", chart_form="stacked_bar",
              skill_id="composition", data_source="GSE293984", golden=[],
              note="per-sample 9-type composition, rod-dominant (~64.5%); control rows limited "
                   "by the 1-control deposit — form+claim"),
        # 6D: the differentiating finding — batch ≈ genotype (1-control deposit). Structural.
        Panel(
            paper_id=PAPER_ID, figure="6", panel="D", chart_form="stacked_bar",
            skill_id="composition", data_source="GSE293984", method_subs=[glmpca_sub],
            golden=[
                Golden(metric="rod2_fold.LCA1", value=2.0, ints_exact=False,
                       structural_limit=True,
                       note="paper: Rod-2 >=2x in LCA-1 vs Control-1 (continuous fold)"),
                Golden(metric="rod2_fold.MSVUS", value=2.0, ints_exact=False,
                       structural_limit=True,
                       note="paper: Rod-2 >=2x in MS-VUS vs Control-1 (continuous fold)"),
            ],
        ),
        # 6E: the engine-delta vs upstream-delta disambiguation (the mission in one panel).
        Panel(
            paper_id=PAPER_ID, figure="6", panel="E", chart_form="venn", skill_id="gsea",
            data_source="GSE293984", method_subs=[fgsea_sub],
            golden=[
                Golden(metric="rod2_enriched_terms", value=GOLD_ROD2_TERMS,
                       close_tol=TERM_COUNT_TOL,
                       note="enriched GO terms for Rod-2 (engine-sensitive count, RISKS #10)"),
                Golden(metric="allthree_core", value=GOLD_ALLTHREE_CORE,
                       note="GO terms shared by all three rod subtypes (the 52-term core)"),
            ],
        ),
        Panel(paper_id=PAPER_ID, figure="6", panel="F", chart_form="dotplot", skill_id="gsea",
              data_source="GSE293984", method_subs=[fgsea_sub],
              golden=[Golden(metric="functional_groups", value=4,
                             note="Rod-2 GO groups: stress/ROS, proteostasis, mito, lipid; "
                                  "Selom hits 3/4 (proteostasis absent)")]),
        Panel(paper_id=PAPER_ID, figure="6", panel="G", chart_form="box", skill_id="deg",
              data_source="GSE293984",
              golden=[Golden(metric="n_down_genes", value=GOLD_DOWN_BOTH,
                             note="49-down bulk signature scaled across rods; Rod-1 highest")]),
    ]


def build_ledger() -> Ledger:
    """The full RPGRIP1 reproduction ledger (Fig 5 + Fig 6), built from the target spec.

    Pure: no data, no heavy deps. This is the hand-authored structured form of
    ``docs/records/rpgrip1-figrepro.md`` that R4's extraction subsystem will eventually produce
    from the PDF. ``drive_captured`` / ``drive_live_fig5`` add the runs + verdicts."""
    paper = Paper(
        id=PAPER_ID, slug=PAPER_ID,
        title="Connecting cilium, stress response, and proteostasis abnormalities inform variant "
              "and therapy assessment in RPGRIP1 retinal organoids",
        doi="10.1016/j.stemcr.2025.102717",
        pmid="41270749",
        # Structured metadata (our extractor's chain → CrossRef; the main PDF isn't staged here).
        authors=["To Ha Loi", "Anson Cheng", "Hani Jieun Kim", "Milan Fernando",
                 "Benjamin M. Nash", "Nader Aryamanesh", "John R. Grigg", "Pengyi Yang",
                 "Anai Gonzalez-Cordero", "Robyn V. Jamieson"],
        venue="Stem Cell Reports", year=2025, volume="20", issue="12", pages="102717",
        geo=["GSE293982", "GSE293984"],
        methods_digest={
            "bulk_de": "featureCounts -> edgeR TMM -> CPM<2 filter -> 3-group NB-GLM -> "
                       "glmLRT -> BH adj-p<0.05 (Control-1/MS-VUS/LCA-1)",
            "signature": "MSigDB C5 sets with RPGRIP1 & EYE/RETINAL/CILIUM/PHOTORECEPTOR & "
                         "size>10 -> union (=1,133) ∩ DE(Control-1 vs MS-VUS)",
            "gsea": "fgsea ranked by DS (sc) or logFC (bulk), MSigDB sets, BH adj-p<0.05",
            "scrna": "emptyDrops -> QC -> DoubletFinder -> Seurat label-transfer (Swamy 2021) "
                     "-> rods GLM-PCA -> Louvain -> Cepo-hclust k=3",
        },
    )
    return Ledger(paper=paper, panels=[*_fig5_panels(), *_fig6_panels()])


# --- captured drive (CI-safe: replay the verified dogfood through the engine) ----------------


def _edger_oracle(oracle_value, golden, computed) -> R.OracleResult:
    """edgeR on the deposited raw data (DEPOSITED_RAW): a miss vs golden -> the paper itself
    is irreproducible. Built via the engine's own agreement helper, not a second heuristic."""
    from oracle import build_oracle_result

    return build_oracle_result("edgeR", R.DEPOSITED_RAW, oracle_value, golden, computed,
                               version="4.10.1", note="GSE293982, adj-p<0.05 (edger_oracle.log)")


def _fgsea_oracle(oracle_value, golden, computed) -> R.OracleResult:
    """fgsea on Selom's intermediate ranking (SELOM_INTERMEDIATE): agrees with the paper but
    not Selom -> engine-delta; agrees with neither -> upstream-delta. Wide band for counts."""
    from oracle import build_oracle_result

    return build_oracle_result("fgsea", R.SELOM_INTERMEDIATE, oracle_value, golden, computed,
                               close_tol=TERM_COUNT_TOL, version="1.38.0",
                               note="same Cepo ranking (fgsea_oracle.log)")


def _captured() -> dict[str, dict]:
    """Per-panel ``{computed, oracles}`` — the real, logged session-11/12 observations.

    ``computed`` maps each golden metric to Selom's value; ``oracles`` maps the metrics whose
    blame an oracle disambiguates to the :class:`OracleResult`. Metrics with no entry are
    matched (exact/close) or degrade to ``delta-unmeasured`` (no oracle) — both honest."""
    return {
        "5sig": {
            "computed": {
                "universe": GOLD_UNIVERSE,             # deterministic — exact
                "signature.count": SEL_SIGNATURE,      # 19 vs printed 78 — fail
                "signature.down_both": SEL_DOWN_BOTH,  # 13 vs printed 49 — fail
            },
            "oracles": {
                "signature.count": _edger_oracle(ORA_SIGNATURE_ADJ, GOLD_SIGNATURE, SEL_SIGNATURE),
                "signature.down_both": _edger_oracle(ORA_DOWN_BOTH_ADJ, GOLD_DOWN_BOTH,
                                                     SEL_DOWN_BOTH),
            },
        },
        "5C": {"computed": {  # all within 1-4 points -> close (R->Python residual, unmeasured)
            "RHO.pct_LCA1": -73, "RHO.pct_MSVUS": -35,
            "PRPH2.pct_LCA1": -57, "PRPH2.pct_MSVUS": -20, "RPGR.pct_MSVUS": 56.5,
        }},
        "6A": {"computed": {"n_cell_types": 9}},       # count exact; identity set delta noted
        "6D": {"computed": {"rod2_fold.LCA1": 1.8, "rod2_fold.MSVUS": 1.1}},  # structural
        "6E": {
            "computed": {"rod2_enriched_terms": SEL_ROD2_TERMS, "allthree_core": SEL_ALLTHREE_CORE},
            "oracles": {
                "rod2_enriched_terms": _fgsea_oracle(ORA_ROD2_TERMS, GOLD_ROD2_TERMS,
                                                     SEL_ROD2_TERMS),     # -> engine-delta
                "allthree_core": _fgsea_oracle(ORA_ALLTHREE_CORE, GOLD_ALLTHREE_CORE,
                                               SEL_ALLTHREE_CORE),       # -> upstream-delta
            },
        },
        "6F": {"computed": {"functional_groups": 3}},  # 3/4 -> close
        "6G": {"computed": {"n_down_genes": 50}},      # ~49 -> close
        # wet-lab panels: not computed (None) -> fail -> out-of-scope.
        "5D": {"computed": {"PRPH2.ihc": None}},
        "5E": {"computed": {"rtqpcr": None}},
        "5F": {"computed": {"proteostat": None}},
    }


def _record_fig5_methods_inconsistency(ledger: Ledger, panel: Panel) -> Sweep:
    """The captured methods_vs_numbers finding (the Fig 5 headline) — the declarative form of
    what :func:`drive_live_fig5` derives by sweeping the real grid. The stated adj-p<0.05 yields
    19, not the printed 78 (nor 181/49); the printed counts appear only at unstated raw-p cuts."""
    note = (f"printed signature counts (78/{GOLD_SIGNATURE_METHODS}/{GOLD_DOWN_BOTH}) are "
            f"unreachable at the stated adj-p<0.05 (yields {SEL_SIGNATURE}); they appear only "
            f"at unstated raw-p cuts (~0.026 / ~0.1 / ~0.04) — not self-reconciling")
    inc = Inconsistency(kind="methods_vs_numbers", printed_in=["figure", "methods"],
                        conflicting_value=[str(GOLD_SIGNATURE), str(GOLD_SIGNATURE_METHODS),
                                           str(SEL_SIGNATURE)], note=note)
    ref = len(ledger.paper.inconsistencies)
    ledger.paper.inconsistencies.append(inc)
    sweep = Sweep(panel_key=panel.key, golden_metric="signature.count",
                  golden_value=GOLD_SIGNATURE, axes=["stat", "thr", "direction", "lfc_min"],
                  stated_setting={"stat": "padj", "thr": 0.05, "direction": "any", "lfc_min": 0.0},
                  stated_value=SEL_SIGNATURE, irreproducible=True, inconsistency_ref=ref, note=note)
    for g in panel.golden:
        if g.metric == "signature.count":
            g.inconsistency_ref = ref
    ledger.sweeps.append(sweep)
    return sweep


def drive_captured(ledger: Ledger | None = None) -> Ledger:
    """Drive the ledger through the engine using the captured dogfood observations.

    Pure + CI-safe: no real data, no R. For every panel with goldens, runs ``validate_panel``
    (verdict + blame, with the captured oracles), records the Fig 5 methods-vs-numbers
    inconsistency, and rebuilds the findings-first scorecard. The asserted output is that the
    engine *produces* the verdicts the manual dogfood reached (paper-irreproducible /
    structural-limit / engine-delta / upstream-delta, and zero Selom-engine bugs)."""
    ledger = ledger or build_ledger()
    cap = _captured()
    for panel in ledger.panels:
        if not panel.golden:
            continue  # form/claim panel — no printed number to validate
        entry = cap.get(panel.key, {})
        computed = entry.get("computed", {})
        oracles = entry.get("oracles")
        guards = ["deterministic_anchor"] if any(g.deterministic for g in panel.golden) else []
        if panel.scope == R.WET_LAB:
            guards = ["wet_lab_scope"]
        val = R.validate_panel(panel, computed, run_id=f"captured-{panel.key}",
                               oracles=oracles, guards_fired=guards)
        ledger.validations.append(val)
        panel.status = "validated"
    sig_panel = ledger.panel("5sig")
    if sig_panel is not None:
        _record_fig5_methods_inconsistency(ledger, sig_panel)
    ledger.scorecard = R.build_scorecard(ledger)
    return ledger


# --- live Fig 5 proof (real GSE293982 -> sweep + gated edgeR oracle -> revalidate) -----------


def _load_de_rows(csv_path: pathlib.Path) -> list[dict]:
    """Selom's real DE output (deg.run_real TMM path, de.py) -> sweep-shaped rows.

    Columns: Geneid, baseMean, log2FoldChange, lfcSE, stat, pvalue, padj. Maps to the
    ``{gene, lfc, p, padj}`` the sweep gate reads. stdlib csv only — no pandas dep here."""
    import csv

    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            try:
                rows.append({
                    "gene": rec["Geneid"],
                    "lfc": float(rec["log2FoldChange"]),
                    "p": float(rec["pvalue"]),
                    "padj": float(rec["padj"]),
                })
            except (ValueError, KeyError):
                continue  # NA rows (pyDESeq2 drops low-power genes) — skip
    return rows


def drive_live_fig5(
    ledger: Ledger | None = None,
    *,
    fig5_dir: str | pathlib.Path,
    counts_path: str | None = None,
    run_oracle: bool = False,
) -> tuple[Ledger, dict]:
    """Re-run the Fig 5 signature-count loop on the real deposit through the actual engine.

    ``fig5_dir`` holds Selom's real DE CSVs (``de_{MSVUS,LCA1}_vs_Control1.csv``) + the
    1,133-gene ``universe.txt`` (the manual records, KEEP). Stages, all real engine code:

      1. ``sweep.signature_set`` on the real DE rows -> Selom's signature.count (19) +
         down_both (13) at the stated adj-p<0.05.
      2. ``validate_panel`` with no oracle -> blame degrades to ``delta-unmeasured`` (honest).
      3. ``sweep_panel`` over the real grid -> proves the printed 78 irreproducible + emits the
         ``methods_vs_numbers`` inconsistency.
      4. (gated, ``run_oracle``) the **edgeR oracle** on the raw counts -> ``signature.adj`` ->
         ``revalidate_panel`` upgrades the blame to ``paper-irreproducible``.

    Returns ``(ledger, summary)``. ``summary`` carries the live numbers so a caller (or the CLI)
    can assert they match captured. The oracle stays gated (ADR 0002): without ``SELOM_ORACLE=r``
    the loop still completes, blame just stays ``delta-unmeasured``."""
    fig5_dir = pathlib.Path(fig5_dir)
    ledger = ledger or build_ledger()
    panel = ledger.panel("5sig")
    if panel is None:
        raise ValueError("ledger has no 5sig panel")

    universe = [g for g in (fig5_dir / "universe.txt").read_text(encoding="utf-8").splitlines()
                if g.strip()]
    ms_rows = _load_de_rows(fig5_dir / "de_MSVUS_vs_Control1.csv")
    lca_rows = _load_de_rows(fig5_dir / "de_LCA1_vs_Control1.csv")

    # 1. Selom's signature (real engine code on real rows) at the stated method (adj-p<0.05).
    # "down in both" = significant+down in the PRIMARY contrast (MS-VUS) AND down-by-direction
    # in the SECONDARY (LCA-1) — the paper's / de.py's / the edgeR oracle's definition (=13).
    # (NB: a strict signature_set ∩ signature_set — significant in *both* — is a different,
    # stricter reading; the down_both golden uses primary-significant + secondary-direction.)
    stated = dict(stat="padj", thr=0.05)
    sig_ms = signature_set(ms_rows, universe, direction="any", **stated)
    down_ms = signature_set(ms_rows, universe, direction="down", **stated)
    lca_lfc = {r["gene"]: r["lfc"] for r in lca_rows}
    down_both = {g for g in down_ms if lca_lfc.get(g, 0.0) < 0}
    computed = {
        "universe": len(universe),
        "signature.count": len(sig_ms),
        "signature.down_both": len(down_both),
    }

    # 2. Validate with no oracle -> delta-unmeasured (the default, honest degradation).
    run = R.ReproRun(id="live-5sig", panel_key=panel.key, skill_id="deg",
                     dataset_ref="GSE293982",
                     computed=[R.MetricValue(metric=k, value=v) for k, v in computed.items()])
    ledger.runs.append(run)
    ledger.validations.append(
        R.validate_panel(panel, computed, run_id=run.id, guards_fired=["deterministic_anchor"]))

    # 3. Real sweep over the grid -> irreproducible + methods_vs_numbers inconsistency.
    sweep = sweep_panel(ledger, panel, "signature.count",
                        {"MSVUS": ms_rows, "LCA1": lca_rows}, universe,
                        contrast="MSVUS",
                        stated_setting={"stat": "padj", "thr": 0.05, "direction": "any",
                                        "lfc_min": 0.0})

    # 4. (gated) edgeR oracle on the raw deposit -> revalidate -> paper-irreproducible.
    oracle_metrics = None
    blame_after = "delta-unmeasured (oracle gated off — ADR 0002)"
    if run_oracle:
        if counts_path is None:
            raise ValueError("--counts is required with --oracle")
        workdir = fig5_dir / "engine-oracle"
        try:
            res = run_edger_signature(counts_path, str(fig5_dir / "universe.txt"),
                                      "Control1", "MSVUS", "LCA1", workdir=workdir)
            m = res.get("metrics", {})
            oracle_metrics = m
            oracles = {
                "signature.count": _edger_oracle(m["signature.adj"], GOLD_SIGNATURE,
                                                  computed["signature.count"]),
                "signature.down_both": _edger_oracle(m["down_both.adj"], GOLD_DOWN_BOTH,
                                                      computed["signature.down_both"]),
            }
            R.revalidate_panel(ledger, panel, oracles=oracles,
                               guards_fired=["deterministic_anchor", "authors_tool_misses"])
            blame_after = _panel_blame(ledger, panel.key, "signature.count")
        except OracleUnavailable as exc:
            blame_after = f"delta-unmeasured (oracle unavailable: {exc})"

    ledger.scorecard = R.build_scorecard(ledger)
    summary = {
        "universe": computed["universe"],
        "signature.count": computed["signature.count"],
        "signature.down_both": computed["signature.down_both"],
        "sweep_irreproducible": sweep.irreproducible,
        "stated_value": sweep.stated_value,
        "oracle_metrics": oracle_metrics,
        "signature.count_blame": blame_after,
    }
    return ledger, summary


def _panel_blame(ledger: Ledger, panel_key: str, metric: str) -> str | None:
    val = next((v for v in ledger.validations if v.panel_key == panel_key), None)
    if val is None:
        return None
    r = next((r for r in val.results if r.metric == metric), None)
    return r.blame if r else None


# --- pretty-print + persistence ---------------------------------------------------------------


def format_scorecard(ledger: Ledger) -> str:
    sc = ledger.scorecard
    if sc is None:
        return "(no scorecard — drive the ledger first)"
    lines = [
        f"RPGRIP1 reproduction scorecard  ({sc.n_panels} panels, {sc.n_in_scope} in scope)",
        "  findings (what the engine surfaced):",
        f"    reproduced (faithful): {sc.findings['reproduced']}",
        f"    paper-irreproducible : {sc.findings['paper_irreproducible']}",
        f"    structural-limit     : {sc.findings['structural_limit']}",
        f"    engine-delta         : {sc.findings['engine_delta']}",
        f"    upstream-delta       : {sc.findings['upstream_delta']}",
        f"    SELOM-ENGINE BUGS    : {sc.findings['selom_engine_bugs']}",
        f"  verdicts : {dict(sc.totals_by_verdict)}",
        f"  blame    : {dict(sc.totals_by_blame)}",
        f"  inconsistencies recorded: {len(ledger.paper.inconsistencies)}",
        "",
        f"  {R.format_score(sc.score)}",
        "  per-panel Reproducibility Score:",
        *R.format_panel_scores(sc.panel_scores),
    ]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover — dev/validation harness (ADR 0002, library-only)
    import argparse

    p = argparse.ArgumentParser(
        description="RPGRIP1 reproduction ledger — drive it through the engine (validation-only)")
    p.add_argument("--live-fig5", action="store_true",
                   help="re-run the Fig 5 count loop on the real GSE293982 deposit")
    p.add_argument("--oracle", action="store_true",
                   help="enable the gated edgeR oracle in the live run (needs SELOM_ORACLE=r)")
    p.add_argument("--fig5-dir", default="D:/tmp-thl/fig5-real")
    p.add_argument("--counts",
                   default="C:/Temp/selom-geo/GSE293982/GSE293982_dedup_countTable_geneName.tsv.gz")
    p.add_argument("--save", action="store_true", help="save the ledger JSON under data_dir/repro")
    args = p.parse_args()

    if args.live_fig5:
        ledger, summary = drive_live_fig5(fig5_dir=args.fig5_dir, counts_path=args.counts,
                                          run_oracle=args.oracle)
        print("LIVE Fig 5 (real GSE293982):")
        for k, v in summary.items():
            print(f"  {k:24s} {v}")
        print()
    else:
        ledger = drive_captured()

    print(format_scorecard(ledger))
    if args.save:
        path = R.save_ledger(ledger)
        print(f"\nsaved: {path}")
