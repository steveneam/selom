# Provenance stamping chokepoint — one server-controlled AI-write attribution

_2026-06-30 · NEXT#1 (hard pre-launch gate). The AI write-path's integrity invariant kept breaking
across the AI-Helpers initiative (the gauntlet caught attribution breaks **3×**) and `/ai/apply` STILL
trusts client-stamped attribution. This funnels every AI write through ONE server-controlled stamp that
derives `actor`/`model`/`approved_by`/`approved_at` itself and never trusts the caller.
[[selom-provenance-stamping-chokepoint]]_

## The hole (confirmed)

- **FE** `lib/ai/proposals.ts::approvedActions()` builds the entire `ai_actions[]` client-side, stamping
  `actor`, `model`, `approved_by` (the literal `"user"`, from `use-ai-helpers.ts`), `approved_at`
  (`new Date().toISOString()`), `prompt`.
- **BE** `routers/ai.py::apply_approved` validates only that each entry has `actor=='ai'` + `type` +
  `target`, then passes the array **verbatim** into `_execute_skill_run(ai_actions=…)` →
  `provenance.build(…, actions=…)`, which appends it untouched. So **`model` / `approved_by` /
  `approved_at` / `actor` are all forgeable** — a caller can attribute a figure to any user, model, or
  approval time.
- `commit_recompute()` (`ai/execute.py`) already stamps `approved_by`/`approved_at` server-side and takes
  `model` from the gateway — but it is **not** the live path (its trailing comment is stale; `/ai/apply`
  uses `_execute_skill_run`). It is kept as-is (used by tests); the live path is the one we fix.
- `/ai/apply` has **no auth dependency** today. Every other write route uses
  `ctx: AuthContext = Depends(require_user)` and derives `user_id` server-side ("the tenant is ALWAYS the
  verified claim, never a request param" — `auth/context.py`). In `dev` mode `require_user` returns the
  fixed `dev_user_id` with no header (offline-safe; existing tests unaffected), and verifies the Clerk
  JWT in prod. So `approved_by = ctx.user_id` is cleanly available.

## The invariant (architectural, not per-bug)

There is **ONE server-controlled chokepoint** that produces every `provenance.actions[]` attribution
record. It derives `actor` / `model` / `approved_by` / `approved_at` **itself** and **never trusts
caller-supplied stamps**. The FE posts the **delta** (which actions to apply — descriptive only), not the
attribution tag. A guard test proves a forged tag is overwritten and that no parallel path bypasses the
chokepoint (the spine-consistency "no parallel path" rule applied to provenance).

This is the integrity boundary of the AI write-path: "AI compiles away" only holds if the recorded actor
tag is **trustworthy**.

## Design

### Backend — the chokepoint (`companions/provenance.py`)

New function — the **only** place AI attribution is stamped:

```python
def stamp_ai_actions(
    client_actions: list[dict],
    *,
    model: str,
    approved_by: str,
    approved_at: str,
    actor: str = "ai",
) -> list[dict]:
    """Re-derive the server-trusted attribution for each posted action delta.

    Keeps ONLY the descriptive fields the client legitimately supplies
    (action_id, type, target, prompt) and OVERWRITES every attribution/approval
    field (actor, model, approved_by, approved_at) with the server-derived values.
    Any client-supplied actor/model/approved_by/approved_at is discarded.
    """
```

- Output record shape is byte-compatible with today's `actions[]`:
  `{action_id, actor, type, target, prompt, model, approved_by, approved_at}`.
- `action_id` / `type` / `target` / `prompt` pass through (descriptive; `prompt` is the user's own goal,
  not a security-sensitive attribution — the server cannot know each proposal's originating goal, so it
  stays client-supplied). `actor` / `model` / `approved_by` / `approved_at` are **always** the injected
  server values regardless of what the client sent.

### Backend — `/ai/apply` (`routers/ai.py`)

- Add `ctx: AuthContext = Depends(require_user)` (the standard write-path dependency).
- Validation stays: non-empty `ai_actions`; each entry a dict with `type` + `target` present (a clean
  400 on a malformed **delta**). **Drop the `actor=='ai'` input requirement** — actor is now server-set,
  not client-asserted.
- Derive server-trusted attribution:
  - `actor = "ai"` (this **is** the AI apply endpoint).
  - `model = get_action_gateway().model_id` (the active gateway).
  - `approved_by = ctx.user_id` (the verified tenant).
  - `approved_at = datetime.now(UTC).isoformat()` (the server clock).
- `trusted = provenance.stamp_ai_actions(actions_list, model=…, approved_by=…, approved_at=…)`.
- Pass **`trusted`** (never the raw `actions_list`) to `_execute_skill_run(ai_actions=trusted)`.

`_execute_skill_run` and `provenance.build` are unchanged — the stamping now happens at the one chokepoint
*before* the list reaches `build`.

**Accepted limitation (noted, not closed here):** `model` is the gateway active **at apply time**. If the
env flips between propose and apply (`live`→`operator`), the recorded model reflects the apply-time
gateway, not the proposing one. The server-trusted current model is strictly better than a forgeable
client string; persisting the proposing model would require a stateful propose→apply token (out of scope,
single-user dev). Documented in the spec + a code comment.

### Frontend — post the delta, not the tag

- `lib/ai/types.ts`: add `AiActionDelta = Pick<AiAction, "action_id" | "type" | "target" | "prompt">`
  (the POST shape). `AiAction` (the full server-produced record read by the ✨ markers + Activity feed)
  is unchanged.
- `lib/ai/proposals.ts::approvedActions(proposals, base, staged)` — **drop the `approvedBy`/`approvedAt`
  params** and stop emitting `actor`/`model`/`approved_by`/`approved_at`. Return `AiActionDelta[]`
  `{action_id, type, target, prompt}`. The `authorOf`-based "still AI-authored" filter (which decides
  *which* accepted proposals are genuinely AI) **stays** — that is part of selecting the delta.
- `lib/ai/api.ts::applyAiActions(aiActions: AiActionDelta[], …)` — type change only (still posts the
  `ai_actions` JSON; the dropped fields simply aren't sent).
- `hooks/use-ai-helpers.ts::rerunPending` — call `approvedActions(aiProposals, fdBaseParams, fdParams)`
  (drop the `"user"` + `new Date().toISOString()` args). `rerunFigureWithAi`'s `aiActions` param type
  follows (`use-figure-run.ts`).

### Mock parity ([[mock-must-mirror-backend-contract]])

`mocks/handlers.ts` `/ai/apply` handler re-derives attribution the same way (server-trusted `actor:"ai"`,
a mock `model`, a mock `approved_by`, an `approved_at` from the handler), so a `dev:mock` re-run produces
the **same** provenance shape the real backend now produces. The mock must not echo client attribution.

## Test plan

- **BE unit** (`tests/test_provenance.py` or `test_ai_*`): `stamp_ai_actions` discards forged
  `actor`/`model`/`approved_by`/`approved_at` and keeps `action_id`/`type`/`target`/`prompt`; sets the
  injected server values.
- **BE integration** (`tests/test_ai_apply*.py`): POST `/ai/apply` with a forged delta
  (`approved_by:"attacker"`, `model:"evil"`, `actor:"human"`, `approved_at:"1999-01-01"`) → the response
  `provenance.actions[*]` carries `approved_by == dev_user_id`, `model == <gateway model_id>`,
  `actor == "ai"`, and an `approved_at` that is **not** the forged value. Existing apply tests updated to
  assert the server-derived values (they previously asserted the client-sent ones).
- **Structure guard** (`tests/test_structure_guard.py`): the "no parallel path" check — the only call
  passing `ai_actions=` a non-None list into `_execute_skill_run` is the `/ai/apply` handler, and that
  handler routes through `provenance.stamp_ai_actions` (grep-based, in the existing guard style).
- **FE** (`lib/ai/proposals.test.ts`): `approvedActions` returns the 4-field delta only (no
  attribution); the `authorOf` "still AI" filter still drops user-overridden keys.
- **FE** (`lib/ai/api.test.ts`): `applyAiActions` posts the delta shape.

## Out of scope

The cross-stage entry points (#2) and the AI-explain follow-ons (#3) are separate specs. `/ai/propose`
and `/ai/explain` stay unauthenticated (they write no provenance — informational/proposal only).

## Gates

BE fast gate (`pytest -m "not slow"`, uv-3.12 PY + `PYTHONPATH=.venv/Lib/site-packages`
[[selom-backend-python-exec]]) + ruff; FE tsc + eslint + vitest. Review: **review-gauntlet**
(correctness — this is the integrity invariant) + **fe-review** (the FE touches the apply path). Verify
on real data + a live uvicorn on a non-:8000 port, posting a forged delta and reading back the figure's
`provenance.actions[]` ([[verify-on-real-data-not-mock]]).
