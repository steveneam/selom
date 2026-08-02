#!/usr/bin/env bash
# skill-smoke.sh -- run EVERY registered skill against the real corpus and gate on the result.
#
# WHY THIS EXISTS. "Are all the skills working?" had no answer in this repo, so it got answered
# from impression. The golden tests (tests/test_skills_golden.py) pin every skill's dependency-free
# STUB to a snapshot -- by construction they say nothing about whether the real engine runs. This
# runs the real engines on real data and publishes the result as docs/skill-coverage/matrix.md.
#
# CONTRACT. Exits non-zero when a skill the committed matrix records as PASSING no longer passes,
# when a registered skill has no row, or when a row exists for a skill that no longer exists. Every
# gate here runs RAW -- no pipe, no `| tail` -- because a pipeline returns the FILTER's exit status
# and throws the real one away (CLAUDE.md's ratchet ladder; [[read-gate-output-raw-not-piped]]).
#
# The run pins SELOM_SKILLS_ENGINE=real and disables the result caches (skills/smoke.py:pin_process),
# so no row can be a stub figure or a cache hit dressed up as a pass.
#
# USAGE
#   scripts/skill-smoke.sh                      # run + compare; non-zero on regression
#   scripts/skill-smoke.sh --write              # regenerate the committed matrix from this run
#   scripts/skill-smoke.sh --only deg,volcano   # a subset (never with --write)
#   scripts/skill-smoke.sh --install-artifacts  # stage the gitignored GO build outputs, then exit
#
# ENV
#   SELOM_DATASETS_DIR   REQUIRED. The real corpus; without it every row is "not run", which is
#                        not the same gate and this script refuses to pretend otherwise.
#
# Exit: 0 = no regression. 1 = a regression / a failing skill. 2 = usage or precondition error.

set -u -o pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "[smoke] not inside a git checkout -- cannot locate the repo root; aborting." >&2
    exit 2
}
BE="$ROOT/app/backend"

command -v uv >/dev/null 2>&1 || {
    echo "[smoke] 'uv' is not on PATH -- the backend runs under uv (astral.sh/uv); aborting." >&2
    exit 2
}

# --------------------------------------------------------------- gitignored build artefacts
# go_graph's real engine loads skills/go_graph/go_dag.json and enrichment prefers
# skills/enrichment/gene_sets_go.json. Both are GITIGNORED build outputs (~12 MB), so a fresh
# checkout has NO working go_graph at all -- it raises FileNotFoundError, it does not degrade.
# Staged copies live in the corpus; this installs them. Rebuild from source instead with:
#   uv run --with obonet --directory app/backend python scripts/build_gene_sets.py
install_artifacts() {
    local src="${SELOM_DATASETS_DIR:-}/genesets"
    local rc=0
    [ -d "$src" ] || { echo "[smoke] no staged artefacts at $src" >&2; return 2; }
    for pair in "go_dag.json:skills/go_graph/go_dag.json" \
                "gene_sets_go.json:skills/enrichment/gene_sets_go.json"; do
        local from="$src/${pair%%:*}" to="$BE/${pair##*:}"
        if [ ! -f "$from" ]; then
            echo "[smoke] MISSING staged artefact: $from" >&2; rc=2; continue
        fi
        if [ -f "$to" ]; then
            echo "[smoke] already installed: ${pair##*:}"
        else
            cp "$from" "$to" && echo "[smoke] installed ${pair##*:} from the corpus"
        fi
    done
    return $rc
}

ARGS=()
for arg in "$@"; do
    case "$arg" in
        --install-artifacts) install_artifacts; exit $? ;;
        -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
        *) ARGS+=("$arg") ;;
    esac
done

if [ -z "${SELOM_DATASETS_DIR:-}" ]; then
    echo "[smoke] SELOM_DATASETS_DIR is unset. Every skill would report 'not run', which is NOT a" >&2
    echo "[smoke] pass -- refusing to produce a matrix that looks like coverage. Export it first:" >&2
    echo "[smoke]   export SELOM_DATASETS_DIR=/path/to/selom-data" >&2
    exit 2
fi
[ -d "$SELOM_DATASETS_DIR" ] || {
    echo "[smoke] SELOM_DATASETS_DIR does not exist: $SELOM_DATASETS_DIR" >&2
    exit 2
}

# Pin the engine selectors HERE, not inside the module: env selection belongs to config.Settings
# (backend structure guard M-002), and skills/smoke.py refuses to run if these are not set -- so an
# unpinned run is a loud error, never a matrix full of stub figures wearing a PASS. The caches are
# switched off in-process as well (skills/smoke.py:pin_process); the env vars are belt and braces.
export SELOM_SKILLS_ENGINE=real
export SELOM_UMAP_ENGINE=scanpy
export SELOM_RESULT_CACHE=off
export SELOM_INPUT_CACHE=off

echo "[smoke] corpus: $SELOM_DATASETS_DIR"
echo "[smoke] engines pinned real; result + input caches off"
echo "[smoke] running every registered skill through its real engine (this takes minutes) ..."

# RAW: output straight to the terminal, status taken from the command itself.
rc=0
( cd "$BE" && uv run python -m skills.smoke "${ARGS[@]+"${ARGS[@]}"}" ) || rc=$?

echo
if [ "$rc" -eq 0 ]; then
    echo "[smoke] RESULT: PASS -- no skill regressed against docs/skill-coverage/matrix.md."
else
    echo "[smoke] RESULT: FAIL (exit $rc) -- read the raw rows above, not just this line."
fi
exit "$rc"
