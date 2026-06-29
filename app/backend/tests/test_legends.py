"""Figure-legend layer (P4c) — the legend half of the Methods+legend layer.

`legends.build_caption` is the per-run primitive (the sibling of `methods.build_body`); the ledger
composer keeps panels separate (one caption per figure) where the methods composer collapses them.
The load-bearing properties: a caption is honest from params alone, sharpened by the run's real
result when present (the DE split, via the SAME `extract.readers` tally as the grading read-back),
and never invents detail for an untemplated skill.
"""

from __future__ import annotations

import pytest

from companions import legends
import papers_api
import reproduction as R
from extract.readers import de_counts
from litsynth import legends_from_ledger as ledger_legends
from skills.contract import load_skill


def _de_table(up=3, down=2, ns=1):
    rows = ([["u%d" % i, 2.0, 0.001, "up"] for i in range(up)]
            + [["d%d" % i, -2.0, 0.001, "down"] for i in range(down)]
            + [["n%d" % i, 0.1, 0.9, "n.s."] for i in range(ns)])
    return {"columns": ["gene", "log2FC", "padj", "direction"], "rows": rows, "title": "DE"}


# --- the canonical DE-count wrapper (one source of truth with the grading reader) -------------


def test_de_counts_tallies_direction_or_none():
    assert de_counts(_de_table(3, 2)) == (3, 2)
    assert de_counts({"columns": ["gene", "logFC"], "rows": [["a", 1.0]]}) is None
    assert de_counts(None) is None


# --- per-skill captions (honest from params alone) --------------------------------------------


@pytest.mark.parametrize("skill_id,needle", [
    ("umap_scrna", "UMAP embedding"),
    ("cluster", "Leiden cluster"),
    ("volcano", "Volcano plot of differential expression"),
    ("pca", "Principal-component analysis"),
    ("markers", "Dot plot"),
    ("trajectory", "diffusion pseudotime"),
    ("go_graph", "node-link graph"),
    ("corr_heatmap", "correlation heatmap"),
    ("scorecard", "Multi-metric comparison"),
    ("regression", "ordinary-least-squares fit"),
])
def test_build_caption_per_skill(skill_id, needle):
    text = legends.build_caption(load_skill(skill_id), {})
    assert needle in text
    assert text.endswith(".")  # a clean, paste-ready sentence


def test_caption_uses_resolved_param_values():
    # the volcano default thresholds (resolved from the spec) appear verbatim.
    text = legends.build_caption(load_skill("volcano"), {})
    assert "|log2FC| >=" in text and "FDR <=" in text


def test_deg_caption_carries_the_contrast():
    text = legends.build_caption(load_skill("deg"), {"reference": "WT", "treatment": "KO"})
    assert "KO versus WT" in text


# --- result enrichment: the DE split, only when the table is supplied -------------------------


def test_volcano_caption_enriched_with_de_split():
    bare = legends.build_caption(load_skill("volcano"), {})
    assert "up," not in bare  # params-only: no fabricated counts
    rich = legends.build_caption(load_skill("volcano"), {}, table=_de_table(3, 2))
    assert "(3 up, 2 down)" in rich


def test_proteomics_de_caption_enriched_with_de_split():
    rich = legends.build_caption(load_skill("proteomics_de"), {}, table=_de_table(4, 1))
    assert "(4 up, 1 down)" in rich


# --- generic fallback: name the skill, invent nothing -----------------------------------------


def test_generic_fallback_for_untemplated_skill(monkeypatch):
    monkeypatch.setattr(legends, "_TEMPLATES", {})  # force every skill down the generic path
    spec = load_skill("volcano")
    assert legends.build_caption(spec, {}) == f"{spec.title} of the input data."


# --- the per-run wiring on /skills/{id}/run ---------------------------------------------------


def test_run_response_carries_a_figure_legend(monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    c = TestClient(app)
    # A DE-results table (logFC + padj) — what volcano actually reads. (A raw counts table would now
    # be blocked pre-run by the D1 data-contract gate; the stub only ever ignored the columns.)
    de = b"gene,log2FoldChange,padj\nA,2.0,0.001\nB,-1.5,0.02\n"
    r = c.post("/skills/volcano/run", files={"matrix": ("m.csv", de, "text/csv")})
    assert r.status_code == 200
    legend = r.json()["figure_legend"]
    assert legend["text"].startswith("Volcano plot of differential expression")


# --- the ledger composer: one caption per in-scope figure -------------------------------------


def _panel(fig, panel, skill_id, *, params=None, scope=R.TRANSCRIPTOMIC):
    return R.Panel(paper_id="demo", figure=fig, panel=panel, skill_id=skill_id,
                   params=params or {}, scope=scope)


def _demo_ledger():
    paper = R.Paper(id="demo", slug="demo", title="Demo", modality="scrna")
    panels = [
        _panel("1", "A", "umap_scrna"),
        _panel("2", "B", "volcano"),            # will carry a driven run (DE split enriches)
        _panel("3", "A", None),                 # form/claim panel, no skill -> skipped
        _panel("3", "B", "markers", scope=R.DATA_NOT_DEPOSITED),  # out of scope -> skipped
        _panel("3", "C", "box"),                # unloadable chart-form id -> skipped
    ]
    ledger = R.Ledger(paper=paper, panels=panels)
    vol = panels[1]
    ledger.runs.append(R.ReproRun(
        id="r1", panel_key=vol.key, skill_id="volcano", params={}, dataset_ref="d.csv",
        figure_spec={"data": [], "layout": {}}, table=_de_table(3, 2)))
    return ledger


def test_compose_ledger_legends_one_per_in_scope_panel():
    items = ledger_legends.compose_ledger_legends(_demo_ledger())
    assert [it.skill_id for it in items] == ["umap_scrna", "volcano"]  # form/oos/unloadable dropped
    assert [it.label for it in items] == ["Figure 1A.", "Figure 2B."]
    # the volcano panel had a driven run, so its caption is enriched with the real DE split.
    assert "(3 up, 2 down)" in items[1].text


def test_compose_ledger_legends_raises_without_in_scope_panels():
    ledger = R.Ledger(paper=R.Paper(id="e", slug="e"),
                      panels=[_panel("1", "A", None), _panel("1", "B", "volcano", scope=R.WET_LAB)])
    with pytest.raises(ValueError, match="no in-scope analysis panels"):
        ledger_legends.compose_ledger_legends(ledger)


# --- against the REAL driven ledgers + the endpoint -------------------------------------------


@pytest.mark.parametrize("slug", papers_api.SLUGS)
def test_real_ledgers_compose_legends(slug):
    items = ledger_legends.compose_ledger_legends(papers_api.driven_ledger(slug))
    assert items and all(it.text and it.label.startswith("Figure ") for it in items)


def test_legends_endpoint_serves_and_validates_slug():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    r = c.get("/papers/hani/legends")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "hani" and body["legends"]
    assert all(item["text"] and item["label"] for item in body["legends"])
    assert c.get("/papers/nope/legends").status_code == 404
