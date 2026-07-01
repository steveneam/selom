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

import json
from pathlib import Path
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
    if request_type == "grade_advice":
        from ai.grade import grade_card

        card = grade_card(data.get("stats"))
        if card:
            return card
        skill = (data.get("stats") or {}).get("skill_id") or "this analysis"
        return (
            f"Statistics for {skill}: the test and its assumptions depend on the skill and its "
            "parameters. Check that your data meets the test's assumptions (replicates, independence, "
            "input scale) before trusting the p-values, and switch tests if it doesn't."
        )
    if request_type in ("draft_methods", "draft_legend"):
        # The deterministic draft IS the run's own methods/legend prose, returned VERBATIM. This is the
        # honesty lever (docs/methods-draft/spec.md): gateway-off returns the deterministic draft
        # (`source="deterministic"`, no ✨), and it is the fallback the live gateway's polish is
        # compared against — a no-op polish stays `deterministic`, never a false ✨.
        return data.get("base_text") or ""
    return "unavailable"


# ---------------------------------------------------------------------------
# Live-gateway explain prompt (shared by both live gateways — NEXT#3 tightening)
#
# The live model was paraphrasing schema-less numbers (calling `panel_count`
# "reviewers"). The fix is a labelled prompt + a system rule that forbids renaming
# or inventing entities — used identically by VercelAIGateway and PydanticAIGateway
# so the two cannot drift. The deterministic fallback above is untouched.
# ---------------------------------------------------------------------------

EXPLAIN_SYSTEM_PROMPT = (
    "You are an analytical explainer for a scientific figure-reproduction tool. "
    "You explain or suggest based ONLY on the structured data provided — you never "
    "fabricate analytical results or values. Use each field with EXACTLY the meaning "
    "given in the prompt; do NOT rename, re-interpret, or translate a field into a "
    "different concept, and do NOT introduce entities that are not in the data "
    "(there are no reviewers, comments, ratings, authors, or users here). "
    "Be concise (≤120 words)."
)


def build_explain_prompt(request_type: str, data: dict, goal: str) -> str:
    """The labelled user prompt for a live ``explain`` call — grounds each field by name.

    Lists the meaning of every field the model will see (so ``panel_count`` is "figure
    panels graded", never "reviewers") and appends the literal JSON so the values are
    exact. Used by both live gateways; the deterministic path does not need it.
    """
    lines = [f"Request: {request_type}", f"User goal: {goal or '(none)'}"]
    if request_type == "explain_score":
        lines += [
            "The data is a reproducibility SCORECARD for one paper's figures.",
            "Field meanings (use these EXACTLY; do not rename or re-interpret):",
            "- score: reproducibility score 0-100 (can the figure be regenerated from the data).",
            "- tier: the reproducibility tier label for that score.",
            "- selom_confidence: 0-100 confidence in OUR OWN reconstruction (a property of the tool).",
            "- panel_count: the NUMBER OF FIGURE PANELS graded — NOT reviewers, comments, or people.",
            "- findings: counts of outcome categories (e.g. reproduced, paper_irreproducible).",
            "- coverage: a plain-language note on what was covered.",
            "Explain what the score means and how to improve reproducibility, grounded only in these values.",
        ]
    elif request_type == "propose_sweep":
        lines += [
            "The data is the declared parameter SWEEP SPACE for a skill; each key is a tunable knob.",
            "Each knob carries: label, type (range/number/select/switch), and its value space "
            "(min/max/step, options, or current value).",
            "Suggest which parameter(s) are most worth sweeping and why, grounded ONLY in the declared "
            "value spaces — you cannot claim figure impact without running. Do not invent knobs not listed.",
        ]
    elif request_type == "grade_advice":
        lines += [
            "The data describes the STATISTICAL METHOD of a figure (its skill_id and, for deg, its mode).",
            "Explain which statistical test and multiple-testing correction it uses, its key "
            "assumptions, and when a different test would be more appropriate — grounded ONLY in the "
            "method described. ADVISORY only: never tell the user you changed or applied anything.",
        ]
    elif request_type == "draft_methods":
        lines += [
            "The data carries base_text: a figure's deterministic, publication-ready METHODS paragraph.",
            "POLISH base_text to the user's goal (tighten wording, match a journal's tone) and return "
            "ONLY the rewritten methods prose — no preamble, no commentary. PRESERVE every number, "
            "threshold, parameter value, statistical test, and tool/citation name EXACTLY; invent "
            "nothing and drop nothing factual. If the goal is empty or you cannot improve it, return "
            "base_text unchanged.",
        ]
    elif request_type == "draft_legend":
        lines += [
            "The data carries base_text: a figure's deterministic, publication-ready LEGEND (caption).",
            "POLISH base_text to the user's goal (tighten wording, match a journal's caption style) and "
            "return ONLY the rewritten caption prose — no preamble, no 'Figure N.' number, no "
            "commentary. PRESERVE every number, threshold, group/contrast name, and quantity EXACTLY; "
            "invent nothing and drop nothing factual. If the goal is empty or you cannot improve it, "
            "return base_text unchanged.",
        ]
    lines.append(f"Data (JSON): {json.dumps(data, indent=2)}")
    return "\n".join(lines)


def _operator_input_key(request_type: str, data: dict) -> str | None:
    """Derive a stable per-INPUT key for an operator explain lookup.

    The FE sends the same ``goal`` (or none) for every paper's "Explain this score" — only
    the input data differs — so the operator keys on something that identifies the input, not
    the goal: a scorecard's ``paper_id`` (the showcase slug rpgrip1 / jev / hani) for
    ``explain_score``, the ``skill_id`` for ``propose_sweep``. Returns ``None`` when no
    identifying field is present (the caller then falls back to the goal key, then deterministic).
    """
    if request_type == "explain_score":
        sc = data.get("scorecard") or {}
        key = sc.get("paper_id") or sc.get("slug")
        return str(key) if key else None
    if request_type == "propose_sweep":
        key = data.get("skill_id") or (data.get("sweep_space") or {}).get("_skill_id")
        return str(key) if key else None
    if request_type == "grade_advice":
        st = data.get("stats") or {}
        key = st.get("skill_id")
        if not key:
            return None
        # deg's advice differs by mode → key includes it so one recording per (skill, mode) is possible.
        return f"{key}:{st['mode']}" if st.get("mode") else str(key)
    if request_type in ("draft_methods", "draft_legend"):
        # Key on the figure's skill (the endpoint threads `skill_id` into `data`, as the other requests
        # do) so one recording lights up each skill's polished methods/legend demo. `None` → deterministic.
        key = data.get("skill_id")
        return str(key).split(".")[-1] if key else None
    return None


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

    @classmethod
    def from_recordings(cls, path: str | None = None) -> "OperatorActionGateway":
        """Seed an operator gateway from a Claude-authored recordings JSON file.

        This is the dev-default / canned-demo path (``SELOM_AI_GATEWAY=operator``): the
        recorded outputs let the AI surfaces light up as ✨AI with **zero credit** spent
        (the demo engine, [[selom-pricing-demo-strategy]]). ``path=None`` resolves to the
        bundled ``ai/recordings/explain.json``. A missing / unreadable / malformed file
        degrades clean to an empty operator (Null semantics until something is recorded) —
        it never raises at startup.

        File schema::

            {"explanations": [{"request_type": "explain_score", "key": "rpgrip1",
                               "text": "…"}],
             "plans": [{"goal": "…", "actions": [{"type": "set_design", "target": "design",
                                                  "payload": {"condition": "…"}}]}]}

        Explanations are keyed ``request_type:key`` where ``key`` is the per-INPUT id
        (see :func:`_operator_input_key`); ``plans`` are goal-keyed :class:`ActionPlan`s replayed
        by :meth:`propose` (the canned demo for a scripted goal, e.g. the ingest design refiner).
        """
        gw = cls()
        resolved = path or str(Path(__file__).resolve().parent / "recordings" / "explain.json")
        try:
            with open(resolved, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            return gw
        if not isinstance(doc, dict):
            return gw
        for entry in doc.get("explanations") or []:
            if not isinstance(entry, dict):
                continue
            rt, key, text = entry.get("request_type"), entry.get("key"), entry.get("text")
            if rt and key and text:
                gw._explanations[f"{rt}:{key}"] = text
        # Propose plans (goal-keyed). A malformed plan must never break startup — skip it
        # (degrade-clean), the same policy the explanations loop follows.
        for entry in doc.get("plans") or []:
            if not isinstance(entry, dict):
                continue
            try:
                plan = ActionPlan.model_validate(entry)
            except Exception:  # noqa: BLE001 — a bad recording degrades to no plan, never a crash
                continue
            gw._plans[plan.goal] = plan
        return gw

    def record(self, goal: str, plan: ActionPlan) -> None:
        """Add or replace a plan for ``goal`` (used as the operator works through a run)."""
        self._plans[goal] = plan

    def record_explanation(self, request_type: str, goal: str, text: str) -> None:
        """Add or replace an explanation for the given request_type + goal pair."""
        self._explanations[f"{request_type}:{goal}"] = text

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return self._plans.get(goal, ActionPlan(goal=goal, actions=[]))

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        """Return a recorded explanation, keyed by INPUT first then goal; else deterministic.

        Tries the per-input key (e.g. ``explain_score:rpgrip1``) so one recordings file lights
        up each showcase paper distinctly, then the legacy ``request_type:goal`` key (the
        programmatic ``record_explanation`` path), then the grounded deterministic fallback.
        """
        for candidate in (_operator_input_key(request_type, data), goal):
            if candidate is not None:
                recorded = self._explanations.get(f"{request_type}:{candidate}")
                if recorded is not None:
                    return recorded
        return _deterministic_explain(request_type, data, goal)
