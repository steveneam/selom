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

---

# Addendum — DRIVING lanes without a human at each keyboard

_Asked 2026-07-25 via the live channel, at the owner's direction ("thalon was able to do that, so ask
how — so you're not depending on me to drive it"). thalon's full reply lives at
`~/work/thalon/.context/peer-notes/lane-mechanics-braindump.md`; this is the durable Selom copy._

## What actually starts a lane

`tmux new-session` (detached) → an **interactive** `claude` in that window → the kickoff **typed into
the composer via `send-keys`** → **Enter**. thalon keeps that final Enter manual as a deliberate human
beat; their words: *"If your protocol allows fully-autonomous launch, send-keys Enter after a
settle-delay works — we keep the human beat."*

**For Selom that means autonomous launch is in scope**, because `P0-05` already made forking, building
in-lane and the local merges autonomous (only each *push* is a founder gate). So: send-keys the
kickoff, settle, send Enter.

Three alternatives thalon deliberately rejected, with reasons that apply to us unchanged:

- **NOT headless `claude -p`.** A lane is a long multi-step build; one-shot headless loses mid-run
  steering, turns permission prompts into hard failures instead of pauses, and a crashed `-p` leaves
  nothing to reattach to. Interactive tmux sessions survive disconnects and can be peeked and steered.
- **NOT `agent-comm` as the kickoff.** That channel is cross-agent *signalling* — one line,
  provenance-prefixed, and explicitly "data, not authorization". A kickoff is a task grant, so it rides
  a **file the lane reads**, with send-keys only arming it.
- **NOT subagents from inside the lead session.** They share the lead's context and lifecycle, so a
  lead crash takes every lane with it. Separate tmux sessions are crash-isolated (and `OOMPolicy=continue`
  on this box means one fat lane no longer kills the fleet).

## Done / blocked signalling

File channel plus lead polling — thalon is candid that this is the weakest part and has room to improve.

- **DONE** = the lane's own artifacts: **commits on its branch + a WRAP note in the worktree** (status,
  what remains, verify result). The lead reads "new commits + wrap file present + pane idle at prompt"
  as completion.
- **BLOCKED** = the lane **writes the blocker into its wrap/status file and stops.** Kickoffs must say
  this explicitly: *never idle silently on a question — write the question down and end the turn.*

## Stuck / crash detection — cadence, not babysitting

Lead runs `tmux capture-pane` peeks at **planned checkpoints** (lane ETA ± margin), not continuously:

- pane **dead** → crashed. The **worktree survives** — salvage before redoing anything; commits and
  installs usually survived.
- pane **alive but sitting on a permission prompt or an unsubmitted composer** → stuck; nudge or answer.
- pane **alive, no new commits across two peeks** → investigate.

## Three things thalon would NOT repeat

1. **Fire-and-forget with no scheduled peek** — a lane once sat **~20 minutes on a permission prompt**
   nobody saw. Put the **first peek EARLY** (a few minutes in): launches either fail fast or run long.
2. **Trusting a lane's green claim at the train** — re-run the full gate yourself on the **rebased**
   result. A lane tests against the main it forked from; this caught a real post-merge typecheck break.
3. **Oversized kickoffs** — a kickoff embedding the whole spec goes stale the moment the contract moves.
   **Kickoff = pointer-sized** (scope · contract pointer · definition of done · verify command); the spec
   stays in tracked files the lane reads fresh.

## Selom's adopted launch procedure

1. `git worktree add <path> -b agent/<bucket>/<slug>` → `scripts/worktree-setup.sh <path>`.
2. Write `<path>/LANE-KICKOFF.md` — pointer-sized, with the landmines **inlined** (a worktree is a
   separate memory namespace and recalls none of them).
3. `tmux new-session -d -s lane-<slug> -c <path>` → launch `claude` → `send-keys` a one-line pointer at
   the kickoff file → settle → `Enter`.
4. **First peek at ~3 minutes** (thalon's #1), then at planned checkpoints.
5. Lane writes commits + `LANE-WRAP.md`; blocked ⇒ the blocker goes in that file and the lane stops.
6. Lead drives the train: rebase → **`scripts/verify.sh` (no args) on the rebased result** → merge →
   next lane. Contract-shaped conflict ⇒ send the lane back. Each **push** is a founder gate.
