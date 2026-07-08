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

## M-003 -- LLM/AI call-site inventory + accessor allowlist

Guard: `app/backend/tests/test_ai_call_site_inventory.py` (a genuinely new concern -> a new file,
not an extension). Guard-only milestone: the surface already conforms, so the 3-move is MEASURE
(inventory the sets) -> CONFORM (already zero-drift) -> ENFORCE (pin the exact sets; a new
label/caller/raw-client is red until the matching EXPECTED_* set is bumped in the same change).

| Inventory | Pinned set | Source |
|---|---|---|
| AI operation labels | `explain_score`, `propose_sweep`, `grade_advice`, `draft_methods`, `draft_legend` (5) | `request_type` dispatch in `ai/gateway.py` (extracted dynamically -> non-vacuous) |
| `stamp_ai_actions` callers | `ai/execute.py`, `routers/ai.py` (2) | def lives in `companions/provenance.py` (excluded) |
| Raw model-client homes | `ai/live/pydantic_gateway.py` (1) | `AnthropicModel(...)` construction; other providers denied elsewhere |
| Gateway selection factory | `get_action_gateway` in `routers/ai.py` (1) | impls asserted present: `ai/gateway.py`, `ai/live/pydantic_gateway.py`, `ai/live/vercel_gateway.py` |

**VERIFY (deferred, recorded not built):** Selom's gateways already **budget-assert** (`ai_token_budget`
/ `ai_timeout_s` threaded into `PydanticAIGateway`/`VercelAIGateway`) and **degrade-clean** in both
directions (any error/timeout -> the byte-identical deterministic fallback). They do NOT emit a
trace span or **record usage metering** (the `withGatewayGuard` budget-assert -> trace -> record-usage
shape). Metering is **warranted once the live gateway is a paid product path at scale** -> deferred to
that point (build-now-gate-later), recorded here. No metering built in M-003.

Gate green: the 4 inventory guards pass; ruff clean. No source changed (guard-only) -> BE fast gate
unchanged from M-002 (**1214 / 1 skipped**) + the 4 new guards.

**Tooling note (owner-endorsed 2026-07-09):** adopt `pytest-xdist` (`pytest -n auto`) for the fast
gate; PIN it in the backend dev deps as part of **M-004** so CI + every invocation parallelize
reproducibly (currently installed only in the owner's env, absent from `pyproject.toml`/`uv.lock`/
`.venv`).

## M-004 -- CI supply-chain hardening + stable aggregate required-check

Files: `.github/workflows/ci.yml` (new; consolidates + replaces `backend-ci.yml` + `frontend-ci.yml`,
both removed), `renovate.json` (new), `app/backend/pyproject.toml` (+`pytest-xdist`).
MEASURE (zizmor `v1.26.1`, `--persona=regular`) taken 2026-07-09.

### Gate -- workflow supply-chain (zizmor)

| Audit | MEASURE (old backend-ci + frontend-ci) | CONFORM (new ci.yml) |
|---|---|---|
| `unpinned-uses` (high) | 4 (checkout/setup-uv/checkout/setup-node, all tag-pinned) | 0 -- every `uses:` a 40-char SHA + tag comment |
| `excessive-permissions` (med) | 2 (no `permissions:` block on either workflow) | 0 -- `permissions: contents: read` at workflow level, no job widens it |
| `artipacked` (med) | 2 (checkout persists credentials) | 0 -- `persist-credentials: false` on every checkout |
| **total actionable** | **8** (14 findings, 6 suppressed) | **0** ("No findings to report", exit 0) |

**3-move preserved:** MEASURE (8 on the old workflows) -> CONFORM (0 on the new `ci.yml`, proven
locally via `uv tool run zizmor@latest`) -> ENFORCE (the blocking zizmor job is only added once the
workflow it gates is already zero; branch protection is owner-run, below).

### Consolidation

One `ci.yml`, since two path-filtered workflows can never be a required check (a skipped required
check blocks a PR forever) and `needs:` only aggregates within ONE workflow:

- `changes` (dorny/paths-filter, SHA-pinned) -> `backend`/`frontend` booleans;
- `backend` (path-gated; ruff + `pytest -m "not slow" -n auto`; steps moved verbatim + xdist) and
  `frontend` (path-gated; lint + tsc + vitest + `next build`; verbatim);
- `hygiene` (`hygiene-scan.mjs --all`, NOT path-filtered) + `workflow-lint` (zizmor, NOT filtered);
- `ci` aggregate (`needs:` all; `if: always()`; passes iff no required job FAILED/cancelled --
  skipped == pass) = the single stable required-check name, invariant under future sharding.

**DL-017 (stub scope):** the light fast-gate closure omits the omics extras, so `auto` resolves the
STUB engine for the science skills -- the required gate protects structure/contract/provenance, not
real deg/gsea. NO literal `SELOM_SKILLS_ENGINE=stub` env is set: the prod-boot tests mock `find_spec`
and would refuse to boot under a forced global stub (would break `test_config_accepts_valid_s3`).

**pytest-xdist:** pinned in the `dev` extra so CI's `uv sync` installs it and the backend job runs
`-n auto`. `uv.lock` NOT regenerated here -- a clean `uv lock` re-resolves/bumps the whole tree
(+900 lines, unrelated packages), out of M-004 scope; `uv sync` (no `--locked`) resolves the new dep
as it already does for the extras. A deliberate `uv lock` refresh is a separate Codex-lane task.

### ENFORCE -- owner-run (VERIFY before flip)

1. Push the branch; open a PR (or push to a branch) so `ci` runs green once (this is the first live
   zizmor + `-n auto` MEASURE on CI infra).
2. Branch-protect `main` requiring exactly the check name **`ci`**, `enforce_admins: false` (GitHub
   Pro on a private repo -- owner has it), so the solo owner keeps direct-push while PRs are gated.
3. Keep the git identity `282747725+steveneam@users.noreply.github.com` (Vercel).

Verified locally: zizmor 0 on `ci.yml`; `ci.yml` + `renovate.json` parse. The path-trio behavior
(docs-only -> `ci` success with backend+frontend skipped; backend-only -> only backend runs) is
verified on the first GitHub run (cannot run Actions locally).

## M-005 -- parallel-lane worktree tooling

Tooling milestone (no MEASURE/CONFORM/ENFORCE gate; acceptance = each artifact exists + works). Files:
`app/frontend/scripts/guard-worktree-install.mjs` (+ FE `package.json` `preinstall` wire),
`scripts/worktree-setup.ps1`, `.claude/settings.json`, `COORDINATION.md`,
`docs/operating/contract-window.md`.

| Artifact | What | Verified |
|---|---|---|
| `guard-worktree-install.mjs` | FE `preinstall` refusing `npm install` inside a worktree (`.git`-as-file); escape `SELOM_WORKTREE_INSTALL_OK=1` | main tree -> exit 0 (owner/CI unaffected); worktree -> exit 1 (blocks); escape -> exit 0 |
| `worktree-setup.ps1` | junction FE `node_modules` + BE `.venv` into a lane; copy `.worktreeinclude`; verify toolchain; idempotent; **teardown = `rmdir /s /q`, never `Remove-Item -Recurse`**; main `node_modules` count snapshot before/after | pure ASCII; PowerShell parse OK |
| `.claude/settings.json` | `includeCoAuthoredBy: false` (makes the no-AI-signoff rule EXECUTABLE) + `worktree.symlinkDirectories` (admin-inert; the junction script is the real guarantee) | valid JSON |
| `COORDINATION.md` | Mode A (<=2 lanes, in-session subagents) vs Mode B (>2, vscode method); one-web-writer-per-wave; pre-provision-at-prep; kill-by-port-listener; **merge-gate section updated to the M-004 `ci` required check** | board trailing-newline intact |
| `contract-window.md` | freeze FE contract types + BE schema before fork; additive-only in-window; each invariant names its executable test; one window/sprint/owner | referenced from the playbook + COORDINATION |

The FE env-reader guard (M-002) allowlists `scripts/`, so the new `.mjs`'s `process.env` read is
clean; FE structure guard green.
