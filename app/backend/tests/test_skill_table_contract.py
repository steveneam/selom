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

from extract.synthesize import ALSO_SYNTHESIZE, _SYNTHESIZERS, synthesize_table
from skills._table import as_tables
from skills.contract import _skill_dir, run_skill_with_table
from skills.registry import list_skill_ids

# The reviewed audit (s56). NATIVE is asserted to EQUAL the set of skills whose runner attaches
# ``spec["table"]`` (``test_native_classification_matches_source``), so this list cannot drift from
# the code — it is documentation with a mechanical guard, not a hand-maintained guess.
NATIVE = {
    "volcano", "deg", "proteomics_de", "enrichment", "cepo",          # attach in the stub
    "mixing_metrics",                                                  # attach in the stub + run_real
    "gsea", "ssgsea",                                                  # conditional attach (real data)
    "diff_abundance", "markers", "normalization_qc", "pseudotime_genes",  # attach in run_real only
    "erg_traces", "erg_bwave_bar", "erg_intensity_response", "erg_flicker",  # attach in the stub (proprietary)
    "facs_gating",                                                     # attach in the stub + run_real
    "boxplot", "violin",                                               # conditional attach (pairs=)
    # Lane B. Each is native and UNCONDITIONAL: the numbers are the point of the figure, and in
    # every case they are irrecoverable from the drawn shapes. A Venn region count is printed but
    # the per-set totals are not; a forest bar's endpoints are pixels, not values, and which of the
    # three derivations produced them is nowhere on the canvas; a Q-Q's λ is a property of the whole
    # ranking. Synthesis (L3) could recover none of those honestly.
    "venn", "forest", "qq",
    # `line` — the per-point mean, spread and n. n is the number that judges the band and
    # is nowhere on the canvas, so it cannot be synthesized from the drawn shapes.
    "line",
    # Lane B continued (§3.2 rows 7/8/10/11). Native and UNCONDITIONAL, same test as above: is the
    # number recoverable from the drawn shapes? In each case no, and the un-recoverable number is
    # the one a reader needs to judge the figure.
    #   lollipop — the bootstrap CI bounds are asymmetric, so neither end is derivable from the
    #     dot's position, and n (which decides whether an interval exists at all) is not drawn.
    #   confusion — the marginals, and the agreement/kappa *refusal*. A normalized cell shows a
    #     percentage; the count behind it is exactly what normalization hides.
    #   slope — the paired p, and the up/down split. The split is the finding a flat mean conceals,
    #     and counting segments off a rendered image is not a recovery.
    #   ridge — the five-number summary and the BANDWIDTH. A curve is as bimodal as its bandwidth
    #     allows, so a density plot that does not disclose its smoothing cannot be checked.
    "lollipop", "confusion", "slope", "ridge",
}

# `NATIVE_L3_BOTH` was renamed and SPLIT, 2026-08-05, by the change that made half of it false.
#
# The old set named `boxplot`/`violin` as the one native-AND-L3 overlap, justified by the two
# sources covering disjoint RUNS: with `pairs=` the native table carried p-values that exist nowhere
# in the figure except as stars, and without it L3 synthesized what the figure does encode. That
# disjointness was never about the science — it existed ONLY because the wire carried one table
# (docs/stats-tables/spec.md D3). D3 predicted the exception would have "no reason left" once two
# tables fit. That is true for `boxplot` and NOT true for `violin`, which is the finding:
#
#   - `boxplot` now attaches BOTH on the same run, declared where it is EXECUTED rather than merely
#     documented (`extract.synthesize.ALSO_SYNTHESIZE`). That is the stronger home — the old set was
#     a note the runtime happened to agree with; this one IS the runtime.
#   - `violin` stays an across-RUNS overlap. Its synthesized table is a PubMed marker call read back
#     out of a figure annotation, and that annotation is a live network lookup — so the table is not
#     deterministically producible and cannot be appended behind a guard that can check it. See the
#     reason at `ALSO_SYNTHESIZE`; it is blocked on NEXT#10(b), not on this contract.
#
# So the partition still needs an overlap allowance, and `ALSO_SYNTHESIZE` is a SUBSET of it: every
# skill that attaches both on one run is by definition allowed to be both.
NATIVE_L3_OVERLAP = {"boxplot", "violin"}

# The reviewed L4-only allowlist: node-link skills with no faithful table → the L4 Pro-AI tier. A
# skill here has NO native table and NO synthesizer *by design* — ``test_l4_only_is_honestly_tableless``
# proves it, so the allowlist can never hide a skill that actually has (or should have) a table.
L4_ONLY = {"go_graph", "pathway", "string_network"}

# The native skills whose STUB attaches a table with default params (the rest attach only in
# ``run_real`` or conditionally on real data — covered by the source check, not runnable stubless).
STUB_NATIVE = {"volcano", "deg", "proteomics_de", "enrichment", "cepo", "mixing_metrics", "erg_traces",
               "erg_bwave_bar", "erg_intensity_response", "erg_flicker", "facs_gating",
               "venn", "forest", "qq", "line"}


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

    overlap = (NATIVE & l3) - NATIVE_L3_OVERLAP
    assert not overlap, (
        f"native ∩ L3 = {sorted(overlap)} — a skill declares ONE table source unless it can "
        f"genuinely be both; then add it to NATIVE_L3_OVERLAP, and to "
        f"extract.synthesize.ALSO_SYNTHESIZE too if it attaches both on the SAME run."
    )
    assert ALSO_SYNTHESIZE <= NATIVE_L3_OVERLAP, (
        f"{sorted(ALSO_SYNTHESIZE - NATIVE_L3_OVERLAP)} append L3 synthesis to a native table but "
        f"are not declared as a native∩L3 overlap — the two declarations cannot disagree."
    )
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


@pytest.mark.parametrize("skill_id", sorted(ALSO_SYNTHESIZE))
def test_also_synthesize_entries_really_want_both_tables(skill_id):
    """The opt-in must EARN itself, or `ALSO_SYNTHESIZE` becomes a hole in the partition — somewhere
    to park a skill that is simply double-classified.

    An entry has to prove all three: a working L3 synthesizer, a native table that appears when
    `pairs=` asks a question the figure cannot answer, and the two carrying DIFFERENT numbers. The
    last one is the point of the whole opt-in: if synthesis could reproduce the native table there
    would be nothing to append, and appending it would just print the same numbers twice under a
    "Computed by Selom" badge."""
    assert skill_id in _SYNTHESIZERS, f"{skill_id} has no L3 synthesizer to append"

    _fig, default_native = run_skill_with_table(skill_id, "unused", {})
    assert default_native is None, (
        f"{skill_id} attaches a native table with DEFAULT params, so synthesis has nothing to add "
        f"that the fill-when-absent path would not already cover"
    )

    # The stub groups differ per skill, so ask for a pair drawn from the figure it just built.
    names = [t.get("name") for t in _fig.get("data", []) if t.get("name")]
    assert len(names) >= 2, f"{skill_id} stub has too few groups to test a pair"
    fig2, native = run_skill_with_table(skill_id, "unused", {"pairs": f"{names[0]}~{names[1]}"})
    assert native is not None and native.get("columns"), (
        f"{skill_id} drew stars from `pairs=` but attached no table — the p-values behind those "
        f"stars exist nowhere else in the figure"
    )

    synth = synthesize_table(skill_id, fig2)
    assert synth is not None, f"{skill_id} synthesizer returned nothing for its own pairs= figure"
    assert synth["columns"] != native["columns"], (
        f"{skill_id}'s synthesized table has the same columns as its native one — appending it "
        f"would print the same result twice, which is the noise this opt-in is gated to avoid"
    )
    assert synth.get("synthesized") is True, (
        f"{skill_id}'s appended table must carry the synthesized flag: inline in a list it is the "
        f"ONLY thing telling the reproduction reader to score it at reduced confidence"
    )


@pytest.mark.parametrize("skill_id", sorted(STUB_NATIVE))
def test_stub_native_skill_yields_a_table(skill_id):
    """The stub-visible native skills really do emit a non-empty Statistics table from their stub
    (so the own-data run path and the reproduction reader get a real table, not a synthesized one).

    Narrowed with ``as_tables`` rather than by ``.get`` on the raw value (D1): a skill attaching a
    list would otherwise fail with ``AttributeError`` on ``list.get`` — the union sprouting at a
    call site, in a test, which is exactly the shape the normalizer exists to stop."""
    _figure, native = run_skill_with_table(skill_id, "unused", {})
    tables = as_tables(native)
    assert tables, f"{skill_id} stub attached no native table"
    assert all(t.get("columns") for t in tables), f"{skill_id} attached an empty table"


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
