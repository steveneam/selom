#!/usr/bin/env bash
# verify.sh -- Selom's ONE gate of record (next-session-plan P0-08).
#
# WHY THIS EXISTS. Selom had no single verify command, so every session assembled the gate by hand
# and every assembly piped it through `| tail`. That is a silent-failure generator: a pipeline
# returns the exit status of the LAST command, so `pytest | tail` reports tail's success and the
# gate's failure code is thrown away. It cost a peer box two real incidents (forbidden content
# reaching origin behind a swallowed guard failure; a red suite read as green at a session close).
# So: every gate here runs RAW -- output straight to the terminal, no pipe, no redirect -- and its
# status is captured from the command itself. See CLAUDE.md's ratchet ladder ("a guard is only a
# ratchet if enforcement is gated on its exit code") and [[read-gate-output-raw-not-piped]].
#
# CONTRACT. Runs every gate, then exits non-zero if ANY failed. It does not stop at the first
# failure: at the merge train you rebase once and want the whole picture, not the first brick wall.
# The final ledger is the authoritative summary -- a gate that did not run is reported as SKIP, never
# folded into a pass.
#
# GATES (CI parity -- .github/workflows/ci.yml is the source of truth for each command):
#   hygiene  node scripts/guards/hygiene-scan.mjs --all
#   be-lint  uv run ruff check .
#   be-test  uv run pytest -m "not slow" -n "$SELOM_PYTEST_WORKERS"
#   be-slow  env -u SELOM_DATASETS_DIR uv run pytest -m slow -n "$SELOM_PYTEST_WORKERS"
#   fe-lint  npm run lint
#   fe-types npx tsc --noEmit
#   fe-test  npm run test
#   fe-build npm run build            <-- the ONLY gate that catches SSR/integration breaks
#
# be-slow deliberately runs with SELOM_DATASETS_DIR UNSET, which is the one place this script drops
# coverage on purpose -- so read the reason. The `slow` lane (reproduction drives, golden renders,
# real-engine validations) was gated NOWHERE: this script and CI both ran only `-m "not slow"`,
# leaving ~385 of 1907 tests with no gate. That is how the pandas-3/pyarrow h5ad breakage survived,
# and how a signature change left 7 tests broken while this gate reported PASS. Corpus-free the lane
# is ~16s and catches exactly that class (measured 2026-08-03: 352 pass / 0 fail against CI's own
# dependency closure); WITH the corpus it is ~7.5 min, which would make the gate of record too
# expensive to keep running. So it is a BREAKAGE gate at CI parity -- numerical regression over real
# data stays with `scripts/skill-smoke.sh` and a full local `uv run pytest` at a milestone.
#
# fe-build is in the default set on purpose. tsc + eslint + vitest all pass on a tree whose pages
# throw on server render (a WebGL import escaping `dynamic(..., {ssr:false})` is the standing
# example), so a train that skips the build can merge a broken app with a green gate
# [[full-app-smoke-test-before-handoff]]. It is also the slowest gate -- `--fast` drops it for
# inner-loop use, and says so in the ledger.
#
# USAGE
#   scripts/verify.sh                 # every gate (use this at the merge train)
#   scripts/verify.sh --fast          # skip fe-build
#   scripts/verify.sh --be            # hygiene + backend only
#   scripts/verify.sh --fe            # hygiene + frontend only
#   scripts/verify.sh --force-build   # run fe-build even in a worktree (it will fail; see the note)
#   scripts/verify.sh --list          # print the gate commands and exit
#
# ENV
#   SELOM_PYTEST_WORKERS   xdist workers, default 2. NOT `auto`: three concurrent lanes x 6 workers
#                          on 6 vCPU oversubscribes the box (next-session-plan P0-09). CI uses auto
#                          because it owns its whole runner.
#   SELOM_DATASETS_DIR     real-data corpus. Unset => data-backed tests SKIP, and a suite that
#                          skipped its real-data coverage is not the same gate. Warned about below.
#
# Exit: 0 = every gate that ran passed. 1 = at least one gate failed. 2 = usage/precondition error.

set -u -o pipefail

# ---------------------------------------------------------------------------- resolve the checkout
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "[verify] not inside a git checkout -- cannot locate the repo root; aborting." >&2
    exit 2
}
BE="$ROOT/app/backend"
FE="$ROOT/app/frontend"

WANT_HYGIENE=1 WANT_BE=1 WANT_FE=1 WANT_BUILD=1 LIST_ONLY=0 FORCE_BUILD=0
for arg in "$@"; do
    case "$arg" in
        --fast)        WANT_BUILD=0 ;;
        --be)          WANT_FE=0 ;;
        --fe)          WANT_BE=0 ;;
        --force-build) FORCE_BUILD=1 ;;
        --list)        LIST_ONLY=1 ;;
        -h|--help) sed -n '2,48p' "$0"; exit 0 ;;
        *) echo "[verify] unknown argument: $arg (try --help)" >&2; exit 2 ;;
    esac
done

WORKERS="${SELOM_PYTEST_WORKERS:-2}"

if [ "$LIST_ONLY" -eq 1 ]; then
    echo "hygiene   node scripts/guards/hygiene-scan.mjs --all"
    echo "be-lint   uv run ruff check .                       (cwd: app/backend)"
    echo "be-test   uv run pytest -m 'not slow' -n $WORKERS   (cwd: app/backend)"
    echo "be-slow   uv run pytest -m slow -n $WORKERS         (cwd: app/backend, corpus-free)"
    echo "fe-lint   npm run lint                              (cwd: app/frontend)"
    echo "fe-types  npx tsc --noEmit                          (cwd: app/frontend)"
    echo "fe-test   npm run test                              (cwd: app/frontend)"
    echo "fe-build  npm run build                             (cwd: app/frontend)"
    exit 0
fi

# ------------------------------------------------------------------- fail CLOSED on missing tools
# A gate that cannot run must never pass silently -- same rule as .githooks/pre-commit.
need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "[verify] required tool '$1' not on PATH -- $2" >&2
        echo "[verify] refusing to report a partial gate as a pass; aborting." >&2
        exit 2
    }
}
need git "cannot resolve the checkout"
[ "$WANT_HYGIENE" -eq 1 ] && need node "the hygiene scanner is a node script"
[ "$WANT_BE" -eq 1 ] && need uv "the backend gates run under uv (astral.sh/uv)"
if [ "$WANT_FE" -eq 1 ]; then
    need npm "the frontend gates run under npm"
    [ -d "$FE/node_modules" ] || {
        echo "[verify] $FE/node_modules is missing -- run 'npm install --legacy-peer-deps' in the" >&2
        echo "[verify] MAIN checkout (never inside a worktree; see scripts/worktree-setup.sh)." >&2
        exit 2
    }
fi

# --------------------------------------------------------------------------------- context warnings
# Surfaced BEFORE the run so they are visible even when the scrollback is long, and repeated in the
# ledger so a skipped-coverage run can never be mistaken for a full one.
NOTES=()
if [ "$WANT_BE" -eq 1 ] && [ -z "${SELOM_DATASETS_DIR:-}" ]; then
    NOTES+=("SELOM_DATASETS_DIR is unset -- real-data tests SKIPPED, so be-test is a weaker gate than CI's.")
fi
IN_WORKTREE=0
if [ -f "$ROOT/.git" ]; then
    # `.git` as a FILE means this is a worktree (a gitdir pointer), not the main checkout.
    IN_WORKTREE=1
    NOTES+=("Running inside a git WORKTREE. Measured on this box: fe-lint, fe-types and fe-test all resolve correctly through the shared node_modules symlink, but fe-build CANNOT run -- Turbopack rejects it ('Symlink node_modules is invalid, it points out of the filesystem root'). So fe-build is a MERGE-TRAIN gate on the main checkout, never an in-lane one.")
fi

# A gate that cannot pass in this environment is noise, not signal -- reporting it as FAIL every run
# is how a ledger stops being read. Report it as NOT RUN, with the reason and where it must run
# instead. Never folded into a pass. --force-build overrides if you want to watch it fail.
BUILD_SKIP_REASON=""
if [ "$WANT_FE" -eq 1 ] && [ "$WANT_BUILD" -eq 1 ] && [ "$IN_WORKTREE" -eq 1 ] && [ "$FORCE_BUILD" -eq 0 ]; then
    WANT_BUILD=0
    BUILD_SKIP_REASON="cannot run in a worktree (Turbopack rejects the out-of-root node_modules symlink) -- run the FULL gate on the main checkout at the merge train. Override: --force-build"
fi
if [ ${#NOTES[@]} -gt 0 ]; then
    echo
    for n in "${NOTES[@]}"; do echo "[verify] NOTE: $n"; done
fi

# ------------------------------------------------------------------------------------- run the gates
# run_gate NAME DIR CMD... -- executes CMD with output going straight to the terminal (RAW: no pipe,
# no capture, no filter) and records the command's own exit status.
NAMES=() STATUSES=()
run_gate() {
    local name="$1" dir="$2"; shift 2
    echo
    echo "=============================================================================="
    echo "[verify] GATE $name  --  $* (cwd: ${dir#"$ROOT"/})"
    echo "=============================================================================="
    local rc=0
    ( cd "$dir" && "$@" ) || rc=$?
    NAMES+=("$name"); STATUSES+=("$rc")
    if [ "$rc" -eq 0 ]; then echo "[verify] GATE $name PASSED"; else echo "[verify] GATE $name FAILED (exit $rc)"; fi
    return 0   # never abort the run; the ledger decides the outcome
}

START=$SECONDS

[ "$WANT_HYGIENE" -eq 1 ] && run_gate hygiene "$ROOT" node scripts/guards/hygiene-scan.mjs --all

if [ "$WANT_BE" -eq 1 ]; then
    run_gate be-lint "$BE" uv run ruff check .
    run_gate be-test "$BE" uv run pytest -m "not slow" -n "$WORKERS"
    # `env -u` is the mechanism, not a style choice: run_gate execs an argv array with no shell, so a
    # `VAR= cmd` prefix would be parsed as the COMMAND NAME, not an assignment. See the header note
    # for WHY the corpus is dropped for this one gate.
    run_gate be-slow "$BE" env -u SELOM_DATASETS_DIR uv run pytest -m slow -n "$WORKERS"
fi

if [ "$WANT_FE" -eq 1 ]; then
    run_gate fe-lint  "$FE" npm run lint
    run_gate fe-types "$FE" npx tsc --noEmit
    run_gate fe-test  "$FE" npm run test
    [ "$WANT_BUILD" -eq 1 ] && run_gate fe-build "$FE" npm run build
fi

# ------------------------------------------------------------------------------------- the ledger
ELAPSED=$((SECONDS - START))
FAILED=0
echo
echo "=============================================================================="
echo "[verify] LEDGER  (${ELAPSED}s)"
echo "=============================================================================="
for i in "${!NAMES[@]}"; do
    if [ "${STATUSES[$i]}" -eq 0 ]; then
        printf '  PASS  %s\n' "${NAMES[$i]}"
    else
        printf '  FAIL  %s  (exit %s)\n' "${NAMES[$i]}" "${STATUSES[$i]}"
        FAILED=1
    fi
done

# Report what did NOT run, so a narrowed gate is never read as the full one.
[ "$WANT_BE" -eq 0 ]    && echo "  SKIP  backend gates (--fe)"
[ "$WANT_FE" -eq 0 ]    && echo "  SKIP  frontend gates (--be)"
if [ "$WANT_FE" -eq 1 ] && [ "$WANT_BUILD" -eq 0 ]; then
    if [ -n "$BUILD_SKIP_REASON" ]; then
        echo "  SKIP  fe-build -- $BUILD_SKIP_REASON"
    else
        echo "  SKIP  fe-build (--fast) -- SSR/integration breaks are NOT covered by this run"
    fi
fi
for n in "${NOTES[@]}"; do echo "  NOTE  $n"; done

echo
if [ "$FAILED" -eq 0 ]; then
    echo "[verify] RESULT: PASS -- every gate that ran passed."
else
    echo "[verify] RESULT: FAIL -- see the FAIL rows above. Read the raw output, not just this ledger."
fi
exit "$FAILED"
