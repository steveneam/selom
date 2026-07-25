#!/usr/bin/env bash
# browser-verify.sh -- drive a REAL figure into the editor and run the browser checks against it.
#
# WHY THIS EXISTS. tsc, eslint and vitest cannot see layout, and `dev:mock` proves the wire, not the
# content. So every layout/affordance claim in the milestone review and the Lane 3 wrap shipped as
# "arithmetic-backed prediction from CSS that no browser ever observed". This is the instrument that
# observes them -- on a real backend, with real data, in a real browser.
#
# It is a HARNESS, not a one-off: `e2e/browser-verify/fixtures.ts` exports the `editor` fixture that
# lands a real figure in the editor, and every check is a spec that consumes it. Adding a check is a
# new .spec.ts, not a new bespoke script [[compound-capability-each-task]].
#
# WHAT IT DRIVES (do not shortcut it -- four shortcuts have already failed):
#   new project -> name it -> drop a real DE CSV -> confirm intake -> run the proposed skill.
# A completed run is the ONLY thing that calls `figure.init(spec)`, and the editor renders off the
# LIVE store's spec, not the persisted record. Demo projects, API-created projects and localStorage
# injection all dead-end; `?demo=` is mock-mode only.
#
# SERVERS. Playwright's `webServer` starts the backend (:8152) and the frontend (:8152-proxied,
# :3152) on demand and STOPS them on exit. `:8000` is eamos and `:3000` is shared on this box --
# never bind either. An already-running server on those ports is reused.
#
# FRESH EVERY RUN. The harness owns its SQLite store and DELETES it before each run, because the
# checks must be re-runnable and identical each time. Without this the store accumulates a project +
# a dataset + a full figure spec per run; the FE's reconcile then pulls every one of those specs
# (a volcano over 16,760 genes is megabytes of JSON) on each page load, and the drive gets slower
# every session until it blows the test timeout. Measured: run 4 exceeded 180s in setup.
# Pass --keep-db to accumulate deliberately (e.g. inspecting what a previous run wrote).
#
# USAGE
#   scripts/browser-verify.sh                    # every check
#   scripts/browser-verify.sh d5                 # only specs matching "d5"
#   scripts/browser-verify.sh --headed           # watch it drive
#   scripts/browser-verify.sh --ui               # Playwright's interactive UI
#   scripts/browser-verify.sh --keep-db          # do NOT reset the harness store first
#   ANNOTATION=on scripts/browser-verify.sh      # render the DEFERRED annotation layer (Plan C
#                                                # territory -- file findings against Plan C's spec,
#                                                # never close them as shipped-and-fine)
#
# ENV
#   SELOM_DATASETS_DIR   REQUIRED -- the real-data corpus. Mock data cannot settle a content-shaped
#                        layout claim, so the harness refuses to run without it.
#   SELOM_BV_FIXTURE_CSV override the input (default: a real EYG_28 bulk-DE export, which routes to
#                        `volcano` at score 100 and returns a RESPONSIVE spec -- no layout.width).
#   SELOM_BV_BE_PORT / SELOM_BV_FE_PORT   override the derived lane ports (8152 / 3152).
#   SELOM_BV_CHROMIUM    explicit Chromium binary (else the newest downloaded ms-playwright build).
#
# Exit: 0 = every check passed. Non-zero = at least one failed. Read the output RAW -- never pipe
# this through `| tail`, which returns tail's status and discards the failure
# [[read-gate-output-raw-not-piped]].

set -u -o pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "[browser-verify] not inside a git checkout -- cannot locate the repo root; aborting." >&2
    exit 2
}
FE="$ROOT/app/frontend"

if [ -z "${SELOM_DATASETS_DIR:-}" ]; then
    cat >&2 <<'EOF'
[browser-verify] SELOM_DATASETS_DIR is unset.

The harness verifies on REAL data, never mock -- a mock proves the wire, not the content, and every
check here is content-shaped (long axis titles, real legend text). Point it at the corpus:

    export SELOM_DATASETS_DIR=/path/to/selom-data

EOF
    exit 2
fi

if [ ! -d "$SELOM_DATASETS_DIR" ]; then
    echo "[browser-verify] SELOM_DATASETS_DIR does not exist: $SELOM_DATASETS_DIR" >&2
    exit 2
fi

# `ANNOTATION=on` is the ergonomic alias for the real flag. Anything checked with it ON is testing
# DEFERRED Plan C territory (docs/pillar-2-direct-manipulation/annotation-remediation-spec.md).
if [ -n "${ANNOTATION:-}" ]; then
    export NEXT_PUBLIC_ANNOTATION_LAYER="$ANNOTATION"
    echo "[browser-verify] NEXT_PUBLIC_ANNOTATION_LAYER=$ANNOTATION -- results are Plan C territory," >&2
    echo "                 to be filed against the annotation spec, NOT closed as shipped-and-fine." >&2
fi

# Reset the harness's own store unless asked not to. Scoped hard to the harness directory so this
# can never touch the corpus, the repo, or a real database.
KEEP_DB=0
ARGS=()
for a in "$@"; do
    if [ "$a" = "--keep-db" ]; then KEEP_DB=1; else ARGS+=("$a"); fi
done

BV_DIR="$SELOM_DATASETS_DIR/_selom-browser-verify"
if [ $KEEP_DB -eq 0 ] && [ -d "$BV_DIR" ]; then
    rm -f "$BV_DIR"/browser-verify.db "$BV_DIR"/browser-verify.db-wal "$BV_DIR"/browser-verify.db-shm
    echo "[browser-verify] store  : reset ($BV_DIR)"
    # The backend opens the DB at startup, so a reset needs a backend that starts AFTER it. If one is
    # already up on the port it is holding the deleted file — stop it and let Playwright start a new one.
    if curl -sf "http://127.0.0.1:${SELOM_BV_BE_PORT:-8152}/health" >/dev/null 2>&1; then
        pkill -f "uvicorn main:app.*--port ${SELOM_BV_BE_PORT:-8152}" 2>/dev/null
        sleep 1
        echo "[browser-verify] store  : stopped the backend that held the old store"
    fi
else
    [ $KEEP_DB -eq 1 ] && echo "[browser-verify] store  : KEPT (--keep-db)"
fi

cd "$FE" || exit 2

echo "[browser-verify] corpus : $SELOM_DATASETS_DIR"
echo "[browser-verify] ports  : backend ${SELOM_BV_BE_PORT:-8152} / frontend ${SELOM_BV_FE_PORT:-3152}"
echo

npx playwright test --config=playwright.browser-verify.config.ts "${ARGS[@]}"
STATUS=$?

echo
if [ $STATUS -eq 0 ]; then
    echo "[browser-verify] PASS -- every check that ran passed."
else
    echo "[browser-verify] FAIL (exit $STATUS) -- read the failures above; a trace is in app/frontend/test-results/."
fi
exit $STATUS
