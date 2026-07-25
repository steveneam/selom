#!/usr/bin/env bash
# lane-status.sh -- the correct probe for parallel-lane worktrees, and a gated teardown.
#
# WHY THIS EXISTS. Driving three lanes in Sprint 2 produced two mistakes that were both *probe* errors,
# not lane errors. Encoding the probe once means the next sprint cannot repeat them:
#
#   1. A hand-rolled loop built the path as `selom-lane$s` with `s=l1`, giving `selom-lane` + `l1`.
#      `git -C <bad-path> log … 2>/dev/null | wc -l` then printed `0`, so all three lanes were reported
#      as having made ZERO commits while they were committing steadily. A suppressed failure reads
#      exactly like data. This script derives paths from `git worktree list` -- it cannot mistype them --
#      and never discards stderr on a command whose result it reports.
#
#   2. An idle Claude Code composer REDISPLAYS ITS LAST SUBMITTED MESSAGE, DIMMED (`ESC[2m`).
#      `tmux capture-pane -p` strips colour, so that echo is indistinguishable from unsent draft text
#      parked in the composer. Three lanes were read as "waiting on founder input" and teardown was held
#      for text that did not exist. This script captures WITH escapes (`-e`) and reports
#      `composer=echo(dim)` vs `composer=DRAFT` on that basis.
#
# COMPLETION SIGNAL (thalon's protocol): new commits + a WRAP file + an idle pane. BLOCKED means the lane
# wrote its blocker into the wrap file and stopped -- lanes are instructed never to idle on a question.
#
# USAGE
#   scripts/lane-status.sh                 # status of every agent/* worktree
#   scripts/lane-status.sh --teardown      # remove lanes that are FULLY MERGED and CLEAN; refuse otherwise
#
# Exit: 0 = every lane wrapped (or, with --teardown, every lane removed). 1 = something needs attention.

set -u -o pipefail

TEARDOWN=0
[ "${1:-}" = "--teardown" ] && TEARDOWN=1
[ $# -gt 0 ] && [ "$TEARDOWN" -eq 0 ] && { echo "usage: $0 [--teardown]" >&2; exit 2; }

MAIN=$(git rev-parse --show-toplevel) || { echo "not in a git checkout" >&2; exit 2; }
cd "$MAIN" || exit 2

# Lane worktrees, derived (never hand-built) from git itself.
mapfile -t LANES < <(git worktree list --porcelain | awk '
  /^worktree /   { wt=$2 }
  /^branch /     { br=$2; if (br ~ /refs\/heads\/agent\//) { sub("refs/heads/","",br); print wt"\t"br } }')

if [ ${#LANES[@]} -eq 0 ]; then
    echo "[lane-status] no agent/* lane worktrees. Nothing to do."
    exit 0
fi

ATTENTION=0
for row in "${LANES[@]}"; do
    dir=${row%%$'\t'*}; branch=${row##*$'\t'}
    name=$(basename "$dir")
    sess=$(tmux list-sessions -F '#S' 2>/dev/null | grep -x -m1 -e "$name" -e "lane-${name##*-}" || true)

    commits=$(git -C "$dir" rev-list --count "main..$branch")
    unmerged=$(git -C "$dir" rev-list --count "main..$branch")
    dirty=$(git -C "$dir" status --porcelain | grep -vE 'LANE-(WRAP|KICKOFF)\.md|\.venv|node_modules' | wc -l)
    wrap=no; [ -f "$dir/LANE-WRAP.md" ] && wrap=YES
    contained=no; git merge-base --is-ancestor "$branch" main 2>/dev/null && contained=YES

    pane=absent composer=-
    if [ -n "$sess" ]; then
        pane=alive
        # Capture WITH escapes: a dimmed line (ESC[2m) is an echo of the last SUBMITTED message, not a draft.
        raw=$(tmux capture-pane -e -p -t "$sess" 2>/dev/null | grep -a '❯' | head -1 || true)
        if [ -z "$(printf '%s' "$raw" | sed 's/\x1b\[[0-9;]*m//g; s/[^[:print:]]//g; s/❯//; s/^[[:space:]]*//; s/[[:space:]]*$//')" ]; then
            composer=empty
        elif printf '%s' "$raw" | grep -q $'\x1b\[2m'; then
            composer='echo(dim)'   # last submitted message redisplayed -- NOT pending input
        else
            composer=DRAFT         # genuinely unsubmitted text
        fi
    fi

    printf '%-22s %-34s commits=%-3s wrap=%-3s dirty=%-3s merged=%-3s pane=%-7s composer=%s\n' \
        "$name" "$branch" "$commits" "$wrap" "$dirty" "$contained" "$pane" "$composer"

    [ "$wrap" = YES ] || ATTENTION=1
    [ "$composer" = DRAFT ] && { echo "    ^ genuinely unsubmitted text in this pane -- resolve before teardown"; ATTENTION=1; }
    [ "$pane" = absent ] && [ "$wrap" != YES ] && echo "    ^ pane gone with no wrap: crashed. THE WORKTREE SURVIVES -- inspect its git status/log/stash before redoing anything."

    if [ "$TEARDOWN" -eq 1 ]; then
        if [ "$contained" != YES ] || [ "$unmerged" -ne 0 ]; then
            echo "    REFUSING teardown: $branch is not fully contained in main ($unmerged unmerged) -- merge it first."
            ATTENTION=1; continue
        fi
        if [ "$dirty" -ne 0 ]; then
            echo "    REFUSING teardown: $dirty uncommitted change(s) in $dir -- commit or discard first."
            ATTENTION=1; continue
        fi
        [ -n "$sess" ] && tmux kill-session -t "$sess" 2>/dev/null && echo "    killed session $sess"
        git worktree remove --force "$dir" && echo "    removed worktree $dir"
        git branch -d "$branch" && echo "    deleted branch $branch"
    fi
done

if [ "$TEARDOWN" -eq 1 ]; then
    echo
    echo "[lane-status] main tree check -- provisioning/teardown must never touch it:"
    printf '  app/frontend/node_modules entries: %s\n' "$(find "$MAIN/app/frontend/node_modules" -mindepth 1 2>/dev/null | wc -l)"
    printf '  app/backend/.venv present: %s\n' "$([ -d "$MAIN/app/backend/.venv" ] && echo yes || echo NO)"
fi

exit "$ATTENTION"
