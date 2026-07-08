# The Contract Window — freezing the shared interface before lanes fork

> Part of the [Selom Playbook](playbook.md). Parallel lanes are only safe on a **frozen contract
> backed by an executable guard**; "frozen" is meaningless unless the freeze rules are explicit and
> enforceable. This doc is those rules. Companion: [`COORDINATION.md`](../../COORDINATION.md) (the
> lane board + Mode A/B threshold); [eng-practices port plan](../eng-practices-port/plan.md) M-005.

## Why a window

The one thing that turns parallel lanes from a speedup into a merge nightmare is a **shared type or
schema changing under a lane's feet**. The fix is not "communicate more" — it is to declare a
**contract window**: a bounded period in which the shared interface is frozen, changes are
**additive-only**, and every new invariant names the exact executable test that will catch its
drift. One window per sprint, one owner.

## What is "the contract"

The surfaces two lanes meet at — the only things a freeze must protect:

- **FE contract types** — the store contracts + `lib/api/` request/response types + `lib/<feature>/`
  public shapes a sibling lane imports.
- **BE schema** — the `SkillSpec` / `param_spec` shape, the `/data/inspect` + run-path response
  envelopes (`RunError` `{error, category, message, fix}`), the provenance `actions[]` shape, and the
  DB/table schema. The FE↔BE JSON contract is the coarse seam (FE decouples via the MSW mock).

Anything **not** on this list is lane-private and needs no window.

## The rules (all four, or it is not a window)

1. **Freeze before fork.** The owner declares the window open and names the frozen surfaces *before*
   any lane worktree is created. A lane that needs a not-yet-frozen shape blocks until it is in.
2. **Additive-only within the window.** You may ADD a field / type / skill / param. You may **never**
   rename, remove, re-type, or tighten a shared shape while the window is open — that is what breaks a
   sibling lane mid-flight. A breaking change closes the window (serialize it, then re-open).
3. **Every invariant names its executable test — in the same change.** Adding a shared shape means
   extending the guard that asserts it *in the same commit*: FE `lib/structure.guard.test.ts` /
   `lib/figure/ssr-plotly-import.test.ts`; BE `tests/test_structure_guard.py`,
   `tests/test_ai_call_site_inventory.py`, `engine/test_vocab_drift_guard.py`, the
   `test_skill_table_contract` / action-registry closed-set guards. A shape with no guard is not
   frozen — it is hope.
4. **One window per sprint, one owner.** Exactly one contract window is open at a time and exactly one
   person (the lead) owns it — the sole merger, mirroring the one-writer-per-board-row discipline. The
   owner opens it, approves each additive change, and closes it at merge.

## Lifecycle

```
OPEN  (owner declares frozen surfaces)
  -> lanes fork on the frozen contract (git worktree + branch; scripts/worktree-setup.ps1)
  -> additive-only changes, each with its guard extended in the same commit
  -> serialized rebase -> ci green -> scope-leak check -> review -> merge (the delegated train)
CLOSE (owner, at merge). A breaking change is a NEW window, never an in-flight edit.
```

## Relationship to the other ratchets

The window is the **process** rule; the executable guards are the **teeth**. The
`ci` required check (M-004) runs those guards on every lane's PR, so a lane that breaks a frozen shape
without extending its guard goes red before it can merge. The contract window is what makes "frozen"
a checkable precondition rather than an aspiration — the same move as the one-writer-per-row board
and the MEASURE->CONFORM->ENFORCE gate ladder.
