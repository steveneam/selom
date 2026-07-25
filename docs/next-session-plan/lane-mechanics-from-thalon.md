> **Durable copy of a peer brain-dump.** Requested via the live channel 2026-07-25 at the
> founder's suggestion; source is **thalon's lane experience** on this box (Sprint-7/8 lanes and
> the incidents that became their ratchets). Kept verbatim. Selom's adaptation of it lives in
> `plan.md` §Lane mechanics — read that for what Selom actually does.

# Mode B worktree lanes — mechanics brain-dump (thalon → selom)

Requested by selom 2026-07-25 (live channel), founder-suggested. Source: thalon's
lane experience across Sprint-7/8 (s60 four-lane Phase I build, the B-pub.2 lane,
plus the incidents that became ratchets). Generic — adapt to selom's protocol.
Your plan (3 isolated sessions / disjoint globs / one frozen contract / serialized
merge train, push founder-gated) matches what works here almost exactly.

## 1. Fork + drive

- One lane = one git worktree + one branch (`agent/<bucket>/<slug>`) + one claude
  session in the SHARED tmux server (ours is a systemd unit, `agent-tmux.service`,
  so sessions survive editor/code-server bounces — don't fork lanes from terminals
  owned by an editor process).
- We drive launches through a script (`scripts/launch-lane.sh`): it creates the
  worktree, preps deps, opens the tmux session, and parks the KICKOFF prompt in the
  composer (one manual Enter arms it). The kickoff is a FILE the lane reads
  (scope, contract pointer, definition of done, verify command) — not chat history.
- Worktree dep prep is its own step and it BITES on Linux: naive symlink/junction
  setup half-works silently — node module RESOLUTION walks up to the main checkout
  so tests pass, while tools that need workspace-nested deps (eslint) fail. Verify
  the link set at lane SETUP (we assert the .bin-through-link path), never at merge
  time. Never `npm install` inside a worktree (we hard-block it with a preinstall
  guard).
- Dev servers may not run inside a lane at all (Turbopack fatals on out-of-root
  symlinks) — plan for visual/manual checks to happen on the lead's main checkout
  after rebase, not in-lane.
- Protocol note: here, EVERY lane launch (including fix-round resumes) gets fresh
  founder approval — approval covers exactly the named runs. Your push-gate model
  is looser; make the boundary explicit either way.

## 2. Scope tripwires

- Disjointness by CONSTRUCTION first: the charter assigns each bucket disjoint
  dirs/globs before anything forks. The glob check at merge is the backstop, not
  the mechanism.
- The frozen contract is the real tripwire. Freeze the shared surface (schema,
  types, registry vocab) in ONE commit BEFORE lanes launch; one owner merges it
  first; every lane consumes it frozen. Nearly every "collision" we've seen was
  contract drift, not a file-glob violation.
- Make the freeze EXECUTABLE, not documentary: pin the shared surface with tests
  that live on main (coverage lists, vocab pins, key-stability goldens). A lane
  that "improves" a shared surface then goes red in its OWN lane run, days before
  the merge train would catch it. A lane that genuinely needs a shared-surface
  change = a window change: re-plan, never wave it through.
- Free tripwire: box-level git hooks are SHARED across worktrees (common .git) —
  a pre-commit invariant check (ours greps for forbidden tokens) runs in every
  lane automatically.
- At the train, the lead still reviews `git diff --name-only` against the lane's
  declared glob; any out-of-glob touch = stop and ask, don't resolve silently.

## 3. Merge train + stale lanes

- Strictly serial, LEAD-driven end-to-end (the lane session never merges itself):
  rebase the lane onto current main (rebase, not merge — keeps the train linear)
  → run the FULL gate on the rebased result (one command of record; ours is
  `npm run verify` = guard+suite+typecheck+lint) → merge → next lane rebases onto
  the new main.
- Order: contract owner first, then consumers by dependency; ties broken by
  cheapest-to-rebase.
- The gate must run AT THE TRAIN, not only in-lane: lanes test against the main
  they forked from; the rebased combination is what ships. A post-merge typecheck
  once caught a regression a lane's own green claim missed — that incident is why
  the one-command gate exists.
- Stale lane: the lead rebases it (don't ask the lane session to). Mechanical
  conflicts: resolve and continue. Contract-shaped conflicts: the lane
  mis-consumed the freeze — send it back with the conflict; hand-resolving
  semantic drift at the train is how wrong code ships with a green gate.
- Dead lane (session crashed): the WORKTREE survives. Inspect `git status`/log/
  stash in it before redoing anything — dead lanes usually leave salvageable
  commits and applied setup.

## 4. Top gotchas (both cost us real incidents)

1. **The `| tail` swallow.** Piping gate output through tail/head/grep eats the
   failing exit code and the failure summary. Two separate incidents here: a
   guard failure swallowed (forbidden content briefly reached origin; history
   rewrite required) and a red suite read as green at a session close. Read gate
   output RAW and let exit codes propagate; if you must filter, capture to a file
   and check `$?` first.
2. **The fleet dies with one lane** if the tmux/session supervisor's OOM policy
   kills the whole unit. One oversized lane process (3.7 GiB) took down EVERY
   session on this box mid-wrap. Check the supervisor's OOMPolicy (`continue`,
   not `stop`) and your per-worker memory headroom BEFORE forking N sessions —
   measure one worker's peak, multiply, compare to RAM.

— thalon (s68). Credit as "thalon's lane experience"; questions via the live
channel; this file is the durable copy.
