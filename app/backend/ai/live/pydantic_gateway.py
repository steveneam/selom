"""Live AI gateway — Pydantic AI structured-output translator (Slice 2).

``pydantic_ai`` is a lazy dep: imported only inside ``_propose_inner``.  The
entire module is safe to import with no pydantic_ai installed — the import
itself carries zero cost, and any ImportError is caught in ``propose``'s outer
try/except so the deterministic core is never on the AI's critical path.

Design: Pydantic AI acts as a *structured-output translator* only — it turns
the NL goal + ActionContext into a Pydantic-validated ``ProposedPlan``.  The S1
spine (ai.execute / routers._run / companions.provenance) remains the SINGLE
authority for validation, approval, execution, and provenance.  The gateway
never calls ``validate_action`` directly, never approves, and never mutates
state (mirrors the RouteVerifier / VisionGateway discipline).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ai.models import Action, ActionContext, ActionPlan, ActionType

if TYPE_CHECKING:
    pass


class ProposedAction(BaseModel):
    """One action proposed by the Pydantic AI translator.

    Maps 1:1 to ``ai.models.Action``; Pydantic validates the ``type`` against
    the closed ``ActionType`` Literal before the gateway returns the plan, so
    the model cannot produce an unregistered action type.
    """

    type: ActionType
    target: str = ""
    payload: dict = {}
    rationale: str = ""


class ProposedPlan(BaseModel):
    """Structured output the AI agent produces.

    An empty ``actions`` list is valid and means the goal was not actionable
    with the current closed vocabulary (the model's honest fallback).
    ``notes`` carries the AI's explanation shown in the pending-changes banner.
    """

    actions: list[ProposedAction] = []
    notes: str = ""


_SYSTEM_PROMPT = (
    "You PROPOSE typed actions from a closed vocabulary; you never execute or approve.\n\n"
    "Allowed action types:\n"
    "  set_param     – target = a parameter name from param_spec; payload = {\"value\": <v>}\n"
    "  add_filter    – target = a parameter name from param_spec; payload = {\"value\": <v>}\n"
    "  remove_filter – target = a parameter name from param_spec; payload = {} (resets to default)\n"
    "  restyle_figure – payload = {\"path\": \"/layout/...\", \"value\": <v>}  (presentation ONLY)\n"
    "  relabel        – payload = {\"path\": \"/layout/... or /data/<i>/<label-key>\", \"value\": <v>}\n\n"
    "Rules:\n"
    "- For set_param / add_filter / remove_filter: target MUST be a parameter listed in the\n"
    "  given param_spec.  Respect the declared min, max, and options exactly.\n"
    "- For restyle_figure / relabel: path MUST point to a layout or trace PRESENTATION key\n"
    "  (marker, line, name, opacity, color, title text…).  NEVER touch /data/<i>/x,\n"
    "  /data/<i>/y, /data/<i>/values, /data/<i>/labels (plotted data arrays) or /layout/meta\n"
    "  (the selom capability contract).  Changing data requires a recompute action instead.\n"
    "- The system validates every action and the USER approves data-recompute changes before\n"
    "  anything runs.  Propose only what the goal needs; return an empty list if nothing applies.\n"
    "- Never invent data values or fabricate analytical results."
)


class PydanticAIGateway:
    """Live gateway: NL goal + ActionContext → Pydantic-validated ``ActionPlan``.

    Pydantic AI is the structured-output *translator* only.  Validation,
    approval, execution, and provenance remain exclusively in the S1 spine.

    Degrades clean on any error (import failure, API error, timeout, missing
    key): ``propose`` returns an empty plan (``NullActionGateway`` semantics)
    and never raises into the loop (Requirement 8).

    Parameters
    ----------
    model:
        Anthropic model name — must accept ``output_config.task_budget``.
    token_budget:
        Per-request token ceiling (maps to ``anthropic_task_budget``).
    timeout_s:
        Wall-clock timeout for the synchronous agent run.  On expiry the
        daemon thread continues in the background and an empty plan is returned.
    """

    def __init__(
        self,
        *,
        model: str = "claude-opus-4-8",
        token_budget: int = 20_000,
        timeout_s: float = 30.0,
    ) -> None:
        self._model = model
        self._token_budget = token_budget
        self._timeout_s = timeout_s

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        """Translate goal + context into a validated ``ActionPlan``.

        Lazy-imports ``pydantic_ai`` so the module is not on the import
        critical path.  Returns an empty plan on any error (degrade-clean).
        """
        try:
            return self._propose_inner(context, goal)
        except Exception:  # noqa: BLE001 — degrade clean, never propagate AI errors
            return ActionPlan(goal=goal, actions=[])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, ctx: ActionContext, goal: str) -> str:
        """Compose a context string for the agent from the ``ActionContext``.

        Includes: stage, skill_id, param_spec (names + constraints only),
        current params, capability_surface summary, data_fit summary, and
        figure_spec shape (keys only — never the full data arrays so the prompt
        stays bounded and no plotted data crosses the wire to the AI).
        """
        import json as _json

        lines: list[str] = [f"Goal: {goal}", f"Stage: {ctx.stage}"]

        if ctx.skill_id:
            lines.append(f"Skill: {ctx.skill_id}")
            try:
                from skills.contract import load_skill

                spec = load_skill(ctx.skill_id)
                param_summary = {
                    name: {
                        k: v
                        for k, v in pdef.items()
                        if k in ("type", "min", "max", "options", "default")
                    }
                    for name, pdef in spec.param_spec.items()
                }
                lines.append(f"param_spec: {_json.dumps(param_summary)}")
            except Exception:  # noqa: BLE001 — param_spec is advisory, degrade clean
                pass

        if ctx.params:
            lines.append(f"Current params: {_json.dumps(ctx.params)}")

        if ctx.capability_surface:
            lines.append(f"Capability surface: {_json.dumps(ctx.capability_surface)}")

        if ctx.data_fit:
            fit_summary = {
                k: ctx.data_fit[k]
                for k in ("score", "confidence", "compatible")
                if k in ctx.data_fit
            }
            lines.append(f"Data fit: {_json.dumps(fit_summary)}")

        if ctx.figure_spec:
            # Shallow summary only — keys, never the plotted data arrays.
            fig_shape = {
                "layout_keys": list(ctx.figure_spec.get("layout", {}).keys()),
                "data_trace_count": len(ctx.figure_spec.get("data", [])),
            }
            lines.append(f"Figure spec (shape): {_json.dumps(fig_shape)}")

        return "\n".join(lines)

    @staticmethod
    def _map_plan(goal: str, proposed: ProposedPlan) -> ActionPlan:
        """Map a validated ``ProposedPlan`` to the canonical ``ActionPlan`` wire type."""
        return ActionPlan(
            goal=goal,
            actions=[
                Action(
                    type=a.type,
                    target=a.target,
                    payload=a.payload,
                    rationale=a.rationale,
                )
                for a in proposed.actions
            ],
            notes=proposed.notes,
        )

    def _propose_inner(self, context: ActionContext, goal: str) -> ActionPlan:
        """Run the Pydantic AI agent with a thread-based timeout guard.

        Any exception (auth error, API error, import error) propagates to the
        outer ``propose`` try/except which degrades to an empty plan.
        """
        from pydantic_ai import Agent
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings

        model_instance = AnthropicModel(self._model)
        model_settings: AnthropicModelSettings = AnthropicModelSettings(
            anthropic_task_budget={"type": "tokens", "total": self._token_budget},
        )
        agent: Agent[None, ProposedPlan] = Agent(
            model_instance,
            output_type=ProposedPlan,
            model_settings=model_settings,
            system_prompt=_SYSTEM_PROMPT,
        )
        prompt = self._build_prompt(context, goal)

        # Thread-based timeout: daemon=True so the hanging thread never blocks
        # process exit; the main thread returns an empty plan on expiry.
        result_holder: list = [None]
        error_holder: list = [None]

        def _do_run() -> None:
            try:
                result_holder[0] = agent.run_sync(prompt)
            except Exception as exc:  # noqa: BLE001
                error_holder[0] = exc

        t = threading.Thread(target=_do_run, daemon=True)
        t.start()
        t.join(timeout=self._timeout_s)

        if t.is_alive():
            # Timeout — return empty plan; daemon thread continues then dies.
            return ActionPlan(goal=goal, actions=[])

        if error_holder[0] is not None:
            raise error_holder[0]  # re-raised; caught by propose()'s except

        return self._map_plan(goal, result_holder[0].output)
