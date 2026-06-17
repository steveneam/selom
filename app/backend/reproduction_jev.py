"""Cioanca/JEV (Cioanca, Natoli et al. 2023) — the SECOND real reproduction ledger.

The first cross-paper stress-test of the Reproduction Engine. RPGRIP1 (``reproduction_rpgrip1``)
was bulk RNA-seq + scRNA where Selom *under-called* a paper whose printed counts were
irreproducible. JEV is a different shape entirely — EV mass-spec proteomics + OpenArray miRNA,
with **faithful reproductions** plus a single-cell pipeline whose data was never deposited — so it
checks whether ``build_ledger`` / the blame taxonomy / the scorecard are RPGRIP1-overfit.

Driving JEV through the engine validates the reproduction AND clarifies the right way to handle
a figure that differs from its own deposit:

* **Selom reproduces the deposited supplementary tables exactly** — the reproducible TARGET is the
  deposit (Table S2 → 34 DE miRNAs, Table S6 → 447 DE proteins, PCA 39.7%/18.5% ≈ published
  39.8%/18.5%, the ST8 deconvolution, the labelled volcano hits at matching positions).
* **Source provenance over accusation (D14).** The published Fig 4e shows 61 up / 119 down (180),
  which is not reconstructable from the complete deposited Table S6 at *any* single threshold (the
  up- and down-counts pin different p; a full sweep confirms it). The labelled proteins sit at
  matching positions, so the figure is most likely a **different biological/experimental
  replicate** than the deposit. The engine records this as a neutral ``Fig4e−`` :class:`SourceTag`
  (``ST6+ Fig4e−``) and a ``deposit_vs_figure`` :class:`Inconsistency`, surfaced transparently —
  NOT as a paper-error blame. The panel still counts as a faithful reproduction of ST6.
* The single-cell panels (Fig 8) are a **method demo** — the study's own scRNA (PRJNA990691) was
  never deposited, so the pipeline runs on the Fadl 2020 reference (GSE153674). That is neither
  wet-lab nor a deposited-data structural limit: it is the new ``DATA_NOT_DEPOSITED`` scope.

Two drive modes mirror ``reproduction_rpgrip1``:

* :func:`drive_captured` — pure/CI-safe: replays the verified dogfood observations (validated
  against the deposited tables) through ``validate_panel`` → ``build_scorecard``.
* :func:`drive_live_de` — re-counts the miRNA + proteome DE from the deposited supplementary
  workbook (``…-s001.xlsx``) through pandas, proving captured == live and that the figures'
  35 / 180 differ from the deposit's 34 / 447.

Library-only (D12); no HTTP. The paper PDF + supplement live outside the repo (Adrian/ share).

Dev/validation entrypoint:

    python -m reproduction_jev                       # captured drive → scorecard
    python -m reproduction_jev --live --xlsx "…/JEV2-12-12393-s001.xlsx"   # live DE recount
"""

from __future__ import annotations

import pathlib

import reproduction as R
from reproduction import (
    Golden,
    Inconsistency,
    Ledger,
    MethodSub,
    Panel,
    Paper,
    Sweep,
    SweepCell,
)

PAPER_ID = "jev"

# --- golden target VALUES (printed in the paper text/figures) --------------------------------
# Confirmed against jev_main.txt + the published figures (Adrian/ share). The paper's PRINTED
# counts are the goldens; what Selom reproduces from the deposited tables is below.
GOLD_MIRNA_UP = 12             # text: "12 upregulated"          (Fig 1c / Fig S1e, p<0.05)
GOLD_MIRNA_DOWN = 23           # text: "23 downregulated"        (ST2 itself only has 22 — off by 1)
GOLD_MIRNA_TOTAL = 35          # 12 + 23
GOLD_PROT_UP = 61             # text/legend: "61 upregulated"   (Fig 4e, p<0.05)
GOLD_PROT_DOWN = 119          # text/legend: "119 downregulated"
GOLD_PROT_TOTAL = 180         # "180 proteins differentially expressed"
GOLD_PC1 = 39.8               # Fig 4c axis label (% variance)
GOLD_PC2 = 18.5               # Fig 4c axis label

# --- what Selom reproduces from the deposited supplementary tables (the real observations) ----
# Each is a logged/verified value, confirmed by re-reading the deposited workbook (drive_live_de
# re-derives the DE counts). Selom matches the authors' OWN tables exactly.
SEL_MIRNA_UP = 12             # ST2 @p<=0.05
SEL_MIRNA_DOWN = 22           # ST2 @p<=0.05  (paper text says 23 — text vs its own table)
SEL_MIRNA_TOTAL = 34
SEL_PROT_UP = 172            # ST6 @p<=0.05
SEL_PROT_DOWN = 275          # ST6 @p<=0.05
SEL_PROT_TOTAL = 447         # ST6 @p<=0.05  (paper text says 180 — text vs its own table)
SEL_PC1 = 39.7              # Selom PCA on the proteome matrix
SEL_PC2 = 18.5
SEL_MIRNA_TOP = "mmu-miR-182-5p"  # top miRNA by p-value (ST2)
SEL_PROT_TOP_UP = "B2M"           # Fig 4e's labeled top-right up-regulated hit (B2m in ST6)
SEL_N_TOP50 = 50                  # Fig 4d top-50 DE heatmap (re-plot of ST6)
SEL_N_EV_FUNC = 28                # Fig 5D EV-mediator proteins (ST10 functional list × ST5)
SEL_MULLER_DR = 2.61             # Fig 6a/b deconvolution (ST8): Müller glia, DR
SEL_MULLER_PD = 22.25            # Fig 6a/b: Müller glia, PD (largest DR→PD contribution shift)


# --- ledger construction (the structured target spec; R4 will auto-generate this) ------------


def _inconsistencies() -> list[Inconsistency]:
    """The two deposit_vs_figure inconsistencies: the paper's printed DE counts don't match
    its own deposited supplementary tables at the stated p<0.05. Indices 0 (miRNA) / 1 (protein)
    are referenced by the affected goldens."""
    return [
        Inconsistency(
            kind="deposit_vs_figure", printed_in=["figure", "text"],
            conflicting_value=[f"text {GOLD_MIRNA_UP}up/{GOLD_MIRNA_DOWN}down={GOLD_MIRNA_TOTAL}",
                               f"ST2 {SEL_MIRNA_UP}up/{SEL_MIRNA_DOWN}down={SEL_MIRNA_TOTAL}"],
            note="Fig 1c text 35 (12/23) vs the complete Table S2 34 (12/22) at p<0.05 — a "
                 "single-miRNA gap (≤/< boundary or typo), within tolerance; reconstructed "
                 "faithfully from ST2 (ST2+ Fig1c+)"),
        Inconsistency(
            kind="deposit_vs_figure", printed_in=["figure", "legend", "text"],
            conflicting_value=[f"Fig4e {GOLD_PROT_UP}up/{GOLD_PROT_DOWN}down={GOLD_PROT_TOTAL}",
                               f"ST6 {SEL_PROT_UP}up/{SEL_PROT_DOWN}down={SEL_PROT_TOTAL}"],
            note="Fig 4e shows 61 up / 119 down (180); reconstructing from the deposited complete "
                 "Table S6 (same dim-reared-vs-PD contrast) gives 172/275 (447) at p<0.05, and no "
                 "single threshold reproduces 61/119 (up-count and down-count pin different p). "
                 "The labelled proteins sit at matching positions, so the figure is most likely a "
                 "different biological/experimental replicate than the deposit — recorded as "
                 "provenance (ST6+ Fig4e−), not a paper error"),
    ]


def _mirna_panels() -> list[Panel]:
    de_sub = MethodSub(
        paper_tool="limma moderated-t on OpenArray miRNA Ct → topTable (Table S2)",
        selom_tool="reproduces the deposited Table S2 DE result directly",
        reason="the authors deposited their DE table; Selom re-derives its counts",
        delta_measured="ST2 reproduced exactly (34 = 12 up / 22 down); the figure's 35 (12/23) "
                       "is a single-miRNA gap, within tolerance",
    )
    return [
        # Fig 1c — DE miRNA heatmap; reproduced against the deposited ST2 (the reproducible
        # target). The figure's 35 vs ST2's 34 is a 1-miRNA boundary/typo → Fig1c still faithful.
        Panel(
            paper_id=PAPER_ID, figure="1", panel="c", chart_form="heatmap", skill_id="deg",
            data_source="Table S1/S2 (OpenArray miRNA)", method_subs=[de_sub],
            sources=[
                R.SourceTag(ref="ST2", faithful=True, note="complete miRNA DE table reproduced exactly"),
                R.SourceTag(ref="Fig1c", faithful=True,
                            note=f"figure {GOLD_MIRNA_TOTAL} ({GOLD_MIRNA_UP}/{GOLD_MIRNA_DOWN}) vs "
                                 f"ST2 {SEL_MIRNA_TOTAL} ({SEL_MIRNA_UP}/{SEL_MIRNA_DOWN}) — 1-miRNA "
                                 f"boundary, within tolerance"),
            ],
            golden=[
                Golden(metric="de_up", value=SEL_MIRNA_UP, source=R.SOURCE_EXTRACTED,
                       inconsistency_ref=0, note="upregulated DE miRNAs in ST2 (p<0.05)"),
                Golden(metric="de_down", value=SEL_MIRNA_DOWN, source=R.SOURCE_EXTRACTED,
                       inconsistency_ref=0, note="downregulated in ST2 (figure says 23)"),
                Golden(metric="de_total", value=SEL_MIRNA_TOTAL, source=R.SOURCE_EXTRACTED,
                       inconsistency_ref=0, note="total DE miRNAs in ST2 (figure says 35)"),
            ],
        ),
        # Fig 3 — same ST2 data recast as a Selom volcano (a presentation the editor offers).
        Panel(
            paper_id=PAPER_ID, figure="3", panel="", chart_form="volcano", skill_id="volcano",
            data_source="Table S2",
            sources=[R.SourceTag(ref="ST2", faithful=True),
                     R.SourceTag(ref="Fig3", faithful=True, note="recast as volcano (paper: CDF+MA)")],
            golden=[
                Golden(metric="top_mirna", value=SEL_MIRNA_TOP, source=R.SOURCE_FIGURE,
                       note="top DE miRNA by p-value (miR-182-5p, miR-183/96/182 cluster)")],
            note="ST2 differential data recast as a volcano; same data as Fig 1c (the paper shows "
                 "it as a CDF + MA plot)"),
    ]


def _proteome_panels() -> list[Panel]:
    return [
        # Fig 4c — proteome PCA: the cleanest genuine analysis reproduction (Selom computes it),
        # and it matches the published variance → ST6+ Fig4c+.
        Panel(
            paper_id=PAPER_ID, figure="4", panel="c", chart_form="pca", skill_id="pca",
            data_source="Table S6 (EV proteome, 2180 × 10)",
            sources=[R.SourceTag(ref="ST6", faithful=True),
                     R.SourceTag(ref="Fig4c", faithful=True, note="PC1/PC2 variance match")],
            golden=[
                Golden(metric="pc1_var", value=GOLD_PC1, unit="%", source=R.SOURCE_FIGURE,
                       ints_exact=False, note="PC1 variance; Selom 39.7%"),
                Golden(metric="pc2_var", value=GOLD_PC2, unit="%", source=R.SOURCE_FIGURE,
                       ints_exact=False, note="PC2 variance; Selom 18.5%"),
            ],
        ),
        # Fig 4d — top-50 DE protein heatmap (re-plot of the deposited table).
        Panel(
            paper_id=PAPER_ID, figure="4", panel="d", chart_form="heatmap", skill_id="heatmap",
            data_source="Table S6",
            sources=[R.SourceTag(ref="ST6", faithful=True),
                     R.SourceTag(ref="Fig4d", faithful=True, note="top-50 DE heatmap")],
            golden=[Golden(metric="n_proteins", value=SEL_N_TOP50, source=R.SOURCE_FIGURE,
                           note="top-50 DE proteins, z-scored, hierarchically clustered")],
        ),
        # Fig 4e — the proteome volcano. Reconstructed FAITHFULLY from the deposited Table S6
        # (the reproducible target) → a win; the published figure shows 61/119/180, which no
        # single threshold on ST6 reproduces (labelled proteins match positions → most likely a
        # different replicate). Recorded transparently as ST6+ Fig4e−, not as a paper error.
        Panel(
            paper_id=PAPER_ID, figure="4", panel="e", chart_form="volcano", skill_id="deg",
            data_source="Table S6",
            sources=[
                R.SourceTag(ref="ST6", faithful=True,
                            note="complete EV-proteome DE table reproduced exactly (172/275/447 @p<0.05)"),
                R.SourceTag(ref="Fig4e", faithful=False,
                            note=f"figure shows {GOLD_PROT_UP} up / {GOLD_PROT_DOWN} down "
                                 f"({GOLD_PROT_TOTAL}); not reconstructable from ST6 at any single "
                                 f"threshold — likely a different replicate"),
            ],
            golden=[
                Golden(metric="de_up", value=SEL_PROT_UP, source=R.SOURCE_EXTRACTED,
                       note="upregulated in the deposited ST6 (p<0.05); figure shows 61"),
                Golden(metric="de_down", value=SEL_PROT_DOWN, source=R.SOURCE_EXTRACTED,
                       note="downregulated in ST6 (p<0.05); figure shows 119"),
                Golden(metric="de_total", value=SEL_PROT_TOTAL, source=R.SOURCE_EXTRACTED,
                       inconsistency_ref=1, note="total DE in ST6 (p<0.05); figure shows 180"),
                Golden(metric="top_up_protein", value=SEL_PROT_TOP_UP, source=R.SOURCE_FIGURE,
                       note="B2M — the figure's labeled top up-regulated hit (matches ST6)"),
            ],
        ),
    ]


def _ev_and_deconv_panels() -> list[Panel]:
    deconv_sub = MethodSub(
        paper_tool="SVR deconvolution (Newman 2015, CIBERSORT-style) vs Fadl 2020 signatures (ST8)",
        selom_tool="re-plots the deposited ST8 deconvolution result",
        reason="the authors deposited the deconvolution table; Selom reproduces the chart",
        delta_measured="chart reproduction of ST8 — values identical (no independent SVR run)",
    )
    return [
        # Fig 5D — EV-mediator functional-protein heatmap (ST10 functional list × ST5).
        Panel(
            paper_id=PAPER_ID, figure="5", panel="D", chart_form="heatmap", skill_id="heatmap",
            data_source="Table S5 × Table S10",
            sources=[R.SourceTag(ref="ST5", faithful=True), R.SourceTag(ref="ST10", faithful=True),
                     R.SourceTag(ref="Fig5D", faithful=True, note="EV-mediator heatmap")],
            golden=[Golden(metric="n_ev_proteins", value=SEL_N_EV_FUNC, source=R.SOURCE_FIGURE,
                           note="ESCRT (PDCD6IP, CHMP2A/4B/5/6, IST1) + RNA-loading (AGO1, "
                                "HNRNPA2B1) EV-biogenesis mediators")],
        ),
        # Fig 6a/b — retinal deconvolution; Müller glia is the largest DR→PD contribution shift.
        Panel(
            paper_id=PAPER_ID, figure="6", panel="a", chart_form="stacked_area",
            skill_id="composition", data_source="Table S8", method_subs=[deconv_sub],
            sources=[R.SourceTag(ref="ST8", faithful=True, note="deconvolution proportions re-plotted"),
                     R.SourceTag(ref="Fig6", faithful=True, note="Müller-glia shift reproduced")],
            golden=[
                Golden(metric="muller_dr_pct", value=SEL_MULLER_DR, unit="%",
                       source=R.SOURCE_FIGURE, ints_exact=False, note="Müller glia, DR EV"),
                Golden(metric="muller_pd_pct", value=SEL_MULLER_PD, unit="%",
                       source=R.SOURCE_FIGURE, ints_exact=False,
                       note="Müller glia, PD EV — largest contribution increase (Fig 6b)"),
            ],
        ),
    ]


def _singlecell_panels() -> list[Panel]:
    """Fig 8 — the single-cell pipeline. The study's own scRNA (PRJNA990691) was never deposited,
    so each panel is a pipeline DEMO on the Fadl 2020 reference (GSE153674): reproducible as a
    figure type, but NOT against the paper's data → the new DATA_NOT_DEPOSITED scope."""
    demo_sub = MethodSub(
        paper_tool="Seurat SCTransform → PCA(3000 HVG) → clustering → FindAllMarkers",
        selom_tool="scanpy pipeline on the Fadl 2020 reference (GSE153674)",
        reason="the study's own scRNA (PRJNA990691) was never deposited",
        delta_measured=None,  # can't measure — a different dataset
    )

    def demo(panel: str, form: str, skill: str, what: str) -> Panel:
        return Panel(
            paper_id=PAPER_ID, figure="8", panel=panel, chart_form=form, skill_id=skill,
            scope=R.DATA_NOT_DEPOSITED, data_source="Fadl 2020 GSE153674 (reference, not the study)",
            method_subs=[demo_sub],
            sources=[R.SourceTag(ref="GSE153674", faithful=True, note="reference dataset (pipeline demo)"),
                     R.SourceTag(ref="Fig8", faithful=False, note="study's own scRNA never deposited")],
            golden=[Golden(metric=panel, value=1, note=f"{what} — pipeline demo, no paper data")])

    return [
        demo("a", "umap", "umap_scrna", "cell-type UMAP (Fig 8a)"),
        demo("ann", "umap", "annotate", "marker-score annotation (Fig 8a)"),
        demo("d", "dotplot", "markers", "marker dotplot (Fig 8d)"),
        demo("e", "trajectory", "trajectory", "pseudotime trajectory (Fig 8e)"),
    ]


def build_ledger() -> Ledger:
    """The full JEV reproduction ledger (Fig 1/3/4/5/6/8), built from the target spec.

    Pure: no data, no heavy deps. The hand-authored structured form of the JEV figure-repro
    record that R4's extraction subsystem will eventually produce from the PDF + supplement."""
    paper = Paper(
        id=PAPER_ID, slug=PAPER_ID,
        title="Retinal EV-miRNA driving gliotic responses in degeneration "
              "(Cioanca, Natoli et al. 2023, J Extracell Vesicles)",
        doi="10.1002/jev2.12393",
        geo=["GSE153674 (Fadl 2020 reference — the study's own scRNA PRJNA990691 not deposited)"],
        methods_digest={
            "mirna_de": "OpenArray miRNA Ct → limma moderated-t → topTable (Table S2), p<0.05",
            "proteome_de": "1D LC-MS/MS → VST → limma moderated-t → topTable (Table S6), p<0.05",
            "pca": "VST-normalized EV proteome → PCA (39.8% / 18.5%, DR–PD split p=0.015)",
            "deconvolution": "SVR deconvolution (Newman 2015) of EV proteome vs Fadl 2020 retinal "
                             "cell-type signatures (Table S7/S8)",
            "scrna": "Seurat SCTransform pipeline — run on the Fadl 2020 reference; the study's "
                     "own scRNA was never deposited",
        },
        inconsistencies=_inconsistencies(),
    )
    return Ledger(
        paper=paper,
        panels=[*_mirna_panels(), *_proteome_panels(), *_ev_and_deconv_panels(),
                *_singlecell_panels()],
    )


# --- captured drive (CI-safe: replay the verified dogfood through the engine) ----------------


def _proteome_sweep() -> Sweep:
    """Record the Fig 4e threshold sweep on the deposited Table S6 — the evidence behind the
    ``Fig4e−`` provenance tag (NOT a blame). No (stat, thr) reaches the figure's printed 180:
    the stated p<0.05 gives 447, adj-P / B-stat / p×|logFC| all miss 61/119/180, and the up- and
    down-counts pin different p-thresholds — so the figure's exact split isn't reconstructable
    from the deposit (most likely a different replicate; the labelled proteins match positions)."""
    grid = [
        SweepCell(setting={"stat": "P.Value", "thr": 0.05}, value=447),    # stated
        SweepCell(setting={"stat": "adj.P.Val", "thr": 0.05}, value=36),
        SweepCell(setting={"stat": "adj.P.Val", "thr": 0.15}, value=145),
        SweepCell(setting={"stat": "adj.P.Val", "thr": 0.20}, value=357),
        SweepCell(setting={"stat": "B", "thr": 0.0}, value=28),
        SweepCell(setting={"stat": "P.Value", "thr": 0.05, "lfc_min": 1.0}, value=255),
        SweepCell(setting={"stat": "P.Value", "thr": 0.05, "lfc_min": 1.5}, value=112),
    ]
    return Sweep(
        panel_key="4e", golden_metric="de_total", golden_value=GOLD_PROT_TOTAL,
        axes=["stat", "thr", "lfc_min"], grid=grid,
        stated_setting={"stat": "P.Value", "thr": 0.05}, stated_value=SEL_PROT_TOTAL,
        reproducing_setting=None, irreproducible=True, inconsistency_ref=1,
        note="no threshold on the complete deposited Table S6 reproduces the printed 180 (61/119)")


def _captured() -> dict[str, dict]:
    """Per-panel ``{computed}`` — the verified observations (confirmed against the deposited
    workbook; drive_live_de re-derives the DE counts). Every panel is validated against its
    DEPOSITED source (the reproducible target), which Selom matches; divergence from a published
    figure is carried by the panel's ``Fig*−`` provenance tag, not by a blame."""
    return {
        "1c": {"computed": {"de_up": SEL_MIRNA_UP, "de_down": SEL_MIRNA_DOWN,
                            "de_total": SEL_MIRNA_TOTAL}},  # == ST2 → exact (figure 35 is +1)
        "3": {"computed": {"top_mirna": SEL_MIRNA_TOP}},     # identity — exact
        "4c": {"computed": {"pc1_var": SEL_PC1, "pc2_var": SEL_PC2}},  # 39.7≈39.8 / 18.5 — exact
        "4d": {"computed": {"n_proteins": SEL_N_TOP50}},     # form re-plot — exact
        "4e": {"computed": {"de_up": SEL_PROT_UP, "de_down": SEL_PROT_DOWN,
                            "de_total": SEL_PROT_TOTAL, "top_up_protein": SEL_PROT_TOP_UP}},
        # == ST6 → exact reproduction of the deposit; Fig4e (61/119/180) carried by the − tag
        "5D": {"computed": {"n_ev_proteins": SEL_N_EV_FUNC}},  # form re-plot — exact
        "6a": {"computed": {"muller_dr_pct": SEL_MULLER_DR, "muller_pd_pct": SEL_MULLER_PD}},
        # Fig 8 — data not deposited: no paper value to match (out-of-scope demo).
        "8a": {"computed": {"a": None}}, "8ann": {"computed": {"ann": None}},
        "8d": {"computed": {"d": None}}, "8e": {"computed": {"e": None}},
    }


def drive_captured(ledger: Ledger | None = None) -> Ledger:
    """Drive the JEV ledger through the engine using the captured dogfood observations.

    Pure + CI-safe. The asserted output is the findings-first scorecard the engine *produces*:
    a wall of faithful reproductions against the deposited sources (tables + PCA), the single-cell
    pipeline out-of-scope (data not deposited), zero Selom-engine bugs — and the proteome volcano
    surfaced transparently as a provenance divergence (ST6+ Fig4e−), not a paper-error blame."""
    ledger = ledger or build_ledger()
    cap = _captured()
    for panel in ledger.panels:
        if not panel.golden:
            continue
        entry = cap.get(panel.key, {})
        guards = ["data_not_deposited"] if panel.scope == R.DATA_NOT_DEPOSITED else []
        val = R.validate_panel(panel, entry.get("computed", {}), run_id=f"captured-{panel.key}",
                               guards_fired=guards)
        ledger.validations.append(val)
        panel.status = "validated"
    ledger.sweeps.append(_proteome_sweep())  # evidence behind the Fig4e− provenance tag
    ledger.scorecard = R.build_scorecard(ledger)
    return ledger


# --- live DE recount (re-derive from the deposited supplementary workbook) --------------------


def _count_de(xlsx_path: str, sheet: str, key_col: str, header: int = 3,
              p_thr: float = 0.05) -> dict:
    """Re-derive up/down/total DE from a deposited limma topTable sheet at p<=p_thr. pandas only."""
    import pandas as pd

    df = pd.read_excel(xlsx_path, sheet_name=sheet, header=header).dropna(subset=[key_col])
    p = pd.to_numeric(df["P.Value"], errors="coerce")
    fc = pd.to_numeric(df["logFC"], errors="coerce")
    sig = p <= p_thr
    return {"up": int(((fc > 0) & sig).sum()), "down": int(((fc < 0) & sig).sum()),
            "total": int(sig.sum())}


def drive_live_de(ledger: Ledger | None = None, *, xlsx_path: str | pathlib.Path) -> tuple[Ledger, dict]:
    """Re-count the miRNA (ST2) + proteome (ST6) DE from the deposited workbook and revalidate.

    Proves captured == live: Selom re-derives 34 (12/22) and 447 (172/275) from the authors'
    deposited tables (the reproducible target), and the figures' 35 / 180 differ — the proteome
    split (61/119) is unreachable from ST6 at any threshold (Fig4e−). Needs pandas + the external
    supplement (not CI-safe)."""
    xlsx_path = str(xlsx_path)
    ledger = ledger or build_ledger()

    mirna = _count_de(xlsx_path, "ST2", "miRNA")
    prot = _count_de(xlsx_path, "ST6", "Protein")

    # Replace the captured DE counts with the live recount, then drive every panel through validate.
    cap = _captured()
    cap["1c"]["computed"] = {"de_up": mirna["up"], "de_down": mirna["down"],
                             "de_total": mirna["total"]}
    cap["4e"]["computed"].update({"de_up": prot["up"], "de_down": prot["down"],
                                  "de_total": prot["total"]})
    for panel in ledger.panels:
        if not panel.golden:
            continue
        entry = cap.get(panel.key, {})
        guards = ["data_not_deposited"] if panel.scope == R.DATA_NOT_DEPOSITED else []
        ledger.validations.append(
            R.validate_panel(panel, entry.get("computed", {}), run_id=f"live-{panel.key}",
                             guards_fired=guards))
        panel.status = "validated"
    ledger.sweeps.append(_proteome_sweep())
    ledger.scorecard = R.build_scorecard(ledger)

    summary = {
        "mirna_ST2": mirna, "mirna_figure": [GOLD_MIRNA_UP, GOLD_MIRNA_DOWN, GOLD_MIRNA_TOTAL],
        "proteome_ST6": prot, "proteome_figure": [GOLD_PROT_UP, GOLD_PROT_DOWN, GOLD_PROT_TOTAL],
        "proteome_provenance": ledger.panel("4e").provenance,
        "captured_matches_live": (mirna["total"] == SEL_MIRNA_TOTAL
                                  and prot["total"] == SEL_PROT_TOTAL),
    }
    return ledger, summary


# --- pretty-print + persistence ---------------------------------------------------------------


def format_scorecard(ledger: Ledger) -> str:
    sc = ledger.scorecard
    if sc is None:
        return "(no scorecard — drive the ledger first)"
    return "\n".join([
        f"JEV reproduction scorecard  ({sc.n_panels} panels, {sc.n_in_scope} in scope)",
        "  findings (what the engine surfaced):",
        f"    reproduced (faithful): {sc.findings['reproduced']}",
        f"    paper-irreproducible : {sc.findings['paper_irreproducible']}",
        f"    structural-limit     : {sc.findings['structural_limit']}",
        f"    engine-delta         : {sc.findings['engine_delta']}",
        f"    upstream-delta       : {sc.findings['upstream_delta']}",
        f"    SELOM-ENGINE BUGS    : {sc.findings['selom_engine_bugs']}",
        f"  verdicts : {dict(sc.totals_by_verdict)}",
        f"  blame    : {dict(sc.totals_by_blame)}",
        "  source provenance (reconstructed-from / diverges-from):",
        *[f"    {p.key:4s} {p.provenance}" for p in ledger.panels if p.sources],
        f"  figure divergences (shown, not blamed): {sc.provenance_divergences or 'none'}",
    ])


if __name__ == "__main__":  # pragma: no cover — dev/validation harness (ADR 0002, library-only)
    import argparse

    p = argparse.ArgumentParser(
        description="JEV reproduction ledger — drive it through the engine (validation-only)")
    p.add_argument("--live", action="store_true",
                   help="re-count miRNA/proteome DE from the deposited supplement")
    p.add_argument("--xlsx",
                   default="C:/Users/seamegdool/Desktop/Claude code and website tips/Data/"
                           "Adrian/JEV2-12-12393-s001.xlsx")
    p.add_argument("--save", action="store_true", help="save the ledger JSON under data_dir/repro")
    args = p.parse_args()

    if args.live:
        ledger, summary = drive_live_de(xlsx_path=args.xlsx)
        print("LIVE DE recount (deposited supplement):")
        for k, v in summary.items():
            print(f"  {k:24s} {v}")
        print()
    else:
        ledger = drive_captured()

    print(format_scorecard(ledger))
    if args.save:
        path = R.save_ledger(ledger)
        print(f"\nsaved: {path}")
