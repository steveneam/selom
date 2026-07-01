"""Engine spine — deterministic ANALYZE-stage PARAM recommendations (Layer A Auto-tune).

The one-click "Auto-tune" button (`docs/auto-tune/spec.md`) fills a skill's inputs with the
best-practice defaults **with NO AI** — it works with the gateway off, carries no ✨ marker, and is
human-attributed (the user clicks it, reviews the diff, and re-runs). This module is the analyze
stage's deterministic source (peer of :mod:`engine.route` and :mod:`engine.questionnaire`).

The baseline is exactly the skill's ``param_spec`` defaults (:func:`skills.contract.defaults`) — for
most skills those already ARE best practice, so the recommendation equals the defaults. On top of that
a **small, curated** rule set (:func:`_apply_curated`) lightly moves a knob when best practice clearly
differs from the raw default (e.g. ``umap_scrna`` selects ~2000 highly-variable genes, not "all
genes"). Every recommended value is clamped to and validated against the skill's own ``param_spec`` —
the button never emits an out-of-range knob.

Scope boundary (deliberate — no parallel path): the **experimental design** params
(``reference``/``treatment``/``condition_col``/``sample_col``) are the **ingest** stage's job — the
intake questionnaire maps the detected design onto those params (FE ``lib/intake/design.ts``,
INTAKE-DESIGN). This analyze recommender does NOT re-map the design (that would be a second mapper that
drifts from the questionnaire's); it tunes the pure ANALYSIS knobs. Both feed the one shared pending
queue, so there is no double-stage. See ``docs/auto-tune/spec.md`` §Design (deviation from R4's deg
bullet, in the direction of no-parallel-path).

Fail-soft: any error in the curated layer degrades to the all-static baseline — never an exception to
the caller.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from skills.contract import SkillSpec, defaults, load_skill, validate_param_ranges


class ParamRec(BaseModel):
    """One recommended parameter: the value, the static default it came from, and why.

    ``scaled`` is True only when a curated rule moved ``value`` off the static ``default`` — the FE
    uses it (plus a value≠current check) to decide which recs to stage, and ``why`` explains the
    change. A rec with ``value == default`` and ``scaled=False`` is the honest static baseline.
    """

    key: str
    value: Any
    default: Any
    why: str = "skill default"
    scaled: bool = False


class ParamRecs(BaseModel):
    """The full recommended param set for one skill given the data context."""

    skill_id: str
    recs: list[ParamRec] = Field(default_factory=list)
    note: str = ""


class RecommendContext(BaseModel):
    """The data DESCRIPTION the FE forwards (mirrors the data-aware-routing context) — never a
    verdict. All optional: any missing field simply degrades its rule to the static default.

    ``design`` is the persisted :class:`engine.questionnaire.DesignHints` (as a dict); v1's curated
    rules do not consume it (design params belong to ingest) but it is accepted for forward
    compatibility so a later curated rule can read replicate counts without a contract change.
    """

    data_columns: list[str] | None = None
    data_kind: str | None = None
    data_n_numeric_cols: int | None = None
    design: dict | None = None


def recommend_params(skill_id: str, ctx: RecommendContext) -> ParamRecs:
    """Deterministically recommend best-practice params for ``skill_id`` given the data context.

    Raises ``FileNotFoundError`` for an unknown skill (the router maps it to 404). The curated layer
    is fail-soft: any error there degrades to the static ``param_spec`` baseline.
    """
    spec = load_skill(skill_id)  # FileNotFoundError for an unknown skill → 404 at the router
    recs: dict[str, ParamRec] = {
        k: ParamRec(key=k, value=v, default=v) for k, v in defaults(spec).items()
    }
    try:
        _apply_curated(skill_id, spec, ctx, recs)
    except Exception:  # noqa: BLE001 — a recommendation helper must never break; fall back to defaults
        recs = {k: ParamRec(key=k, value=v, default=v) for k, v in defaults(spec).items()}
    # R3 — never emit an invalid value: a rec that somehow fails the spec's own range/type/options
    # check reverts to the static default (defensive; _clamp already keeps curated values in range).
    for key, rec in list(recs.items()):
        if validate_param_ranges(spec, {key: rec.value}):
            recs[key] = ParamRec(key=key, value=rec.default, default=rec.default)
    return ParamRecs(skill_id=skill_id, recs=list(recs.values()), note=_summary_note(recs))


# --- the curated rule set (small + documented; adding a rule is a localized change here) ------------

def _apply_curated(skill_id: str, spec: SkillSpec, ctx: RecommendContext,
                   recs: dict[str, ParamRec]) -> None:
    """The only place skill-specific best-practice overrides live (spec §R4). Each rule cites its
    basis; anything a rule can't derive stays the static default. Keep this SMALL — full per-knob
    data-scaling / AI search is explicitly out of scope (``docs/auto-tune/spec.md`` D3)."""
    # umap_scrna / cluster: select the top highly-variable genes before PCA. Standard scRNA practice
    # (Seurat/scanpy) is ~2000 HVGs; the raw default here is 0 (= all genes), which the param's own
    # note flags as sub-optimal ("~2000 recommended"). Data-independent best practice, clamped to range.
    if skill_id in ("umap_scrna", "cluster"):
        _set(recs, spec, "n_hvg", 2000,
             "select the top ~2000 highly-variable genes before PCA (standard scRNA practice)")


def _set(recs: dict[str, ParamRec], spec: SkillSpec, key: str, value: Any, why: str) -> None:
    """Set a curated recommendation, clamped to the param's ``[min, max]``. A no-op when the key isn't
    in the spec or the clamped value equals the static default (keep the honest baseline rec)."""
    entry = spec.param_spec.get(key)
    if entry is None or key not in recs:
        return
    value = _clamp(entry, value)
    if value == recs[key].default:
        return
    recs[key] = ParamRec(key=key, value=value, default=recs[key].default, why=why, scaled=True)


def _clamp(entry: dict, value: Any) -> Any:
    """Clamp a numeric value into the param_spec's ``[min, max]`` (bools/strings pass through)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    lo, hi = entry.get("min"), entry.get("max")
    if lo is not None:
        value = max(value, lo)
    if hi is not None:
        value = min(value, hi)
    return value


def _summary_note(recs: dict[str, ParamRec]) -> str:
    n = sum(1 for r in recs.values() if r.scaled)
    if n == 0:
        return "These are the best-practice defaults for this skill."
    return f"Set {n} best-practice input{'s' if n != 1 else ''} for your data — review below, then re-run."
