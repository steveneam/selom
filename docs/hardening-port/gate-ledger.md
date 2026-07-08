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
