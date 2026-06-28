# Selom Agent-Handoff Protocol

> **Single home for coordination rules.** This file is the one place the Selom
> agent-coordination protocol is written down. `CLAUDE.md` and `CODEX.md` at the
> repo root POINT here and must NOT restate these rules. Change a rule here, not
> in two places.

Selom is a no-code multi-omics figure SaaS built by two agents working in
disjoint lanes inside one repo at `D:/selom`:

- **Claude** owns the frontend (`app/frontend`) and `plans/v2-frontend.md`.
- **Codex** owns the backend (`app/backend`) and `plans/v2-backend.md`.

Commercial / licensing gates are intentionally DEFERRED by the owner (build now,
gate before launch). They never block in-lane work. See `DECISIONS.md`.

---

## Read order each session

Read these in order before doing any work:

1. `CLAUDE.md` (if you are Claude) **or** `CODEX.md` (if you are Codex)
2. `agent_handoff/README.md` (this file)
3. `agent_handoff/CURRENT.md` — live state
4. `agent_handoff/RISKS.md` — active build landmines
5. Your active plan — `plans/v2-frontend.md` (Claude) or `plans/v2-backend.md` (Codex)
6. `git status --short --branch`

---

## Hard rules

1. **Never delete or overwrite the other agent's section or plan.** Supersede by
   append, then archive the old content to
   `agent_handoff/archive/<date>-<slug>.md`. History is preserved, never destroyed.
2. **Each agent writes ONLY its own `CURRENT.md` section** — Claude writes
   `## Claude — Last Task & Resume`, Codex writes `## Codex — Last Task & Resume`.
   Do not edit the other agent's section.
3. **Parallel mode = disjoint scopes.** Claude = `app/frontend` +
   `plans/v2-frontend.md`. Codex = `app/backend` + `plans/v2-backend.md`. Stay in lane.
4. **Shared files require a lock.** `CLAUDE.md`, `CODEX.md`, `agent_handoff/*`,
   `ROADMAP.md`, `plans/README.md`, and the FE<->BE contract file may only be
   edited after claiming a lock in `CURRENT.md` -> `## Shared File Locks`. Release
   it when done.
5. **Contract changes are backend-led.** The FE<->BE contract file is changed by
   Codex. The frontend requests changes via `CURRENT.md` -> `## Cross-Agent Requests`;
   it does not edit the contract directly.
6. **No idle waiting.** If blocked, do safe in-lane work — plan/spec, harden your
   own tree, build mock-first. Never start a gated milestone just to fill time.
7. **Roles are explicit.** Any role swap is written into `CURRENT.md` ->
   `## Active Status` before work proceeds.
8. **Claim the Log Edit-Lock before editing any handoff/log doc.** Set the single
   `## Log Edit-Lock` line in `CURRENT.md`, stamp your section, and read the REAL
   clock with PowerShell `Get-Date -Format "yyyy-MM-dd HH:mm zzz"` — never guess a
   time. Release the lock when done.
9. **`CURRENT.md` updates at MAJOR boundaries only, REPLACE never stack** — and it is
   a thin, slot-based pointer, not a per-session essay (see "CURRENT.md shape"). Minor
   progress goes to each agent's rolling log, not into `CURRENT.md`.

---

## CURRENT.md shape (lean)

`CURRENT.md` is a thin, slot-based pointer. The per-session NARRATIVE (what shipped,
file-by-file) already lives in commit messages + the plan/spec docs — **do not duplicate
it here**. Keep these sections and overwrite them in place each session:

- **▸ SESSIONS** — one row per session, newest first: `CODENAME · date · sha-range · one-line`.
  Scan this instead of reading prose; a finished LIVE block collapses to ONE new row here.
- **▸ LIVE** — header `CODENAME · date · sha (push state) · agent`, then ~3 bullets: **Shipped**
  (one line + the commit range to read), **Gates**, **Verified-live** (the deltas git can't show).
- **▸ NEXT** · **▸ DEFERRED** · **▸ ENV / landmines** · **▸ READ FIRST** — short bullet lists.
- **## Codex — Last Task & Resume** — the other agent's section (rule 2: never edit it).

**Session tag:** every session has a short ALL-CAPS **CODENAME** (e.g. `STRUCTURE-REFACTOR`)
+ date + sha. That tuple is the session's identifier across `CURRENT.md`, commits, and
`archive/`. Detail beyond the bullets → the commit range (`git log <a>..<b>`) or a write-once
`archive/<date>-<codename>.md` — never a growing inline comment. The win: updating the handoff
= overwrite ~6 short slots + add one SESSIONS row, not author-then-demote a dense paragraph.

---

## Stop / Break

When the user says stop, break, wrap, or pause:

- Reach the nearest **verified** boundary — never stop mid-edit or mid-task.
- The final chat message ends with a labeled, single-line:
  `Safe to clear: yes | no` + a one-line reason.
- Followed by a fenced, paste-ready resume `Prompt:` block.
- **Kill anything you started.** Stop every dev server, watcher, or background process
  you launched this session (e.g. `npm run dev:mock`) before ending — never leave them
  running across sessions. Only kill what *you* opened; leave pre-existing processes
  alone and note them instead. Mention the cleanup in your final message.

---

## Resume-prompt format

A pointer, not a state dump (~8 lines). The first line is a real-clock stamp:

```
# Resume · YYYY-MM-DD HH:MM +zzzz · <agent>
```

Then: what to read first, the one-line delta since last session, and the
next action / gate. The schema and content already live in the files it names —
do not re-encode them.

---

## Ownership

- **Claude** — frontend UI / design / product copy / browser iteration. Invoke
  the `ui-ux-pro-max` and `frontend-design` skills.
- **Codex** — backend APIs / skill runners / data / tests / verification.

---

## Portability note

This entire agent-handoff protocol is pure **BONES** — nothing in it is
Selom-specific except the paths and surface names. A canonical copy should live
in future **Forj** so any two-agent project transplants it unchanged.
