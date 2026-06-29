"""ai/ — the Probabilistic Shell for Selom's deterministic engine spine.

Slice 1: Action Gateway — pure backend, no live LLM. The public surface is:
  models   — Pydantic types (Action, ActionPlan, ActionContext, HelperTurn, …)
  registry — closed ACTION_REGISTRY (the moat-as-data)
  gateway  — ActionGateway Protocol + NullActionGateway + OperatorActionGateway
  execute  — validate_action, apply_plan, commit_recompute
  loop     — run_helper_turn (the bounded propose→validate→stage/apply driver)

Import concrete paths (no barrel re-exports) per the project lib/ convention.
"""
