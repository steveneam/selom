#!/usr/bin/env python3
"""Prune stale history out of `agent_handoff/CURRENT.md` into a dated archive file.

The weekly hygiene chore ([[archive-currentmd-history-weekly]]) made reusable: it moves the
**oldest `<!-- prior live-state (session N): … -->` comments** out of CURRENT.md into
`agent_handoff/archive/<date>-current-history.md`, keeping the newest `--keep` of them, and
leaves a one-line pointer behind. History is preserved verbatim, never destroyed (README rule 1);
the EOL style of CURRENT.md is preserved.

WHAT IT DOES (mechanical, safe, idempotent):
  * finds every `<!-- prior live-state (session <digit>…): … -->` comment (single- or multi-line),
  * keeps the newest `--keep` (top of file = newest), appends the rest to the dated archive,
  * replaces the archived span with a pointer comment (which itself does NOT match the pattern,
    so re-running is a no-op once nothing old remains).

WHAT IT DOES NOT DO (do these by hand — they are content, not mechanics):
  * write the new top-of-file live-state paragraph for the current session,
  * wrap the previous live-state paragraph as `<!-- prior live-state (session N): … -->`,
  * refresh the `## Resume Prompt` block, the `## Active Status` cell, or the `## Log Edit-Lock`.
  So the per-session flow is: (1) hand-write the new live-state + wrap the prior one + refresh the
  Resume Prompt / Active Status / lock; (2) run THIS to sweep the now-stale comment tail to archive.

Usage:
  python agent_handoff/prune_current_history.py --dry-run     # preview (counts + what moves)
  python agent_handoff/prune_current_history.py               # keep newest 2, archive the rest
  python agent_handoff/prune_current_history.py --keep 3 --date 2026-06-21

Run on the real machine; --date defaults to today's local date (the machine clock, not a guess).
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

# The progress output includes a "↓" in the session-range label; the Windows console defaults to
# cp1252, which can't encode it. Force utf-8 on stdout so the tool runs anywhere (file writes are
# already utf-8). Guarded — `reconfigure` exists on Python 3.7+ TextIO, absent on some wrapped streams.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CURRENT = os.path.join(HERE, "CURRENT.md")
ARCHIVE_DIR = os.path.join(HERE, "archive")

# Strict: only true per-session comments — a digit OR a `T<n>` tangent-session id after "session ".
# The pointer comments this script writes say "(sessions … archived)" — the `s` (no space) after
# "session" can't match the required "session " + [0-9T], so pointers are skipped and re-runs stay
# idempotent.
PRIOR_RE = re.compile(r"<!-- prior live-state \(session [0-9T].*?-->", re.S)


def _read_keep_eol(path: str) -> tuple[str, str]:
    raw = open(path, "rb").read()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return text, eol


def prune(current: str, keep: int, date: str, dry_run: bool) -> int:
    text, eol = _read_keep_eol(current)
    matches = list(PRIOR_RE.finditer(text))
    print(f"found {len(matches)} prior-live-state comment(s); keeping the newest {keep}.")
    if len(matches) <= keep:
        print("nothing to archive.")
        return 0

    to_archive = matches[keep:]
    start, end = to_archive[0].start(), to_archive[-1].end()
    block = text[start:end]  # verbatim span (may include blank lines / nested pointers)
    sessions = [re.search(r"session ([0-9T]+)", m.group(0)).group(1) for m in to_archive]
    label = f"sessions {sessions[0]} ↓ {sessions[-1]}" if len(sessions) > 1 else f"session {sessions[0]}"
    archive_path = os.path.join(ARCHIVE_DIR, f"{date}-current-history.md")
    rel_archive = os.path.relpath(archive_path, os.path.dirname(current)).replace(os.sep, "/")

    print(f"  archiving {len(to_archive)} comment(s) [{label}] -> {rel_archive}")
    if dry_run:
        print("  (dry-run: no files written)")
        return len(to_archive)

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    header = (
        f"# CURRENT.md — archived history ({date})\n\n"
        "> Prior-live-state comments swept out of `agent_handoff/CURRENT.md` to keep the live\n"
        "> file lean ([[archive-currentmd-history-weekly]]). Verbatim; full history also in git log.\n"
    )
    section = f"\n## Prior live-state comments ({label}) — archived {date}\n\n{block}\n"
    mode = "a" if os.path.exists(archive_path) else "w"
    with open(archive_path, mode, encoding="utf-8", newline="\n") as f:
        if mode == "w":
            f.write(header)
        f.write(section)

    pointer = (
        f"<!-- prior live-state ({label}) archived {date} → `{rel_archive}` "
        "(full text also in git log). -->"
    )
    text = text[:start] + pointer + text[end:]
    with open(current, "w", encoding="utf-8", newline=eol) as f:
        f.write(text)
    print(f"  done. CURRENT.md now {eol!r}-terminated, {len(matches) - len(to_archive)} comment(s) kept inline.")
    return len(to_archive)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=DEFAULT_CURRENT, help="path to CURRENT.md")
    ap.add_argument("--keep", type=int, default=2, help="newest prior-live-state comments to keep inline (default 2)")
    ap.add_argument("--date", default=None, help="archive date YYYY-MM-DD (default: today, machine clock)")
    ap.add_argument("--dry-run", action="store_true", help="preview only; write nothing")
    args = ap.parse_args()
    date = args.date or datetime.date.today().isoformat()
    prune(args.file, args.keep, date, args.dry_run)


if __name__ == "__main__":
    main()
