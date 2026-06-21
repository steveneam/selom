"""Engine-spine ANALYZE entry (E4): the runner takes a DataBundle.

``run_bundle_with_table`` is the DataBundle-aware sibling of ``run_skill_with_table`` — both
products flow through ``engine.ingest`` to one classified bundle and then run the skill from it.
Skills are still path-based, so the bundle entry executes from ``bundle.path`` and is therefore
*byte-identical* to the path runner (E4: additive, nothing coerced yet). Stub engine, no heavy deps.
"""

import pytest

from engine.databundle import DataBundle
from engine.ingest import ingest
from reproduction_drive import _default_runner
from skills.contract import run_bundle, run_bundle_with_table, run_skill, run_skill_with_table


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_run_bundle_with_table_is_byte_identical_to_the_path_runner():
    bundle = DataBundle(payload=None, path="unused")
    fig_b, tbl_b = run_bundle_with_table("volcano", bundle, {})
    fig_p, tbl_p = run_skill_with_table("volcano", "unused", {})
    assert fig_b == fig_p
    assert tbl_b == tbl_p


def test_run_bundle_drops_the_table_like_run_skill():
    bundle = DataBundle(payload=None, path="unused")
    assert run_bundle("volcano", bundle, {}) == run_skill("volcano", "unused", {})


def test_run_bundle_requires_a_source_path():
    with pytest.raises(ValueError, match="no source path"):
        run_bundle_with_table("volcano", DataBundle(payload=None, path=None), {})


def test_ingest_sets_the_runner_path_and_runs_from_it(tmp_path):
    p = tmp_path / "de.csv"
    p.write_text("gene,log2FoldChange,padj\nRHO,1.2,0.01\nRPGR,-0.7,0.04\n")
    bundle = ingest(str(p))
    assert bundle.path == str(p)           # the runner handle is the live source path
    assert bundle.source.sha256            # provenance still carries the digest, not the path
    fig_b, _ = run_bundle_with_table("volcano", bundle, {})
    fig_p, _ = run_skill_with_table("volcano", str(p), {})
    assert fig_b == fig_p


# --- reproduction's default runner now loads matched data through engine.ingest ----


def test_default_runner_routes_through_ingest_byte_identical(tmp_path):
    p = tmp_path / "de.csv"
    p.write_text("gene,log2FoldChange,padj\nA,2,0.01\n")
    fig_d, tbl_d = _default_runner("volcano", str(p), {})
    fig_p, tbl_p = run_skill_with_table("volcano", str(p), {})
    assert fig_d == fig_p and tbl_d == tbl_p


def test_default_runner_fails_soft_for_an_unrecognized_path(tmp_path):
    # An exotic data_map override engine.ingest can't load still reaches the skill (path fall-back).
    p = tmp_path / "mystery.bin"
    p.write_bytes(b"\x00\x01\x02")
    fig, _ = _default_runner("volcano", str(p), {})
    assert fig["data"]
