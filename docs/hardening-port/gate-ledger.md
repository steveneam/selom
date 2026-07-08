# Engineering-practices port -- gate ledger

Tracks each enforcement gate through the 3-move discipline: MEASURE (report-only, count) ->
CONFORM (repo to zero) -> ENFORCE (blocking CI + a wired pre-commit gated on exit code). Never
flip a blocking gate onto a non-conforming repo. Plan: `docs/eng-practices-port/plan.md`.

## M-001 -- repo-hygiene scanner (`scripts/guards/hygiene-scan.mjs`)

MEASURE command: `node scripts/guards/hygiene-scan.mjs --all` (exit 0 = clean, 1 = hits, 2 = usage/error).
Baseline taken 2026-07-09 over 878 tracked files (`git ls-files`).

| Gate | MEASURE (baseline) | CONFORM | ENFORCE |
|---|---|---|---|
| merge-conflict markers | 0 hits / 878 files | n/a (already clean) | pending: `.githooks/pre-commit` + CI `--all` |
| forbidden tokens | 1 hit -> FALSE POSITIVE (prose "AKIA..." in `infra/stacks/github_oidc_stack.py:4`); pattern tightened from a bare `AKIA` prefix to the real key shape `AKIA[0-9A-Z]{16}` -> 0 real | done (pattern precision; no repo change needed) | pending |
| trailing-newline (board files) | 0 hits (`COORDINATION.md`, `agent_handoff/CURRENT.md`) | n/a (already clean) | pending |

**Detection proven (non-vacuous):** a staged fixture holding a conflict marker, a synthetic AWS key
in the real `AKIA`+16-char shape, and a do-not-commit marker -> 3 hits, exit 1. Both `--all`
(tracked set) and `--staged` (index blobs via `git show :path`) modes verified. (This doc obfuscates
those example literals so it passes its own gate -- the guard applies uniformly, docs included.)

**Scope note (trailing-newline):** enforced only on append-prone board files (the source ratchet's
scope), not repo-wide, so the gate does not balloon into a repo-wide false CONFORM on generated/
third-party files.

**ENFORCE (pending owner go on the `core.hooksPath` cutover -- changes local git behavior):**
- `.githooks/pre-commit` runs `hygiene-scan.mjs --staged` and aborts the commit on non-zero exit
  (gated on exit code, never a `;`-chain).
- `git config core.hooksPath .githooks`; MIGRATE graphify's `.git/hooks/{post-commit,post-checkout}`
  into `.githooks/` (gitignored, still firing) in the SAME cutover so the switch does not silently
  retire graphify -- its gated retirement stays in M-007.
- `.gitattributes` LF-normalization so a CRLF line cannot smuggle a conflict marker past the matcher.
- CI runs `--all` as part of the consolidated `ci.yml` (M-004).

## M-002 -- single-env-reader + router import-boundary ratchets

Guards: `app/backend/tests/test_structure_guard.py::test_single_env_reader` +
`::test_routers_import_only_allowlisted_engine_facade`; `app/frontend/lib/structure.guard.test.ts`
("reads app-config process.env only in lib/config/env.ts" + "lib/ modules do not import upward").
MEASURE taken 2026-07-09.

### Gate A -- single-env-reader (backend)

MEASURE: 18 `os.environ` reads/writes across 13 backend files. 3 writes (`tests/regen_golden.py`,
`reproduction/papers/hani.py`, `dorgau.py` -- the per-run `SELOM_UMAP_ENGINE` override); 15 reads.

| | count | detail |
|---|---|---|
| MEASURE | 18 in 13 files | app-config readers to route: `SELOM_SKILLS_ENGINE`, `SELOM_UMAP_ENGINE`, `ANTHROPIC_API_KEY`, `SELOM_NCBI_{TOOL,EMAIL,API_KEY}`, `SELOM_OPENALEX_EMAIL`, `SELOM_CITATION_CACHE`, `SELOM_PAPER_METADATA_CACHE` |
| CONFORM | 0 non-allowlisted | typed `Settings` fields for the litsynth/paper-metadata vars; **live accessors** `skills_engine()` / `umap_engine()` / `anthropic_api_key_present()` (re-read `os.environ` at call time in `config.py` -- the reproduction override + ~45 monkeypatching tests need live semantics, not frozen fields) |
| ENFORCE | guard green | `test_single_env_reader` fails on any `os.environ`/`os.getenv` outside `config.py` + the allowlist |

Allowlist (genuine env probes / per-run writers, NOT app config): `config.py` (the one home),
`db/engine.py` (`AWS_LAMBDA_FUNCTION_NAME`), `oracle.py` (`LOCALAPPDATA`),
`reproduction/papers/hani.py` + `dorgau.py` (write `SELOM_UMAP_ENGINE`), and `tests/` (setup/monkeypatch).

**Live-verified** (uv-3.12 interpreter): env vars set AFTER `Settings()` construction still select the
same backend (UMAP override -> scanpy; skills-engine -> stub/real; ANTHROPIC presence flips); the
litsynth NCBI key still resolves from the process env identically to the old `os.environ.get`
(`.env` defines none of these); the app boots on `:8010` (`/health` + `/ready` = 200 ok).

### Gate B -- single-env-reader (frontend)

MEASURE: app-config `process.env` reads = `NEXT_PUBLIC_API_MOCKING` (4 sites: `msw-provider.tsx`,
`data-panel.tsx`, `project-workspace.tsx` x2) + `API_PROXY_TARGET` (`next.config.ts`). `NODE_ENV`
(`figure-canvas.tsx`, `params.ts`) is framework/environment detection, not app config.

| | detail |
|---|---|
| MEASURE | 4 mocking reads scattered across 3 components |
| CONFORM | new `lib/config/env.ts` exports `apiMockingEnabled`; the 3 components import it |
| ENFORCE | guard: app-config `process.env` only in `lib/config/env.ts`; `NODE_ENV` allowed anywhere; `next.config.ts` + `scripts/` allowlisted (framework/build; `API_PROXY_TARGET` stays a direct read in `next.config.ts`) |

### Gate C -- router import-boundary (backend)

MEASURE: routers import `engine.{compat, match, recommend}` (3 facade modules; no reach into a
deeper engine internal). CONFORM: already conforming (allowlist == the current set). ENFORCE:
`test_routers_import_only_allowlisted_engine_facade` fails on a new `engine.<module>` import in a
router until `_ROUTER_ENGINE_ALLOWLIST` is extended on purpose.

Gates green: BE fast **1214 passed / 1 skipped** (+2 guards) + ruff clean; FE tsc clean, eslint 0
errors (1 pre-existing warning), vitest **513**.
