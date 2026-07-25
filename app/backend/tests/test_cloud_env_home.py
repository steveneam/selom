"""ONE home per cloud setting — the ratchet on the trap L2-02 walked into.

**The failure this exists to stop.** The live Nango broker URL and secret key were staged in
``app/backend/.env`` and everything downstream *looked* right: ``deploy/nango/preflight.sh`` read
that file and passed all five checks against ``https://nango.swordfish.cfd``. But
``app/backend/config.py`` loads ``<repo root>/.env`` — a different file — so the running server never
saw any of it and ``settings.nango_base_url`` silently fell back to its default,
``http://localhost:3003``: the DEAD local dev instance, which shares nothing with the live one. A
green preflight and a server talking to a corpse, at the same time.

Two files claiming to be "the env" is a two-tables-drifting bug, the same shape as the FE/BE provider
fork this lane exists to kill (A20). Documentation is the weakest rung of the ratchet ladder, so the
agreement is asserted here instead: the script and the settings class must name the SAME file.
"""

from __future__ import annotations

import re
from pathlib import Path

from config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFLIGHT = _REPO_ROOT / "deploy" / "nango" / "preflight.sh"


def _settings_env_file() -> Path:
    env_file = Settings.model_config.get("env_file")
    assert env_file, "Settings no longer declares an env_file — this guard cannot bind the two homes"
    return Path(str(env_file)).resolve()


def test_the_backend_env_file_is_the_repo_root_env():
    """Pin the home itself, so 'just move it to app/backend/.env' can't quietly happen again."""
    assert _settings_env_file() == (_REPO_ROOT / ".env").resolve()


def test_preflight_reads_the_same_env_file_the_backend_does():
    """A preflight that reads a file the server does not can pass while the server is misconfigured
    — which is precisely what happened. Bind them."""
    assert _PREFLIGHT.is_file(), f"Nango preflight missing at {_PREFLIGHT}"
    src = _PREFLIGHT.read_text(encoding="utf-8")
    match = re.search(r'^BACKEND_ENV="([^"]+)"', src, re.M)
    assert match, "BACKEND_ENV assignment not found in preflight.sh — update this guard, not the trap"

    resolved = match.group(1).replace("$REPO_ROOT", str(_REPO_ROOT)).replace(
        "${REPO_ROOT}", str(_REPO_ROOT)
    )
    assert Path(resolved).resolve() == _settings_env_file(), (
        f"preflight.sh reads {resolved!r} but the backend loads {_settings_env_file()} — the two "
        "homes have diverged, so the preflight can go green against a broker the server never uses."
    )


def test_env_example_documents_the_cloud_settings():
    """``.env.example`` is the tracked copy a fresh clone (and the merge-train lead) works from. A
    setting that only exists in someone's gitignored file is not a setting anyone else can find."""
    example = (_REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for var in (
        "SELOM_NANGO_BASE_URL",
        "SELOM_NANGO_SECRET_KEY",
        "SELOM_CLOUD_GOOGLE",
        "SELOM_CLOUD_DROPBOX",
    ):
        assert var in example, f"{var} is undocumented in .env.example"
