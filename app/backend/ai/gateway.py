"""ActionGateway Protocol + implementations (Slice 1 — no live LLM).

AI proposes, never originates a mutation.  The gateway is a subroutine of the
deterministic loop (``ai.loop.run_helper_turn``); the deterministic core is never
on the AI's critical path.  A live ``PydanticAIGateway`` slots in behind this
Protocol in Slice 2 without touching the loop or the registry.

Mirrors the ``RouteVerifier`` / ``VisionGateway`` discipline (``extract/routing/
verify.py``, ``extract/vision.py``): a typed Protocol with an always-available
no-op default and a replayable operator stand-in for CI-safe testing.

S4 extension: the ``explain`` method supports the informational helper path
(``POST /ai/explain``).  It is NOT a mutation — it produces explanatory text grounded
in deterministic data passed by the caller (scorecard / sweep space) and never goes
through the action registry or ``apply_plan``.  With ``NullActionGateway`` the
fallback is a short deterministic summary of the passed data; with the live gateway
it is AI-generated text grounded in the same data.  Degrade-clean in both directions.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai.models import ActionContext, ActionPlan


# ---------------------------------------------------------------------------
# Deterministic fallbacks for explain (used by Null + Operator gateways).
# ---------------------------------------------------------------------------

def _is_num(x) -> bool:
    """A real number (a ``bool`` is not a sweep value)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _fmt_num(n) -> str:
    """Trim a number for prose (``3.0`` → ``3``, ``0.01`` → ``0.01``)."""
    return f"{n:g}"


def _knob_metrics(spec: dict, ptype) -> tuple[float, str, int]:
    """``(breadth, reason, kind)`` for one declared sweep knob.

    Grounded ONLY in the knob's *declared* value space — it ranks how much there is
    to sweep, never a claim about figure impact (which can't be known without running).
    ``kind`` is the sort priority (numeric 3 > select 2 > switch 1 > unknown 0); a missing
    ``type`` is inferred from the presence of ``min``/``max`` (numeric) or ``options`` (select).

    ``ptype`` is the cross-lane FE ``ParamField['type']`` string (``lib/catalog/params.ts``):
    ``range``/``number`` → numeric, ``select`` → select, ``switch`` → switch, ``text`` → the
    unknown/no-range bucket (ranked last). A NEW FE param type not listed here falls through to
    breadth-0 and ranks last (fails soft, never raises). ``test_knob_metrics_handles_every_paramfield_type``
    pins this mapping so a change trips a test rather than silently dropping a sweepable knob.
    """
    mn, mx, st = spec.get("min"), spec.get("max"), spec.get("step")
    has_range = _is_num(mn) and _is_num(mx) and mx > mn
    if ptype in ("range", "number") or (ptype is None and has_range):
        if has_range:
            step = st if (_is_num(st) and st > 0) else (mx - mn) / 10
            steps = max(1, round((mx - mn) / step))
            return steps, f"widest declared range ({_fmt_num(mn)}–{_fmt_num(mx)}, ~{steps} steps)", 3
        return 1, "numeric knob", 3
    opts = spec.get("options")
    n_opts = len(opts) if isinstance(opts, list) else 0
    if ptype == "select" or (ptype is None and n_opts):
        return n_opts, f"{n_opts} options", 2
    if ptype == "switch":
        return 2, "on / off", 1
    return 0, "no declared range", 0


def rank_sweep_space(sweep_space: dict | None) -> list[dict]:
    """Rank the sweepable knobs by declared value-space breadth — the grounded recommender.

    Pure data → reproducible: the same ranking regardless of gateway, so the live AI's
    prose can vary while the structured picks the UI preselects stay deterministic.  Sorts
    by kind priority (numeric > select > switch > unknown), then breadth desc, then label;
    returns the top three as ``{param, label, reason}`` (never fabricates a value).
    """
    if not isinstance(sweep_space, dict):
        return []
    ranked: list[dict] = []
    for key, spec in sweep_space.items():
        spec = spec if isinstance(spec, dict) else {}
        label = spec.get("label") or key
        breadth, reason, kind = _knob_metrics(spec, spec.get("type"))
        ranked.append({"param": key, "label": label, "reason": reason, "_b": breadth, "_k": kind})
    ranked.sort(key=lambda r: (-r["_k"], -r["_b"], str(r["label"]).lower()))
    return [{"param": r["param"], "label": r["label"], "reason": r["reason"]} for r in ranked[:3]]


def _deterministic_explain(request_type: str, data: dict, goal: str) -> str:
    """Build a deterministic explanation from the caller-supplied data.

    Grounded entirely in the ``data`` dict passed by the caller (a scorecard or a
    sweep-space dict) — never fabricated.  Used as the fallback when no live
    gateway is available and as the TestModel stand-in in CI.
    """
    if request_type == "explain_score":
        sc = data.get("scorecard") or {}
        score = sc.get("score", "n/a")
        tier = sc.get("tier", "unknown")
        conf = sc.get("selom_confidence")
        # Prefer an explicit ``panels`` list; else fall back to a ``panel_count`` scalar (what
        # the FE sends). Do NOT default ``panels`` to ``[]`` — an empty list would shadow the
        # scalar and always read 0 (caught on the live engine, not the green suite).
        panels = sc.get("panels")
        n_panels = len(panels) if isinstance(panels, list) else sc.get("panel_count", 0)
        head = f"Reproducibility {score}/100 (tier: {tier})"
        if conf is not None:
            head += f", Selom confidence {conf}/100"
        summary = f"{head}. {n_panels} panel(s) scored."
        findings = sc.get("findings") if isinstance(sc.get("findings"), dict) else {}
        bits = []
        if findings.get("reproduced"):
            bits.append(f"{findings['reproduced']} reproduced")
        if findings.get("paper_irreproducible"):
            bits.append(f"{findings['paper_irreproducible']} paper-irreproducible")
        if bits:
            summary += " " + ", ".join(bits) + "."
        return summary + " Improve by supplying data that matches the paper's figures more closely."
    if request_type == "propose_sweep":
        suggestions = rank_sweep_space(data.get("sweep_space"))
        if not suggestions:
            return (
                "No sweep space provided — specify parameters and their ranges to sweep."
            )
        parts = ", ".join(f"{s['label']} ({s['reason']})" for s in suggestions)
        return (
            f"Suggested sweeps: {parts}. "
            "Numeric knobs with the widest declared range vary the result the most — start there."
        )
    return "unavailable"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ActionGateway(Protocol):
    """The AI write-path seam.

    ``propose`` returns an ActionPlan drawn from the closed ACTION_REGISTRY.
    ``explain`` returns grounded explanatory text (NOT a mutation — not an action).
    ``model_id`` identifies the actor that produced the plan — stamped into provenance
    so the audit log records which model (or operator/null stand-in) proposed the action.
    A gateway that returns an empty plan / a deterministic string (the default) leaves
    every existing behaviour unchanged (zero-regression guarantee).
    """

    model_id: str

    def propose(self, context: ActionContext, goal: str) -> ActionPlan: ...

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        """Return grounded explanatory text for an informational helper request.

        ``request_type`` is one of ``"explain_score"`` / ``"propose_sweep"``.
        ``data`` carries the deterministic artifacts grounding the explanation
        (scorecard dict, sweep-space dict).  Must never fabricate data values.
        Degrade-clean: an unavailable gateway returns a deterministic fallback.
        """
        ...


# ---------------------------------------------------------------------------
# Null gateway (always-available default)
# ---------------------------------------------------------------------------

class NullActionGateway:
    """The always-available default: no gateway, empty plan / deterministic text.

    With NullActionGateway as the active gateway, ``run_helper_turn`` returns a
    HelperTurn with no actions, no staged params, and no gaps — identical to
    pre-spec behaviour (the offline / degraded-gracefully guarantee).

    ``explain`` returns a short deterministic summary grounded in the passed data
    so the informational endpoint degrades gracefully rather than returning nothing.
    """

    model_id: str = "null"

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return ActionPlan(goal=goal, actions=[])

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        return _deterministic_explain(request_type, data, goal)


# ---------------------------------------------------------------------------
# Operator gateway (CI-safe replay stand-in)
# ---------------------------------------------------------------------------

class OperatorActionGateway:
    """Claude-as-gateway dev/dogfood stand-in: replays operator-recorded ActionPlans.

    Plans are keyed by goal string.  A goal with no recorded plan returns an empty
    plan (NullActionGateway semantics) — the seam never fabricates an action.
    Use ``record`` to build up the replay set before passing this to the loop.

    ``record_explanation`` / ``explain`` mirror the same replay discipline for
    informational helper requests (``POST /ai/explain``): a recorded text is
    returned; unrecorded goals fall back to the deterministic summary.

    This is the CI-safe, LLM-free implementation used in tests; it lets the entire
    propose→validate→stage/apply loop and the informational path run deterministically.
    """

    model_id: str = "operator"

    def __init__(
        self,
        plans: dict[str, ActionPlan] | list[ActionPlan] | None = None,
    ) -> None:
        items = plans.values() if isinstance(plans, dict) else (plans or [])
        self._plans: dict[str, ActionPlan] = {p.goal: p for p in items}
        self._explanations: dict[str, str] = {}

    def record(self, goal: str, plan: ActionPlan) -> None:
        """Add or replace a plan for ``goal`` (used as the operator works through a run)."""
        self._plans[goal] = plan

    def record_explanation(self, request_type: str, goal: str, text: str) -> None:
        """Add or replace an explanation for the given request_type + goal pair."""
        self._explanations[f"{request_type}:{goal}"] = text

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return self._plans.get(goal, ActionPlan(goal=goal, actions=[]))

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        key = f"{request_type}:{goal}"
        return self._explanations.get(key, _deterministic_explain(request_type, data, goal))
