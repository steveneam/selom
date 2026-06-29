"""Per-paper captured reproduction ledgers (repo-structure plan §3A).

Each module builds + drives one paper's ledger via ``build_ledger`` / ``drive_captured``
(rpgrip1 · jev · hani are wired into ``papers_api._LEDGER_MODULES``; dorgau is a standalone
ledger + dev CLI). Run a paper's dev CLI with ``python -m reproduction.papers.<slug>``.
"""
