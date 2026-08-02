# Parallel Sprint 3 — Mode B (3 lanes), launch-ready

Written 2026-08-02 to be **executed next session with no further planning**. Mode B per
`COORDINATION.md` (> 2 lanes → own tmux session each); mechanics per
`docs/next-session-plan/lane-mechanics-from-thalon.md`. Master sequencing:
`docs/build-plan-2026-08/plan.md`.

Owner is away. Forking, building in-lane and local merges are autonomous (`P0-05`); the owner
authorised pushing 2026-08-02.

---

## 1. Why these three, and why the rest is NOT in a lane

Lanes are only worth it when the buckets are **disjoint by file glob** and joined by a frozen
contract. Three qualify. Three deliberately do not:

| Work | Lane? | Why |
|---|---|---|
| `A1` cloud-export **real round trip** | **NO — lead, main tree** | Needs a real browser + the live broker. **Turbopack cannot run in a worktree**, so `fe-build` and every browser check are train-only, main-checkout-only. The lead does this while the lanes run. |
| `P-E` auth (FE half) | **NO — sequential, after the train** | Touches `app/layout.tsx`, `middleware.ts` and `lib/api/client.ts` — the last of which is the **frozen contract**. It would conflict with every FE lane. Coupled work is faster serial. |
| `OH-01` arq + Redis job store | **NO — after Lane B lands** | It is the *producer*; Lane B builds the only *reader*. Ship it first and it ships with no consumer — the exact `R-02` trap. |

---

## 2. The partition — disjoint globs

**One writer per glob. A lane that needs a file outside its glob STOPS and writes the blocker.**

### Lane A — `paper-outputs`  ·  branch `agent/paper-outputs/lit-synth`

Closes `R-01` + `R-03`: the lit-synthesizer and paper-level outputs have **zero FE call sites**,
including the **Reproducibility Score** — a named part of the product thesis that currently cannot
be shown for a paper. Largest user-visible loss on the board.

```
app/frontend/lib/litsynth/**
app/frontend/components/paper/**
app/frontend/components/methods/**
app/frontend/app/paper/**
docs/paper-outputs/**
```

- **Mobbin first** (standing rule): `search_screens` for *"a document view with generated citations
  and an export action"* and *"a scorecard or quality-score panel with a breakdown"*. The
  Reproducibility Score has no precedent in this repo — look before inventing.
- **Check first** whether the Workspace Library's Methods/legend slot was the intended home
  ([[selom-workspace-library]]) — do not invent a second home for the same thing.
- **Spec the IA placement before building** (`docs/paper-outputs/spec.md`, short). Where paper-level
  output lives is expensive to move later.
- Backend is **read-only** here: `/methods/compose` and the citations routes already exist.

### Lane B — `jobs`  ·  branch `agent/jobs/status-surface`

Closes `R-02` + `R-06`: nothing in the FE polls a job, so long runs show no progress, and the
reproduction event stream has no consumer.

```
app/frontend/lib/jobs/**
app/frontend/components/jobs/**
app/frontend/lib/reproduction/progress*.ts
app/backend/routers/jobs.py
docs/jobs-surface/**
```

- **Mobbin first** (standing rule): `search_flows` for *"a long-running job with progress and a
  completion state"*. Note what Drive does here — a persistent bottom-right progress card with
  collapse + dismiss — and decide explicitly whether Selom wants that or inline progress.
- Surface progress where a long run is actually launched (skill run, reproduction).
- `R-06` is the same shape as `R-02` — its non-streaming sibling *is* reached, so this is a
  progress-visibility gap, not a dead feature.

### Lane C — `skills`  ·  branch `agent/skills/coverage`

P-C: answer "are all the skills working?" with **evidence**, which nothing currently can.

```
app/backend/skills/**
app/backend/tests/test_skill_smoke.py
scripts/skill-smoke.sh
docs/skill-coverage/**
```

- Build a **smoke matrix**: run all 36 skills against a real dataset from `SELOM_DATASETS_DIR`,
  record pass/fail + runtime, commit the matrix, and make it a ratchet that fails on regression.
- `umap_scrna` is the **last stub-only skill** — give it a real engine path or record why not.
- Backend-only: this lane touches no frontend file at all.

---

## 3. The frozen contract (no lane may edit)

Frozen for the sprint; changing one is a **stop-and-report**, not an edit:

- `app/frontend/lib/api/client.ts` — the transport, and P-E's landing spot.
- `app/backend/cloud/**` — the lead is finishing `A1` in it.
- `app/backend/skills/contract.py` + `skills/_table.py` — Lane C uses them, does not change them.
- `scripts/verify.sh`, `scripts/guards/**` — gate machinery.
- `agent_handoff/CURRENT.md`, `COORDINATION.md` — lead-owned boards.

**Known conflict point:** `app/backend/tests/test_reachability_guard.py`. Lane A deletes the
`R-01`/`R-03` waivers and Lane B the `R-02`/`R-06` ones, so both edit the same list. That is correct
per the ratchet (a waiver is deleted by the change that wires its surface up, never banked ahead) —
the conflict is line-level and the **lead resolves it in the train**. Lanes must not pre-empt it by
touching each other's rows.

---

## 4. Merge train — order and rule

**C → B → A.** Smallest blast radius first: C is backend-only and cannot conflict with the FE lanes;
B touches one backend router plus a narrow FE slice; A is the largest FE change and merges last.

For each lane: rebase onto `main` → **run `scripts/verify.sh` (no args) on the REBASED result** →
merge → next. Never trust a lane's own green claim: it tested against the `main` it forked from, and
that has already caught a real post-merge typecheck break here. A contract-shaped conflict sends the
lane back rather than being fixed in the train.

---

## 5. Launch sequence (next session, in order)

1. **Lead first:** `A1` cloud-export real round trip on the main tree — it is owed, and it is the
   one thing a lane physically cannot do.
2. For each lane: `git worktree add <path> -b <branch>` → `scripts/worktree-setup.sh <path>`.
3. Write `<path>/LANE-KICKOFF.md` — **pointer-sized**, landmines **inlined** (§6). A worktree is a
   separate memory namespace and recalls none of them.
4. `tmux new-session -d -s lane-<slug> -c <path>` → launch `claude` → `send-keys` a one-line pointer
   at the kickoff → settle → `Enter`.
5. **First peek at ~3 minutes** — thalon's #1 regret was a lane sitting ~20 minutes on an unseen
   permission prompt. Then peek at planned checkpoints, not continuously.
6. Lane writes commits + `LANE-WRAP.md`. **Blocked ⇒ write the blocker in that file and stop —
   never idle silently on a question.**
7. Lead runs the train (§4), then `P-E` auth sequentially, then `OH-01`.

---

## 6. Landmines to INLINE in every kickoff

A worktree recalls no memory. Paste these into each `LANE-KICKOFF.md`:

- **Never `npm install` in a lane.** Deps are **shared symlinks**; the FE `preinstall` guard refuses
  it and it would clobber the main tree.
- **A new backend dep needs a re-plan, not a sync** — `uv run` auto-syncs the **shared** `.venv`,
  mutating every lane at once.
- **Turbopack cannot run in a worktree.** Use `bash scripts/verify.sh --fast`; `fe-build` and every
  browser check are **train-only**.
- **Read gate output RAW.** Never `| tail` a gate — a pipe returns the filter's exit code and
  discards the failure.
- **Real data, not mock.** `dev:mock` skips the paths that break. Export
  `SELOM_DATASETS_DIR=/home/deploy/migration/selom-migration-staging/selom-data`.
- **Serve dev on `localhost`, never `127.0.0.1`** — Next 16 renders but never hydrates, with no
  error.
- **Never bind `:8000`** — that is eamos.
- **Commits:** conventional, named paths (never `git add -A`), **no AI co-author trailer or
  sign-off**. `git user.email` must stay `282747725+steveneam@users.noreply.github.com` or Vercel
  blocks deploys.
- **Any frontend work ⇒ consult Mobbin MCP first** (`search_flows` / `search_screens` /
  `search_sections`) — standing rule, owner-directed 2026-08-02. Comparison instrument, **not** a
  template: write down which patterns you REJECTED and why, not just what you copied. Lane C is
  backend-only and is exempt.
- **Do not push.** The lead owns the train and the push.
- **Stay inside your glob.** Anything outside it ⇒ stop and write the blocker.

---

## 7. Definition of done (per lane)

- Its rows are wired and reachable by a real user — not just a route that answers.
- Its reachability waiver(s) deleted (Lane A, Lane B).
- `bash scripts/verify.sh --fast` green in-lane, raw.
- `LANE-WRAP.md` written: status, what remains, verify result, and any blocker.
