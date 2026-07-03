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
declarations (see the plan). **Merge gate: owner DEFERRED branch protection for this solo-lead sprint** — the
lead runs the discipline manually (rebase → CI green → review → owner-approved merge, one lane at a time; no merge on red).

| lane | owner | owns (glob) | branch | status | depends-on | merge-order |
|------|-------|-------------|--------|--------|------------|-------------|
| ENG | `D:/selom-eng` (BE `:8011`) | `app/backend/engine/**` · `reproduction/**` · `companions/**` | agent/eng/consistency | pending — forked, awaiting kickoff | — | 1 |
| ERG | `D:/selom-erg` (BE `:8012` · FE `:3002`) | `skills/{_erg,_iwx,_celeris,_tracegrid}.py` · `skills/proprietary/erg_*/**` · `lib/erg/**` + carve-outs `components/project/marks-editor.tsx` · `components/figure/mark-drag.ts` | agent/erg/marks-v2 | pending — forked, awaiting kickoff | — | 2 |
| FIG | `D:/selom-fig` (FE `:3003`) | `app/frontend/lib/figure/**` · `components/figure/**` **minus** `mark-drag.ts` | agent/fig/gridlines | pending — forked, awaiting kickoff | — | 3 |

Status vocab: `pending · in_progress · blocked:<what> · review · merged`.
**One writer per row** — the lead owns assignments + merge-order; each owner writes only
its own `status`. Messages below are append-only; you replace only your own state.
**Merge gate (set up before the first fork):** CI gate job + protect `main`; then rebase→CI→review→merge, serialized. No merge on red.

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
