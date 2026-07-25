#!/usr/bin/env bash
# worktree-setup.sh -- provision a Selom parallel-lane git worktree on Linux.
#
# Linux port of scripts/worktree-setup.ps1 (eng-practices port M-005), which is Windows-only:
# junctions, `.venv\Scripts\python.exe`, `cmd /c rmdir`. The box is Linux now, so the lane partition
# in docs/next-session-plan/plan.md had no working provisioning tool. This is it.
#
# WHAT IT DOES. Symlinks the single MAIN-checkout `app/frontend/node_modules` and `app/backend/.venv`
# into a lane worktree so a lane shares deps without a multi-GB reinstall, copies the
# `.worktreeinclude` files (gitignored context the checkout does not carry -- notably
# `app/backend/.env`, which holds the cloud OAuth creds), and asserts the link set RESOLVES.
# Idempotent: re-running is a no-op.
#
# WHY IT ASSERTS AT SETUP. Node module resolution walks UP the tree to the main checkout, so a
# half-broken link set still passes tests while tools that need workspace-nested deps (eslint) fail --
# and it fails at the merge train, hours later, looking like a code problem. Catch it here instead.
#
# USAGE (from anywhere)
#   git worktree add /home/deploy/work/selom-lane1 -b agent/backend-integrity/l1
#   scripts/worktree-setup.sh /home/deploy/work/selom-lane1
#
# TEARDOWN
#   git worktree remove /home/deploy/work/selom-lane1
# On Linux `rm -rf` does NOT descend into a symlinked directory (it unlinks the symlink), so the
# catastrophic-teardown hazard the PowerShell version guards against does not exist in the same form
# here. The main-tree file-count guard below is kept anyway: it is nearly free, and it is the ratchet
# that proves provisioning never wrote into the main tree.
#
# Exit: 0 = lane ready. 1 = refused / verification failed. 2 = usage error.

set -u -o pipefail

step() { echo "[worktree-setup] $*"; }
die()  { echo "[worktree-setup] ERROR: $*" >&2; exit "${2:-1}"; }

[ $# -ge 1 ] || die "usage: scripts/worktree-setup.sh <worktree-path> [main-checkout]" 2

command -v git >/dev/null 2>&1 || die "git not on PATH"

WORKTREE=$1
MAIN=${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}

[ -d "$WORKTREE" ] || die "worktree path does not exist: $WORKTREE
  create it first:  git worktree add $WORKTREE -b agent/<bucket>/<slug>"

WORKTREE=$(cd "$WORKTREE" && pwd)
MAIN=$(cd "$MAIN" && pwd)

[ "$WORKTREE" != "$MAIN" ] || die "worktree equals the main checkout ($MAIN) -- refusing"

# A worktree's .git is a FILE (a `gitdir:` pointer); the main checkout's is a directory.
[ -d "$WORKTREE/.git" ] && die "$WORKTREE looks like a MAIN checkout (.git is a directory), not a worktree -- refusing"
[ -e "$WORKTREE/.git" ] || die "$WORKTREE has no .git entry -- is it really a git worktree?"

step "main:     $MAIN"
step "worktree: $WORKTREE"

# ------------------------------------------------------------------ teardown-safety: before snapshot
MAIN_NM="$MAIN/app/frontend/node_modules"
count_files() { [ -d "$1" ] && find "$1" -mindepth 1 2>/dev/null | wc -l || echo 0; }
BEFORE=$(count_files "$MAIN_NM")
step "main node_modules entry count (before): $BEFORE"

# --------------------------------------------------------------------------------- link the dep sets
# Symlinks, not junctions: on Linux they need no privileges and resolve for node + uv alike.
link_one() {
    local target=$1 link=$2
    if [ ! -e "$target" ]; then
        step "SKIP (no main target yet -- provision it in the MAIN checkout first): ${target#"$MAIN"/}"
        return 0
    fi
    if [ -L "$link" ]; then
        local cur; cur=$(readlink -f "$link" 2>/dev/null || true)
        if [ "$cur" = "$(readlink -f "$target")" ]; then
            step "OK (already linked): ${link#"$WORKTREE"/}"
            return 0
        fi
        die "existing symlink points elsewhere: $link -> $cur (expected $target). Remove it and re-run."
    fi
    [ -e "$link" ] && die "refusing to replace a REAL directory with a symlink: $link
  a lane must share the main tree's deps, not carry its own copy. Remove it first (rm -rf '$link')."
    mkdir -p "$(dirname "$link")" || die "cannot create parent of $link"
    ln -s "$target" "$link" || die "failed to link $link -> $target"
    step "linked: ${link#"$WORKTREE"/} -> ${target#"$MAIN"/}"
}

link_one "$MAIN/app/frontend/node_modules" "$WORKTREE/app/frontend/node_modules"
link_one "$MAIN/app/backend/.venv"         "$WORKTREE/app/backend/.venv"

# ---------------------------------------------------------------- copy the .worktreeinclude context
# gitignore-ish syntax; only plain FILE patterns are copied (no globs, no directories) -- the same
# subset the PowerShell version handles, kept deliberately dumb.
INCLUDE="$MAIN/.worktreeinclude"
if [ -f "$INCLUDE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        pat=$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        case "$pat" in ''|'#'*|'**'*) continue ;; esac
        src="$MAIN/$pat"
        [ -f "$src" ] || continue
        dst="$WORKTREE/$pat"
        mkdir -p "$(dirname "$dst")" && cp -f "$src" "$dst" && step "copied: $pat"
    done < "$INCLUDE"
fi

# ------------------------------------------------------------------------------ verify the toolchain
# Resolution must work THROUGH the link, which is the failure mode that otherwise surfaces as a
# mystery eslint break at the merge train.
step "verifying toolchain..."
FAIL=0
if [ -e "$WORKTREE/app/frontend/node_modules" ]; then
    [ -d "$WORKTREE/app/frontend/node_modules/next" ] || {
        echo "[worktree-setup] FE node_modules link does not resolve 'next' -- install the MAIN checkout:" >&2
        echo "                 (cd $MAIN/app/frontend && npm install --legacy-peer-deps)" >&2
        FAIL=1
    }
    # eslint is the tool that actually needs workspace-nested resolution; check it explicitly.
    [ -e "$WORKTREE/app/frontend/node_modules/.bin/eslint" ] || {
        echo "[worktree-setup] FE node_modules link does not resolve the 'eslint' binary -- the lint gate" >&2
        echo "                 will fail in this lane. Re-provision the MAIN checkout." >&2
        FAIL=1
    }
else
    echo "[worktree-setup] no FE node_modules link -- the frontend gates cannot run in this lane." >&2
    FAIL=1
fi

if [ -e "$WORKTREE/app/backend/.venv" ]; then
    [ -x "$WORKTREE/app/backend/.venv/bin/python" ] || {
        echo "[worktree-setup] BE .venv link does not resolve bin/python -- run 'uv sync' in $MAIN/app/backend." >&2
        FAIL=1
    }
else
    step "NOTE: BE .venv not linked (no main .venv yet) -- run 'uv sync' in $MAIN/app/backend first."
fi

# --------------------------------------------------------------- teardown-safety: after must match
AFTER=$(count_files "$MAIN_NM")
step "main node_modules entry count (after):  $AFTER"
[ "$BEFORE" = "$AFTER" ] || die "MAIN node_modules entry count changed ($BEFORE -> $AFTER) -- provisioning must NEVER write into the main tree. Investigate before proceeding."

[ "$FAIL" -eq 0 ] || die "lane provisioned but the toolchain did NOT verify (see above) -- fix before starting work"

# ------------------------------------------------------------------------------------ lane landmines
# A worktree is a SEPARATE MEMORY NAMESPACE, so a lane session recalls none of this. It is printed
# here and belongs inlined in the lane's kickoff FILE too.
cat <<EOF

[worktree-setup] done. Lane ready: $WORKTREE

  LANDMINES -- inline these in the lane's kickoff file, do not assume recall:
  * NEVER run 'npm install' in this worktree. node_modules is a SYMLINK to the main tree, so an
    install writes THROUGH it and clobbers every other lane. app/frontend/scripts/
    guard-worktree-install.mjs refuses it; do not set SELOM_WORKTREE_INSTALL_OK to get around it.
  * The BE .venv is SHARED the same way. 'uv run' auto-syncs, so a lane that changes
    pyproject.toml/uv.lock MUTATES every other lane's interpreter. A lane needing new BE deps stops
    and re-plans -- it does not sync the shared venv.
  * Dev servers may not run here at all (Turbopack can fatal on out-of-root symlinks). Real-browser
    checks belong on the MAIN checkout after rebase, not in-lane.
  * Gate of record: scripts/verify.sh (it detects a worktree and warns accordingly). Cap test
    parallelism -- SELOM_PYTEST_WORKERS=2, never 'auto': 3 lanes x 6 workers on 6 vCPU oversubscribes.
  * Offset ports per lane (BE :801X, FE :315X). :8000 is eamos on this box -- never bind it.
  * git user.email must stay the noreply address or Vercel blocks deploys.
EOF
