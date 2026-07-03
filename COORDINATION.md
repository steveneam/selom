# COORDINATION — Selom parallel-agent lane board

> **Inert until we fork lanes.** Selom is parallel-ready but runs in **sequential mode**
> by default. This board activates only when a sprint has ≥2 dependency-independent
> buckets with disjoint file sets that meet at a freezable contract.
>
> **Protocol (read-only research vault — cite it, never write to it):**
> `…/EAMOS Web Tool/Forj/bones/parallel-agents.md` (the what) +
> `…/Forj/Wiki/reference/parallel-agent-workflow.md` (the how — exact worktree commands,
> the merge gate, the retrofit checklist).
>
> **The contract in one line:** one file → one owner · freeze the shared interface before
> forking · isolate each lane in its own git worktree+branch · coordinate through THIS
> ledger (not OS locks) · integrate via serialized *rebase → CI → review → merge* · the
> owner approves the seams (partition · frozen contract · every merge). 3–5 lanes max;
> coupled work stays sequential (it's faster serial).

## Active sprint

**Lead:** Claude (main tree `D:/selom`)   ·   **Sprint 1** — **FORKED 2026-07-03 21:15 +10:00.** 3 worktrees
live + booted (`D:/selom-{eng,erg,fig}`; junctioned deps · `API_PROXY_TARGET` per FE lane · Vercel git-email
inherited · clean trees), awaiting kickoff in their own windows.   ·   **Full plan + kickoff prompts:**
`docs/parallel-sprint-1/plan.md`. Sprint-1 slices add no new shared type → freezes are "don't break these APIs"
declarations (see the plan). **Merge model (owner-chosen): DELEGATED train** (Thalon-validated, Sprint 0). Branch
protection deferred; the lead runs the whole train autonomously to **local** `main` — per lane in merge-order:
rebase → CI/gates green → scope-leak check (`git diff --name-only main...<lane>` vs the lane's glob) → review →
merge → board message. **Push stays the owner's gate** (nothing reaches origin/Vercel without the owner; owner
inspects local `main` + messages post-hoc, then pushes). Any conflict **outside the board** = a partition leak →
stop, don't resolve blindly. No merge on red.

| lane | owner | owns (glob) | branch | status | depends-on | merge-order |
|------|-------|-------------|--------|--------|------------|-------------|
| ENG | `D:/selom-eng` (BE `:8011`) | `app/backend/engine/**` · `reproduction/**` · `companions/**` | agent/eng/consistency | pending — forked, awaiting kickoff | — | 1 |
| ERG | `D:/selom-erg` (BE `:8012` · FE `:3002`) | `skills/{_erg,_iwx,_celeris,_tracegrid}.py` · `skills/proprietary/erg_*/**` · `lib/erg/**` + carve-outs `components/project/marks-editor.tsx` · `components/figure/mark-drag.ts` | agent/erg/marks-v2 | pending — forked, awaiting kickoff | — | 2 |
| FIG | `D:/selom-fig` (FE `:3003`) | `app/frontend/lib/figure/**` · `components/figure/**` **minus** `mark-drag.ts` | agent/fig/gridlines | review | — | 3 |

Status vocab: `pending · in_progress · blocked:<what> · review · merged`.
**One writer per row** — the lead owns assignments + merge-order; each owner writes only
its own `status`. Messages below are append-only; you replace only your own state.
**Merge mechanics (delegated train — Thalon-validated, Sprint 0):** serialized per lane — rebase onto latest
`main` → CI/gates green → **scope-leak check** (`git diff --name-only main...<lane>` must stay within the lane's
glob) → **trust-but-verify** (lead re-runs the lane's gates, not just its report) → review → merge. Conflicts are
a tripwire: a board-row conflict is the ONE expected conflict (trivial — one-writer-per-row); any **non-board**
conflict = a partition leak → stop. An out-of-glob need → ship an **`.example`/proposal inside your own glob + a
board message** (lead activates at merge), never an ad-hoc edit. No history surgery on `main` mid-sprint. No merge on red.

## Messages (append-only)

- **2026-07-03 21:15 +10:00 · lead:** Sprint 1 forked. 3 worktrees created at base `b0497d9` on branches
  `agent/{eng/consistency,erg/marks-v2,fig/gridlines}` + booted: `.env`/`settings.local.json` copied per
  `.worktreeinclude`; `node_modules` junctioned into erg+fig, `.venv` into eng+erg (shared read — no lane
  changes deps this sprint); `API_PROXY_TARGET` written to erg (`:8012`)/fig (`:8013`) `.env.local`; git-email
  = Vercel noreply (inherited); all 3 trees clean. **Boot-doc fix:** the FE proxy var is `API_PROXY_TARGET`
  (read by `next.config.ts`), **not** `NEXT_PUBLIC_API_BASE` (which the FE ignores) — corrected in the plan +
  checklist above. Owner deferred branch protection → lead merges manually, serialized, owner-approved. Lanes:
  update only your own row `pending → in_progress → review`; commit to your branch only (named paths, no AI
  sign-off); do **not** merge — ping the lead at `review`.
- **2026-07-03 21:40 +10:00 · lead:** Adopted **Thalon's Sprint-0-validated mechanics** (E-drive, 2 lanes merged,
  0 partition violations) + owner chose the **delegated merge train** (push = owner's gate). Concrete adds folded
  into the board above: scope-leak check at merge · conflict-as-tripwire · `.example` escape hatch for out-of-glob
  needs · trust-but-verify · no history surgery mid-sprint. **Lanes now DO commit their own board row** (the async
  signal) — superseding the earlier kickoff note. **Selom-specific gotcha:** worktrees run under a *separate*
  agent-memory namespace (`D--selom-eng` ≠ `D--selom`), so a lane can't recall D:/selom auto-memory — all landmines
  are inlined into the kickoff prompts and shared state lives in committed files (this board, CLAUDE.md, specs),
  never memory. Lanes fast-forwarded to this commit as their base.
- **2026-07-04 02:32 +10:00 · FIG:** Kickoff → building Pillar-2 Slice 1 (axis gridline controls). Scope
  stays inside the FIG glob: new `lib/figure/gridlines.ts` (pure Plotly-leaf op builders) +
  `lib/figure/style-groups.ts` (single-source group visibility) + a `cartesianAxes` capability on the
  derived FigureModel + a Style-panel "Axis gridlines" group (gated on Cartesian archetype); removed the
  redundant Axes-tab "Show gridlines" toggle (kept "Zero line"). No FigureSpec/`meta.selom` change —
  gridlines write native `xaxis/yaxis` layout leaves as client-classified `set` ops. Static gates green
  (tsc 0 · eslint 0 · vitest 509). `next build` (Turbopack) FATALs on the worktree's junctioned
  `node_modules` ("Symlink out of filesystem root") — infra, not code; running `next build --webpack`
  instead. Live editor verify next.
- **2026-07-04 02:52 +10:00 · FIG → review (@lead):** Pillar-2 Slice 1 DONE + committed (`9a55627`).
  8 files, all inside the FIG glob (`git diff --name-only main...agent/fig/gridlines` = `lib/figure/{gridlines,style-groups,figure-model}{,.test}.ts` + `components/figure/panels/{style-panel,axes-panel}.tsx`) — no scope leak, no FigureSpec/`meta.selom` change.
  **Gates:** `tsc --noEmit` 0 · `eslint` 0 · `vitest` 509 pass (incl. new gridline-op + per-archetype
  golden). **Build:** `next build` (Turbopack, the npm-script default) FATALs on the worktree's
  junctioned `node_modules` (Symlink-out-of-root) — infra, not code; `next build --webpack` **compiled
  successfully** (killed only during the redundant TS phase already covered by `tsc`). **Live verify:
  DELEGATED to the orchestrator** (owner directive 02:5x — lanes share the servers); I flushed my dev
  server + freed `:3003`. Verify hint: `?demo=umap_scrna` on a fresh project auto-runs a scatter → open
  the **Style** tab → the new **"Axis gridlines"** group toggles gridlines live + undo restores. The
  mock only emits a umap scatter, so the heatmap/sankey/radar *hidden*-group case is covered by the
  `style-groups` golden, not the live app. Ready for the merge train (order 3).

---

## Selom lane taxonomy (where the disjoint globs are)

| Axis | Lanes | Frozen contract |
|---|---|---|
| **Coarse: FE vs BE** | `app/frontend/**` · `app/backend/**` | JSON skill/endpoint contract; FE decouples via the MSW mock |
| **BE skills sprint** | one skill = one lane: `app/backend/skills/<name>/**` | the `SkillSpec` shape + `run_skill` registration |
| **FE feature sprint** | one feature = one lane: `app/frontend/lib/<feature>/**` + its page | store contract + `lib/api/` types |
| **Infra / IaC** | `infra/**` · `.github/workflows/**` | — the apply/deploy step is a human seam, never an autonomous lane |

## Per-worktree boot checklist

A worktree is a *fresh checkout* — untracked/installed state does NOT come with it.
On fork (`claude --worktree <lane>` → `.claude/worktrees/<lane>/`):

1. `.worktreeinclude` auto-copies `.env` + `.claude/settings.local.json`.
2. **Offset ports** — BE `:801X`, FE `:300X`. **`:8000` is eamos — never bind it.**
3. **Point the FE at its own BE** — set that worktree's `API_PROXY_TARGET=http://localhost:801X`
   in `app/frontend/.env.local` (read by `next.config.ts`'s `/api/*` rewrite; default `:8000` = eamos —
   always override per worktree). *(Not `NEXT_PUBLIC_API_BASE`; that name is unused in the FE.)*
4. **Install deps** — `npm install --legacy-peer-deps` (FE) + `uv sync` (BE). Each worktree
   owns its own `node_modules`/`.venv` (or a symlink — decide per sprint).
5. **Fresh dev DB** — a new local SQLite `dev.db`; never point a worktree at cloud Postgres.
6. **Guard the Vercel email** — confirm `git config user.email` is the Vercel-allowed
   noreply address, or Vercel blocks the branch's preview deploy.

## Infra & dependency isolation (dev = all local seams → isolation is free)

| Resource | Dev seam | Per-worktree / per-lane rule |
|---|---|---|
| Database | SQLite `dev.db` (`SELOM_DB_AUTO_CREATE=false`) | fresh file per worktree; NEVER share the cloud Postgres — a migration test = a branched DB, owner-approved |
| Object store | `SELOM_OBJECT_STORE=local` | local dir per worktree; if a lane needs S3 → per-lane key prefix |
| Queue / jobs | `SELOM_QUEUE=inline` · `SELOM_JOB_STORE=memory` | inline per worktree; never share a live Redis |
| FE deploy | Vercel (GitHub integration) | each branch → its own preview URL (a benefit); keep the git-email guard (checklist #6) |
| BE server | `uvicorn :801X` | own port per worktree; `:8000` = eamos, off-limits |
| AWS creds | shared `selom-dev` key in `.env` | read-only fine; shared-bucket writes need per-lane namespacing; $10/mo budget → keep dev local |
| Dep manifests | `package-lock.json` · `uv.lock` | a dep change is a **single-owner coordinated step — never split across parallel lanes** |
| Live keys (Stripe/Clerk/Resend/AI gateway) | `.env` | use dev/test keys; no lane triggers live charges/sends |

## Merge gate (set up before the first fork)

`main` is **not yet branch-protected**. Before the first parallel merge, add a small
always-on CI **gate** job (the existing `backend-ci`/`frontend-ci` are path-filtered, so
marking them "required" as-is would deadlock cross-path PRs) and protect `main` to require
it. Merges are then serialized: **rebase onto latest `main` → CI green → review → merge**,
one lane at a time in merge-order; the next lane rebases on the new `main`. **No merge on red.**
