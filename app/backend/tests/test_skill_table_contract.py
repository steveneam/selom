"""P4-4a — skill table-contract uniformity audit + guard (docs/reproduction-engine/
skill-table-contract.md).

Every in-scope skill must have a *declared* Statistics-table source, so no graded-path skill is
**silently tableless** (a panel that drives but whose golden can never be read back). Three sources
partition the whole catalog:

* **native** — the skill attaches its own ``spec["table"]`` in its runner (stub ``run.py`` and/or the
  heavy ``run_real.py``; ``gsea``/``ssgsea`` attach it conditionally on real data, so the stub shows
  none — the *source* is the truth, asserted below).
* **L3** — no native table, but ``extract.synthesize.synthesize_table`` re-shapes the skill's own
  figure into a canonical table. This set is exactly ``_SYNTHESIZERS`` (the code is the registry).
* **L4-only** — node-link / un-tabulatable skills (``go_graph``/``pathway``/``string_network``) whose
  numbers are edges, not a stats table → the L4 Pro-AI tier; an honest, reviewed gap, not a surprise.

THIS test is the enforcement of that doc: a new skill that is tableless, has no synthesizer, and is
not a reviewed L4-only entry lands in *none* of the three sets and fails the completeness assertion —
forcing a table-source decision before it can ship into a graded path.
"""

from __future__ import annotations

import pytest

from extract.synthesize import _SYNTHESIZERS, synthesize_table
from skills.contract import _skill_dir, run_skill_with_table
from skills.registry import list_skill_ids

# The reviewed audit (s56). NATIVE is asserted to EQUAL the set of skills whose runner attaches
# ``spec["table"]`` (``test_native_classification_matches_source``), so this list cannot drift from
# the code — it is documentation with a mechanical guard, not a hand-maintained guess.
NATIVE = {
    "volcano", "deg", "proteomics_de", "enrichment", "cepo",          # attach in the stub
    "gsea", "ssgsea",                                                  # conditional attach (real data)
    "diff_abundance", "markers", "normalization_qc", "pseudotime_genes",  # attach in run_real only
    "erg_traces", "erg_bwave_bar", "erg_intensity_response", "erg_flicker",  # attach in the stub (proprietary)
}

# The reviewed L4-only allowlist: node-link skills with no faithful table → the L4 Pro-AI tier. A
# skill here has NO native table and NO synthesizer *by design* — ``test_l4_only_is_honestly_tableless``
# proves it, so the allowlist can never hide a skill that actually has (or should have) a table.
L4_ONLY = {"go_graph", "pathway", "string_network"}

# The native skills whose STUB attaches a table with default params (the rest attach only in
# ``run_real`` or conditionally on real data — covered by the source check, not runnable stubless).
STUB_NATIVE = {"volcano", "deg", "proteomics_de", "enrichment", "cepo", "erg_traces",
               "erg_bwave_bar", "erg_intensity_response", "erg_flicker"}


def _attaches_table(skill_id: str) -> bool:
    """True when any runner file in the skill's dir attaches its own ``spec["table"]`` — the
    mechanical native-table signal. Covers ``run.py`` / ``run_real.py`` / ``run_scanpy.py`` and the
    conditional ``if table is not None: spec["table"] = table`` attach. Reads only the skill's own
    dir, so the shared infra (``skills/contract.py``, ``skills/_table.py``) is never miscounted."""
    return any('spec["table"]' in py.read_text(encoding="utf-8")
               for py in _skill_dir(skill_id).glob("*.py"))


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_table_contract_partitions_every_skill():
    """The core guard: native ∪ L3 ∪ L4-only == every shipped skill, the three sets pairwise
    disjoint. A new tableless skill with no synthesizer that isn't a reviewed L4-only entry lands in
    none of them and fails here — there is no silent tableless graded path."""
    all_skills = set(list_skill_ids())
    l3 = set(_SYNTHESIZERS)

    assert NATIVE.isdisjoint(l3), f"native ∩ L3 = {sorted(NATIVE & l3)} (a skill can't be both)"
    assert NATIVE.isdisjoint(L4_ONLY), f"native ∩ L4-only = {sorted(NATIVE & L4_ONLY)}"
    assert l3.isdisjoint(L4_ONLY), f"L3 ∩ L4-only = {sorted(l3 & L4_ONLY)}"

    classified = NATIVE | l3 | L4_ONLY
    unclassified = all_skills - classified
    assert not unclassified, (
        f"tableless skill(s) with no declared table source: {sorted(unclassified)} — give each a "
        f"native spec['table'], an extract.synthesize synthesizer (L3), or add to L4_ONLY if it is "
        f"genuinely un-tabulatable (node-link)."
    )
    stale = classified - all_skills
    assert not stale, f"the audit classifies skill(s) that no longer ship: {sorted(stale)}"


def test_native_classification_matches_source():
    """NATIVE is grounded in code, not a guess: it equals exactly the set of skills whose runner
    source attaches ``spec["table"]``. Adding a native table to a new skill (or removing one) flips
    this until the doc list is updated to match."""
    detected = {s for s in list_skill_ids() if _attaches_table(s)}
    assert detected == NATIVE, (
        f"native-table set drifted from source: in-source-not-doc={sorted(detected - NATIVE)} "
        f"in-doc-not-source={sorted(NATIVE - detected)}"
    )


@pytest.mark.parametrize("skill_id", sorted(STUB_NATIVE))
def test_stub_native_skill_yields_a_table(skill_id):
    """The stub-visible native skills really do emit a non-empty Statistics table from their stub
    (so the own-data run path and the reproduction reader get a real table, not a synthesized one)."""
    _figure, native = run_skill_with_table(skill_id, "unused", {})
    assert native is not None and native.get("columns"), f"{skill_id} stub attached no native table"


@pytest.mark.parametrize("skill_id", sorted(L4_ONLY))
def test_l4_only_is_honestly_tableless(skill_id):
    """A reviewed L4-only skill must have NO native table AND NO synthesizer — else it belongs in
    native/L3, not the AI tier. This is what stops the allowlist from silently absorbing a skill that
    actually has (or should have) a table."""
    assert skill_id not in _SYNTHESIZERS, f"{skill_id} has an L3 synthesizer — it is not L4-only"
    assert not _attaches_table(skill_id), f"{skill_id} attaches a native table — it is not L4-only"
    figure, native = run_skill_with_table(skill_id, "unused", {})
    assert native is None, f"{skill_id} emitted a native table at runtime"
    assert synthesize_table(skill_id, figure) is None, f"{skill_id} unexpectedly synthesizes a table"
