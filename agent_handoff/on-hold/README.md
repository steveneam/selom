# Selom — On Hold (Docker / WSL-gated work)

Deferred work that depends on **Docker or WSL**. Owner directive (2026-06-13): **ask before
any Docker/WSL work** (memory `ask-before-docker-wsl`). These are parked here so they're
**not forgotten** — pick each up, with the owner's go-ahead, when its trigger arrives.
Non-Docker work proceeds normally. When an item is started, drop a per-item scope note in
this folder before building.

| # | Item | What it is | Why gated | Belongs to | Resume when |
|---|---|---|---|---|---|
| 1 | **Kaleido journal export** | B4 journal-preset PNG/SVG/PDF export via Kaleido | needs Docker + system Chromium (RISKS #2 · DECISIONS #7 web-first) | **B4** (its only remaining item) | the deploy image is built (B8-adjacent) |
| 2 | **arq Redis job-status store** | Redis-backed `JobStore` so cross-process (arq) job *status*/errors are visible, not just success (`jobs/worker.py` caveat) | needs a running **Redis** (Docker/WSL on Windows) | B3 hardening → B7 | infra is stood up |
| 3 | **OmicVerse isolated worker** | 2nd Verified engine + the prime Skill-Foundry source (~1000 `ov.*` fns ≈ SkillSpec runners) | `pandas<3` conflict (RISKS #9) → must run out-of-process / containerised | B2 follow-up → **B9** | scoping the isolated env (Docker / its MCP server) |
| 4 | **Deploy image** | Render CPU + Modal GPU + Vercel; AGPL SCA scan (hard gate) | the deployment **Docker image** | **B8** launch | Stage 3 launch |
| 5 | **Community skill sandbox** | Docker + mamba images + network policy for community-tier skills | container sandbox (design §6.5 E) | **B9** (v2, deferred) | Skill Foundry community tier |

**Not gated (so NOT here):** R2 object storage (cloud config, not Docker); all the current
P1 breadth work (`deg`/`enrichment` modes, `pathway`/`go-graph` skills run via HTTP APIs).

_Filed 2026-06-13 · Claude (acting FE+BE), owner-directed. Cross-ref: `CURRENT.md`, `RISKS.md` #2/#9, `docs/build-charter.md` B4/B8/B9._
