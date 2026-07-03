# Parallel Sprint 1 — plan + prep

**Stamp:** 2026-07-03 16:08 +10:00 · base `603eae2` (parallel-ready retrofit landed).
**Status:** PLANNED + SCOUTED — **forks NEXT session.** This session = plan + scout + prep only (owner directive). Awaiting owner sign-off on the partition before any fork.
**Protocol (read-only vault):** `Forj/bones/parallel-agents.md` + `Forj/Wiki/reference/parallel-agent-workflow.md`. Board = `COORDINATION.md`.

Three lanes, dedicated terminal sessions, **Claude = lead** in the main tree (`D:/selom`): I partition, freeze contracts, coordinate `COORDINATION.md`, and run the serialized merge gate. Owner approves the partition, the frozen contracts, and every merge.

Each lane's scope below is the **grounded output of a read-only scout pass** (3 parallel scout agents, 2026-07-03), not a guess.

---

## Finalized partition

| Lane | Owns (exclusive) | Sprint-1 slice | Frozen it consumes | Merge |
|---|---|---|---|---|
| **ENG** (BE) | `app/backend/engine/**` · `reproduction/**` · `companions/**` | Engine-internal consistency: promote the DE/metab synonym vocab to ONE named engine primitive + a drift-guard test; land **WS2.8** (counts-gate) + **WS2.7** (gzip, additive) | — (owns the spine) | 1 |
| **ERG** (BE+FE) | `skills/_erg.py` · `skills/_iwx.py` · `skills/_celeris.py` · `skills/_tracegrid.py` · `skills/proprietary/erg_*/**` · `app/frontend/lib/erg/**` · **+ carve-outs** `components/project/marks-editor.tsx` · `components/figure/mark-drag.ts` | Manual-marks v2 (spec R6/R7): a per-run **auto-vs-moved provenance log** + a **blinding toggle** | classify output (`kind`/QCReport) · the figure-model resolver (`capabilities.landmarkMarks`) | 2 |
| **FIG** (FE) | `app/frontend/lib/figure/**` · `components/figure/**` **minus** `mark-drag.ts` | Pillar-2 Slice 1 — **axis gridline controls** (a Style-panel group writing native Plotly `layout` patches) | the loose `FigureSpec` passthrough (no change) | 3 |

Lanes are **independent** (none blocks another) — merge order is just to serialize; the next lane rebases on the new `main`.

---

## The scout findings that shaped the cuts (the traps)

1. **`mark-drag.ts` lives in FIG's directory but is ERG-specific** (imports `@/lib/erg/marks`). → **file-level carve-out: ERG owns it**, FIG owns the rest of `components/figure/**`.
2. **`components/project/**` is contested** — ERG's `marks-editor.tsx` + the FIG editor mount seam both live there. → Sprint-1 slices are scoped so only ERG touches `marks-editor.tsx`; **FIG stays behind the `EditorWorkspace`/`PropertyPanel` boundary** (Slice 1 only touches `components/figure/panels/style-panel.tsx` + `lib/figure/`). FIG Slices 0/6/7 (shell IA, editable table, stage-split) are **cross-lane → deferred**.
3. **ENG's synonym convergence straddles the boundary** (the forked `_FC_COLS`/`_METRIC_COLS` copies live in `skills/*/run_real.py`, OUT of `engine/`). → Sprint-1 ENG does the **engine-internal** promotion + a drift-guard that **flags** the out-of-lane forks but does **not** edit them; converging those is a coordinated later step.
4. **`skills/_erg.py` is the core ERG math module** (the "3 helpers" brief missed it) → added to ERG. The ERG glob is **4 helpers + the proprietary erg_* skills + `lib/erg/` + 2 carve-out files.**

## Frozen contracts (declarations — no blocking pre-commit needed for Sprint 1)
Sprint-1 slices add **no** new shared type, so nothing must be pre-committed to base. The freezes are "**don't break these APIs this sprint**":
- **ENG** preserves classify's OUTPUT: the `kind` taxonomy (`engine/models.py` `ALL_KINDS`), the `QCReport`/`QCFlag` shape, and `DataBundle`'s public fields. Its internal synonym refactor is behavior-preserving.
- **ERG** preserves `skills/_iwx.py::read_iwxdata` + `skills/_celeris.py::is_diagnosys_export` (ENG's `engine/ingest.py` imports them) and the `lib/erg/marks.ts` exported API (FIG's `figure-canvas.tsx` imports `MarkRole`).
- **FIG** does not change the `FigureSpec` TS shape or the `meta.selom` primitive union (gridlines write legal Plotly `layout` leaves only). *(If a later FIG slice adds a `sigbar` primitive, THAT gets designed + pre-committed to base first — not this sprint.)*

---

## Merge gate — set up FIRST, next session, before any fork
`main` is not yet protected. Add a tiny always-on CI **gate** job (the path-filtered `backend-ci`/`frontend-ci` can't be "required" as-is — they'd deadlock cross-path PRs) and protect `main` to require it, `enforce_admins=false` (lead can still direct-push; lanes go through the gate). Then every merge = **rebase onto latest `main` → CI green → review → merge**, one lane at a time. **No merge on red.**

---

## Worktrees & terminals — how the 3 lanes actually run

**Key point:** each lane runs in its **own separate worktree FOLDER**, not in `D:/selom`. Three agents all opening `D:/selom` would edit the same files — the exact clash we're preventing. `D:/selom` stays as the **lead** (this session).

**Create the 3 worktrees** (sibling folders; one branch each):
```bash
cd /d/selom
git worktree add ../selom-eng -b agent/eng/consistency
git worktree add ../selom-erg -b agent/erg/marks-v2
git worktree add ../selom-fig -b agent/fig/gridlines
```
This makes `D:/selom-eng`, `D:/selom-erg`, `D:/selom-fig` — each a full checkout on its own branch, sharing one `.git`. (`.worktreeinclude` auto-copies `.env` + `.claude/settings.local.json` into each.)

**Boot each worktree** (a worktree is a fresh checkout — no installed state):
- Deps: `npm install --legacy-peer-deps` (FE lanes) + `uv sync` (BE lanes) — **or** junction the main tree's `node_modules` into each worktree (the Thalon symlink) to skip the reinstall.
- Ports: offset per worktree — BE `:8011/:8012/:8013` (**never `:8000` = eamos**), FE `:3001/:3002/:3003`.
- FE lanes: set that worktree's `NEXT_PUBLIC_API_BASE=http://localhost:801X` (the committed example says `:8000`, which is eamos).
- Confirm `git config user.email` = `282747725+steveneam@users.noreply.github.com` (or Vercel blocks the branch's preview).

**Open each — your question, answered:** it is **3 separate VSCode windows, each opening a DIFFERENT worktree folder** (`D:/selom-eng`, `-erg`, `-fig`) — *not* 3 terminals on the same `D:/selom` folder, and *not* 3 windows on `D:/selom`.
- **Recommended:** File → New Window → Open Folder → `D:/selom-eng` → open its integrated terminal → run `claude`. Repeat for `-erg`, `-fig`. Each window's file-explorer + terminal is scoped to its own lane — clean mental model + true isolation.
- Keep `D:/selom` open in a 4th window (or your current one) = **the lead** (me). I don't fork; I merge.
- *(Alternative if you prefer one window: 3 integrated-terminal tabs, each `cd`'d into a different worktree folder, then `claude`. Works, but the file explorer still shows the main tree — more confusing.)*
- *(Native shortcut: `claude --worktree eng` creates `.claude/worktrees/eng/` and starts the agent there in one step — skips the manual `git worktree add`.)*

**Cleanup after merge:** `git worktree remove ../selom-eng` (add `--force` if dirty) + delete the branch.

---

## Kickoff prompts (paste one into each lane's `claude` session)

### Lane ENG
```
You are the ENG lane build agent for a parallel sprint on Selom (worktree D:/selom-eng, branch agent/eng/consistency). Read CLAUDE.md, AGENTS.md, COORDINATION.md, docs/parallel-sprint-1/plan.md, and docs/restructure/plan.md (WS2.7/WS2.8/WS3.1) first.

OWN EXCLUSIVELY: app/backend/engine/**, app/backend/reproduction/**, app/backend/companions/**. Touch NOTHING outside these globs — especially not app/backend/skills/** or app/frontend/**.
FROZEN (do not change the shape of): classify's output — the `kind` taxonomy (engine/models.py ALL_KINDS), QCReport/QCFlag, DataBundle public fields. Your synonym refactor must be behavior-preserving.

DoD (one slice): (1) promote the DE/metab synonym vocab (_LOGFC/_PVAL/_METAB_TOKENS in engine/databundle.py) to ONE public named engine primitive that classify/columns/compat/frame_schema/qc import; (2) a drift-guard test that FAILS if a second copy of those sets forks — it may only FLAG the known out-of-lane forks (extract/ingest, skills/*/run_real.py), never edit them; (3) land WS2.8 (the counts-gate demotion in _classify_frame) and WS2.7 (a transparent .csv.gz loader reusing _load_csv, additive); (4) all 4 reproduction hand-ledgers + the 3 cold-drive snapshots stay byte-identical/green.

Gates: BE fast pytest (`-m "not slow"`) + ruff, via the uv-3.12 PY + PYTHONPATH (see memory selom-backend-python-exec / CLAUDE.md), from app/backend. Verify WS2.7 live on a real .csv.gz at /data/inspect on :8011 (never :8000).
Commit to YOUR branch only (named paths, no `git add -A`, no AI sign-off). Do NOT merge — the lead merges. Update only YOUR row in COORDINATION.md (pending→in_progress→review). If blocked or stuck ~3 iterations, stop and report.
```

### Lane ERG
```
You are the ERG lane build agent for a parallel sprint on Selom (worktree D:/selom-erg, branch agent/erg/marks-v2). Read CLAUDE.md, AGENTS.md, COORDINATION.md, docs/parallel-sprint-1/plan.md, docs/records/erg-manual-marks/spec.md (R6+R7), and docs/figure-data-capabilities/spec.md first.

OWN EXCLUSIVELY: app/backend/skills/_erg.py, skills/_iwx.py, skills/_celeris.py, skills/_tracegrid.py, skills/proprietary/erg_*/**, app/frontend/lib/erg/**, AND the two carve-out files app/frontend/components/project/marks-editor.tsx + app/frontend/components/figure/mark-drag.ts. Touch NOTHING else — not engine/**, not the rest of components/figure/** or components/project/**.
FROZEN (do not change signatures): skills/_iwx.py::read_iwxdata and skills/_celeris.py::is_diagnosys_export (engine/ingest.py imports them); the lib/erg/marks.ts exported API (readSeededMarks/roleTag/snapToSample/MarkRole/SeededMark — FIG imports these). You need NO figure-spec / engine change — consume the existing resolver.

DoD (manual-marks v2, R6+R7): (1) BE _erg.py emits a per-run provenance log {segment, marker, auto_ms, set_ms, moved} (aggregate the existing a_source/b_source/n1_source/p1_source tags) + each ERG skill's table caption states "N of M operator-adjusted"; (2) FE marks-editor.tsx gains a "blind" toggle that hides group/condition labels + greys the headers while marking and restores them off, marks surviving the toggle; (3) surface per-marker "operator-moved" state; (4) INVARIANT: no manual_marks ⇒ every ERG skill byte-identical (goldens unchanged); blinding is pure FE state.

Gates: BE fast pytest + ruff (uv-3.12 PY + PYTHONPATH); FE tsc + eslint(0 err) + vitest. Verify live on the hum-heavy real ERG file per the spec (BE :8012 / FE :3002).
Commit to YOUR branch only (named paths, no AI sign-off). Do NOT merge. Update only YOUR COORDINATION.md row. (The Naka-Rushton modelFit fit-knobs UI is a SEPARATE later slice — needs a spec first; NOT this sprint.)
```

### Lane FIG
```
You are the FIG lane build agent for a parallel sprint on Selom (worktree D:/selom-fig, branch agent/fig/gridlines). Read CLAUDE.md, AGENTS.md, COORDINATION.md, docs/parallel-sprint-1/plan.md, docs/pillar-2-direct-manipulation/spec.md (§5.1), and docs/figure-editor-contract/spec.md first.

OWN EXCLUSIVELY: app/frontend/lib/figure/** and app/frontend/components/figure/** EXCEPT mark-drag.ts (that file is the ERG lane's). Touch NOTHING outside — not components/project/** (the editor mount seam), not lib/erg/**, not hooks/use-figure-store.ts (consume it, don't fork it), no backend.
FROZEN (do not change): the FigureSpec TS shape (lib/figure/figure-spec.ts + contract.ts) and the meta.selom primitive union. Gridlines write legal Plotly layout leaves only — no persisted-contract change.

DoD (Pillar-2 Slice 1 — axis gridline controls): (1) a new "Axis gridlines" control group in components/figure/panels/style-panel.tsx, gated on Cartesian-axis capability from deriveFigureModel; (2) controls write native Plotly patches as client-classified JSON-Patch `set` ops — xaxis/yaxis.showgrid, gridcolor, gridwidth, griddash, minor.*, dtick; (3) instant live re-render + undo/redo via the existing store; WYSIWYG export unchanged; (4) figures without Cartesian axes (heatmap/sankey/radar) hide the group; (5) a unit test + a golden of which Style groups show per archetype.

Gates: FE tsc + eslint(0 err) + vitest (+ next build catches SSR). Verify live in the running editor (npx next dev --webpack; FE :3003) that gridline edits render + undo. Do NOT touch Slices 0/6/7 (cross-lane, deferred).
Commit to YOUR branch only (named paths, no AI sign-off). Do NOT merge. Update only YOUR COORDINATION.md row.
```

---

## RESUME PROMPT (next session)
> # Selom — Parallel Sprint 1 · fork + drive · 2026-07-03 16:22 +10:00 · Claude (lead)
> Read `docs/parallel-sprint-1/plan.md` (this file) + `COORDINATION.md` first. `git fetch && git status` — origin/main at the prep stamp.
> **This session = execute Sprint 1.** Order: (1) get owner sign-off on the partition above if not already given; (2) set up the merge gate (CI gate job + protect `main`, enforce_admins=false); (3) create the 3 worktrees + hand the owner the 3 kickoff prompts (or spawn per the run-model); (4) as each lane reaches `review` in COORDINATION.md, run the serialized merge gate (rebase→CI→review→merge) WITH owner approval each merge; the next lane rebases on the new `main`. No merge on red. (5) After all 3 merge, run one milestone review-gauntlet + fe-review over the sprint diff (cadence = milestone, [[review-cadence-phase-not-task]]).
> **Also still parked:** the restructure board WS2.7→WS2.8 is now folded INTO the ENG lane; if Sprint 1 is deferred, WS2.7 resumes solo/sequential (nothing was built — clean park).
> Landmines unchanged: BE ports 801X (never :8000=eamos), uv-3.12 PY + PYTHONPATH, `npx next dev --webpack`, git email = the Vercel noreply, no AI sign-off, kill servers/worktrees you start.
