# AGENTS — Selom

Selom is a no-code multi-omics figure SaaS: drop an h5ad/CSV/mzML, apply analysis skills (UMAP / DEG / volcano / GSEA), get publication-ready editable figures plus auto-methods text. Python FastAPI backend + Next.js frontend + editable Plotly figures.

Any AI agent: read in this order.

1. **Research vault** (canonical research/context layer) — location provided out-of-band (`$SELOM_VAULT_DIR`):
   - `Business/selom.md` — product identity (mission, north star, model).
   - `Selom/Wiki/semantic-index.md` — machine-readable map of all Selom research.
2. **This repo entry points** — `CLAUDE.md` (Claude Code) / `CODEX.md` (Codex backend).
3. **Coordination** — `agent_handoff/README.md` (the single coordination home).

`CLAUDE.md` is the Claude-Code alias of this entry; the lane split and dev commands live there and in `CODEX.md`. The vault holds the research and context; product code lives in this repo.

## Parallel-agent standing rules

This repo is parallel-ready — 2–5 build agents can run in isolated git worktrees without
clashing. Board + full accounting: `COORDINATION.md`. Protocol (read-only vault):
`Forj/bones/parallel-agents.md` + `Forj/Wiki/reference/parallel-agent-workflow.md`.

1. **Propose lanes proactively.** When upcoming work has ≥2 dependency-independent buckets
   with disjoint file sets that meet at a freezable interface, call it out and propose a
   worktree partition (owned glob per lane · frozen contract · merge order) — don't wait to
   be asked. Otherwise run sequentially; coupled work is faster serial.
2. **End clear-safe.** Every session ends with `agent_handoff/CURRENT.md` updated + a
   stamped resume prompt handed back; kill any dev server or worktree you started.

Worktrees stay on local seams (SQLite · local store · inline queue), offset ports
(BE `:801X`, never `:8000`=eamos), and keep `git user.email` on the Vercel-allowed noreply
address. Details + the infra-isolation matrix live in `COORDINATION.md`.
