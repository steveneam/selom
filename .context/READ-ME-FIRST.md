# READ ME FIRST — Selom build agent orientation

You are about to work on **Selom**, a no-code multi-omics figure SaaS (Python FastAPI backend + Next.js frontend + editable Plotly figures).

## The model: vault = context, repo = code

The research/context layer is **canonical in the vault**, not in this repo. Read the vault first, then orient in the code.

1. **Research vault:**
   `C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool`
2. **Identity:** `Business/selom.md` — mission, north star, model, scope decisions.
3. **Map:** `Selom/Wiki/semantic-index.md` — machine-readable index of all Selom research (decisions, specs, syntheses, entities).
4. **This repo:** `CLAUDE.md` (Claude / frontend) or `CODEX.md` (Codex / backend), then `agent_handoff/README.md` for coordination.

## Why this split

The vault is the durable research and context layer that both build agents query; product code lives here in `D:/selom`. Code is never mirrored into the vault — vault pages cite repo paths and line numbers. When in doubt about *what to build and why*, the answer is in the vault; *how it is built* is here.

## Lane reminder

Claude owns `app/frontend`; Codex owns `app/backend`. Default split, not a hard wall — cross only through the handoff for shared contract changes.
