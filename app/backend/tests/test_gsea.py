"""GSEA engine upgrade — figure shape + library-mode table across engines.

The stub golden (test_skills_golden) pins the dependency-free path. These exercise the
REAL engines on a tiny synthetic ranked list where the answer is known: a gene set
concentrated at the top of a descending rank must score a positive enrichment score, and
library mode must return a sorted Statistics table. The in-house weighted-KS path needs no
extra deps; the gseapy path is importorskip'd. (blitzgsea is validated as a dogfood — its
first import does a slow numba JIT, so it is kept out of the fast CI suite.)
"""

import numpy as np
import pandas as pd
import pytest


def _ranked_csv(tmp_path, n=200):
    """A descending ranked DE table; genes G0..G29 carry the top (most positive) metric."""
    rng = np.random.default_rng(0)
    metric = np.sort(rng.normal(size=n))[::-1]
    df = pd.DataFrame({"gene": [f"G{i}" for i in range(n)], "log2fc": metric})
    path = tmp_path / "ranked.csv"
    df.to_csv(path, index=False)
    return str(path)


def _es(fig):
    """The peak enrichment score from the figure's 'peak ES' marker trace."""
    return fig["data"][1]["y"][0]


def _is_three_panel(fig):
    return (isinstance(fig.get("data"), list) and len(fig["data"]) == 5
            and "GSEA" in fig["layout"]["title"]["text"])


def test_inhouse_top_set_positive_es(tmp_path):
    from skills.gsea.run_real import run

    path = _ranked_csv(tmp_path)
    top = " ".join(f"G{i}" for i in range(30))  # concentrated at the top of the rank
    fig = run(path, {"engine": "inhouse", "gene_set": top, "set_name": "Top", "n_perm": 200})
    assert _is_three_panel(fig)
    assert _es(fig) > 0.3, "a top-concentrated set should give a strong positive ES"


def test_inhouse_bottom_set_negative_es(tmp_path):
    from skills.gsea.run_real import run

    path = _ranked_csv(tmp_path)
    bottom = " ".join(f"G{i}" for i in range(170, 200))  # concentrated at the bottom
    fig = run(path, {"engine": "inhouse", "gene_set": bottom, "set_name": "Bottom", "n_perm": 200})
    assert _es(fig) < -0.3, "a bottom-concentrated set should give a strong negative ES"


def test_gseapy_single_set(tmp_path):
    pytest.importorskip("gseapy")
    from skills.gsea.run_real import run

    path = _ranked_csv(tmp_path)
    top = " ".join(f"G{i}" for i in range(30))
    fig = run(path, {"engine": "gseapy", "gene_set": top, "set_name": "Top", "n_perm": 200})
    assert _is_three_panel(fig)
    assert _es(fig) > 0.3


def test_gseapy_agrees_with_inhouse_es(tmp_path):
    """Cross-check: gseapy's ES and the in-house weighted-KS ES agree for the same set."""
    pytest.importorskip("gseapy")
    from skills.gsea.run_real import run

    path = _ranked_csv(tmp_path)
    top = " ".join(f"G{i}" for i in range(30))
    a = _es(run(path, {"engine": "gseapy", "gene_set": top, "n_perm": 200}))
    b = _es(run(path, {"engine": "inhouse", "gene_set": top, "n_perm": 200}))
    assert abs(a - b) < 0.05, f"ES disagree: gseapy={a} inhouse={b}"


def test_gseapy_library_mode_table(tmp_path):
    pytest.importorskip("gseapy")
    from gene_sets.library import load_collection
    from skills.contract import run_skill_with_table

    lib = load_collection("curated")
    if not lib:
        pytest.skip("curated gene-set library not built in this checkout")

    # Rank the library's OWN genes so the sets overlap: the first set's members at the top,
    # the rest below — library mode should then recover that set near the top of the table.
    target, target_genes = next(iter(lib.items()))
    rest = sorted({g for genes in lib.values() for g in genes} - set(target_genes))
    ordered = list(target_genes) + rest
    df = pd.DataFrame({"gene": ordered, "log2fc": np.linspace(4.0, -2.0, len(ordered))})
    path = tmp_path / "lib_ranked.csv"
    df.to_csv(path, index=False)

    fig, table = run_skill_with_table("gsea", str(path), {"engine": "gseapy", "gene_sets": "curated", "n_perm": 200})
    assert _is_three_panel(fig)
    assert table and table["columns"] == ["gene set", "NES", "NOM p", "FDR q"]
    assert table["rows"], "library mode should list tested sets"
    # The top-loaded set must be enriched (positive NES). It may not rank #1 because the
    # curated panels share genes (e.g. cilium/phototransduction overlap), so assert on its
    # own row rather than the ranking.
    target_row = next((r for r in table["rows"] if r[0] == target), None)
    assert target_row is not None, f"{target} should be among the tested sets"
    assert target_row[1] is not None and target_row[1] > 0, "top-loaded set should have positive NES"


# --- ranking-metric resolution (milestone review 2026-07-25, finding A5) --------------------------

def test_bare_t_never_substring_matches_a_gene_id_column():
    """A table with no fold-change column must not rank on `entrezgene_id` because it contains 't'."""
    import pandas as pd

    from skills.gsea.run_real import _ranked

    df = pd.DataFrame({
        "GeneID": ["RHO", "ACTB", "GAPDH", "PDE6B", "RPGRIP1", "CRX"],
        "entrezgene_id": [6010, 60, 2597, 5158, 57096, 1406],
        "t": [8.1, -3.2, 0.4, 5.9, -6.7, 2.2],
        "P.Value": [1e-9, 0.002, 0.7, 1e-5, 1e-7, 0.03],
    })
    ranked = _ranked(df, None)
    # limma's moderated t is the ranking metric; the Entrez ids are not.
    assert set(ranked["metric"]) == {8.1, -3.2, 0.4, 5.9, -6.7, 2.2}
    assert ranked["metric"].iloc[0] == 8.1  # descending by signed metric


def test_a_non_numeric_ranking_column_is_an_honest_error_not_a_garbage_ranking():
    import pandas as pd
    import pytest

    from skills.gsea.run_real import _ranked

    # `score` matches by substring but holds labels — coercion would leave nothing usable.
    df = pd.DataFrame({
        "gene": ["RHO", "ACTB", "GAPDH"],
        "score_label": ["high", "low", "mid"],
    })
    with pytest.raises(ValueError, match="does not look like a ranking metric"):
        _ranked(df, None)


def test_run_records_the_engine_and_permutation_count_it_actually_used(tmp_path):
    """The prose cannot state what ran unless the runner writes it down.

    `engine` defaults to `auto` and resolves from what is importable, and `_perm_count` floors the
    library engines at 100 — so both facts are the runner's to record, not the params'. Same shape
    as `meta.significance` / `meta.adaptation`.
    """
    from skills.gsea.run_real import run

    path = _ranked_csv(tmp_path)
    top = " ".join(f"G{i}" for i in range(30))
    fig = run(path, {"engine": "inhouse", "gene_set": top, "n_perm": 200})
    assert fig["layout"]["meta"]["gsea"] == {
        "engine": "inhouse", "n_perm": 200, "fdr_corrected": False,
    }

    # A single pasted set corrects nothing across sets, whichever engine ran.
    pytest.importorskip("gseapy")
    fig = run(path, {"engine": "gseapy", "gene_set": top, "n_perm": 200})
    assert fig["layout"]["meta"]["gsea"]["engine"] == "gseapy"
    assert fig["layout"]["meta"]["gsea"]["fdr_corrected"] is False


def test_inhouse_engine_refuses_library_mode_with_an_actionable_message(tmp_path):
    """The in-house engine scores ONE set, so library mode is impossible for it — and the message
    blamed a missing dependency ("needs gseapy or blitzgsea installed") that is in fact installed.
    Reachable from the UI since `engine` gained a control, so the wrong diagnosis is one a user
    now sees."""
    from skills.gsea.run_real import run

    with pytest.raises(ValueError) as err:
        run(_ranked_csv(tmp_path), {"engine": "inhouse"})   # no gene_set -> library mode
    msg = str(err.value)
    assert "cannot run library mode" in msg
    assert "installed" not in msg, "the environment is not the problem when the engine was chosen"
