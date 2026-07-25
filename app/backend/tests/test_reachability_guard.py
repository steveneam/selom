"""Reachability ratchet — a backend capability a user cannot reach is not shipped.

**The failure this exists to stop.** Selom keeps building things nobody can use, and only a
token-heavy milestone review notices. Google Drive + Dropbox OAuth went fully live — real refresh
tokens, live API calls returning 200 — while the UI still refused to offer them.
``POST /data/assemble-scrna`` shipped working and has no FE surface at all. ERG oscillatory
potentials, PhNR and flicker-FFT are measured and nothing displays them. Each was re-discovered by a
review rather than caught when it happened. [[selom-shipped-not-reachable]] already named the remedy
— "add a reachability guard test" — and that guard was never built, so the lesson survived only in
memory, the weakest rung of the ratchet ladder.

**What this asserts.** Every user-facing backend route is either:

1. **reached** — its path appears at an FE call site, or
2. **waived** — listed in :data:`WAIVERS` with a real reason and a tracking ID.

A new endpoint with neither fails this test in the author's own run, at the moment it is added.

**Stale waivers fail too**, and that is the load-bearing half. A waiver that has become reachable is
an error, so a lane cannot leave its waiver behind after wiring the surface up — the waiver list can
only shrink. Without that, waivers accumulate and the guard rots into a list of excuses.

**Granularity is the PATH, not the method** — deliberately. Distinguishing ``GET /datasets`` from
``POST /datasets`` would mean inferring the verb at every call site, including raw ``fetch`` calls
that pass ``method`` in an options object, and the false-positive rate is not worth it. A referenced
path means the feature area is wired; per-verb coverage is a job for feature tests. The real debt this
guard is aimed at — a whole capability with no UI — is path-level.

**Why a source scan rather than a hand-declared map:** a declared map is another table to keep in
sync, and this whole class of bug *is* two tables drifting apart. The scan cannot go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------------- FE source set
_FE = Path(__file__).resolve().parents[2] / "frontend"

#: Directories holding real product source. `mocks/` is excluded on purpose (below).
_FE_SOURCE_DIRS = ("app", "components", "hooks", "lib")


def _fe_source_files() -> list[Path]:
    """Every real FE source file — deliberately EXCLUDING mocks and tests.

    This exclusion is the point, not an optimisation. `mocks/handlers.ts` names almost every backend
    path, so counting it would make the guard pass for a route only the MSW mock has ever called —
    exactly the "the mock proves the wire, not the product" trap. A test file naming a path proves
    even less. [[selom-mock-is-wire-only-verify-real]] · [[mock-fallback-never-fabricates-data]]
    """
    out: list[Path] = []
    for d in _FE_SOURCE_DIRS:
        root = _FE / d
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix not in (".ts", ".tsx") or not p.is_file():
                continue
            name = p.name
            if name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
                continue
            if "mock" in name.lower() or any(part == "mocks" for part in p.parts):
                continue
            out.append(p)
    return out


def _fe_source_text() -> str:
    files = _fe_source_files()
    assert files, f"no FE source files found under {_FE} — the guard cannot run; fix the path"
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)


# ------------------------------------------------------------------------------- route enumeration
#: Not user-facing: liveness/readiness probes and the generated API docs. Excluded by CATEGORY with a
#: stated reason rather than waived one-by-one, because no FE surface should ever reach them and a
#: waiver would wrongly imply someone intends to.
INFRA_PATHS = {
    "/health": "liveness probe — infrastructure, not a user surface",
    "/ready": "readiness probe — infrastructure, not a user surface",
    "/docs": "FastAPI-generated Swagger UI — developer surface",
    "/docs/oauth2-redirect": "Swagger OAuth redirect — developer surface",
    "/redoc": "FastAPI-generated ReDoc — developer surface",
    "/openapi.json": "generated OpenAPI schema — developer/tooling surface",
}

#: Routes with no FE call site and a real reason. **A waiver must name a tracking ID** so it is a
#: debt with an owner, not a shrug. Removing a waiver is part of the change that wires the surface up.
#:
#: Format: path -> (tracking-id, reason)
#: Backlog + reasoning: ``docs/reachability/backlog.md``. Every ``R-xx`` below was found BY THIS GUARD
#: on its first run, not by a review — 17 unreachable paths against a review that had surfaced 2.
WAIVERS: dict[str, tuple[str, str]] = {
    "/data/assemble-scrna": (
        "L2-05",
        "Shipped working in 11a115f with no FE surface — the example that motivated this guard. "
        "Lane 2 builds the surface.",
    ),
    # ---- R-01 lit-synthesizer: backend shipped, zero FE ------------------------------------------
    "/methods/compose": (
        "R-01",
        "lit-synthesizer is recorded as SHIPPED but has no FE call site at all — auto-methods text "
        "cannot be reached by any user. The single largest shipped-not-reachable capability found.",
    ),
    "/citations/by-doi": (
        "R-01",
        "Citation lookup by DOI shipped with the lit-synthesizer; no FE call site. Reached only by "
        "backend tests today.",
    ),
    "/citations/search": (
        "R-01",
        "Citation search shipped with the lit-synthesizer; no FE call site. Reached only by backend "
        "tests today.",
    ),
    # ---- R-02 async job pipeline: no FE consumer of job STATUS -----------------------------------
    "/jobs/{job_id}": (
        "R-02",
        "The async job API has no FE consumer: the frontend runs skills through the SYNCHRONOUS "
        "/skills/{id}/run path, so no surface ever polls a job. Directly relevant to the unparked "
        "arq+Redis job-status store (OH-01) — that store would have no reader today.",
    ),
    "/jobs/{job_id}/events": (
        "R-02",
        "Job SSE stream has no FE consumer — nothing subscribes, so long-running work cannot report "
        "progress to a user. Same root cause as /jobs/{job_id}.",
    ),
    "/jobs/{job_id}/result": (
        "R-02",
        "Job result retrieval has no FE consumer, because nothing submits async jobs from the UI.",
    ),
    "/skills/{skill_id}/jobs": (
        "R-02",
        "Async skill submission is unused — the FE calls the synchronous /run instead, so every "
        "long skill blocks a request. The async path exists and is simply not wired.",
    ),
    "/skills/{skill_id}/jobs-dataset": (
        "R-02",
        "Async dataset-backed skill submission is unused for the same reason as /skills/{id}/jobs.",
    ),
    # ---- R-03 paper-level outputs ----------------------------------------------------------------
    "/papers/{slug}/legends": (
        "R-03",
        "Generated figure legends for a paper have no FE surface, so the legend output cannot be "
        "read or exported by a user.",
    ),
    "/papers/{slug}/methods": (
        "R-03",
        "Paper-level methods text has no FE surface — the same gap as R-01 seen from the paper side.",
    ),
    "/papers/{slug}/scorecard": (
        "R-03",
        "The Reproducibility Score is computed and served but no FE surface reads this route, so the "
        "score cannot be shown for a paper.",
    ),
    # ---- R-04 artifacts -------------------------------------------------------------------------
    "/artifacts/{artifact_id}": (
        "R-04",
        "Artifact retrieval has no FE call site; artifacts are produced by runs and cannot be "
        "fetched back by id from the UI.",
    ),
    "/artifacts/{artifact_id}/table": (
        "R-04",
        "Tabular view of an artifact has no FE call site — the table an artifact carries cannot be "
        "opened by a user.",
    ),
    # ---- R-05..R-07 singletons ------------------------------------------------------------------
    "/papers/metadata/by-doi": (
        "R-05",
        "DOI metadata enrichment has no FE call site, so the auto-rename/XMP enrich path is not "
        "user-reachable even though it is wired into Skill Match server-side.",
    ),
    "/reproduction-runs/{run_id}/events": (
        "R-06",
        "The reproduction SSE progress stream has no FE consumer, so a reproduction run reports no "
        "live progress. The non-streaming /reproduction-runs/{run_id} IS reached, so this is a "
        "progress-visibility gap rather than a dead feature.",
    ),
    "/workspace": (
        "R-07",
        "The workspace ROOT collection has no FE call site — the FE fetches the two child "
        "collections (/workspace/gene-sets, /workspace/papers) directly. Likely genuinely "
        "redundant: resolve by deleting the route or by using it, not by leaving it ambiguous.",
    ),
}


def _route_pattern(path: str) -> re.Pattern[str]:
    """Compile a route path into a matcher for FE call sites.

    ``{param}`` (and ``{key:path}``) become "one path segment of anything a call site could put
    there" — a template hole like ``${encodeURIComponent(id)}`` must match, so the class excludes
    only ``/`` and string delimiters.

    The trailing lookahead is what stops ``/skills/{id}/run`` from also matching
    ``/skills/${id}/run-dataset``: the next character must not continue the path.
    """
    parts = [re.escape(p) for p in re.split(r"\{[^}]*\}", path)]
    body = r"[^/\"'`?\s]+".join(parts)
    return re.compile(body + r"(?![A-Za-z0-9_/-])")


def _user_facing_paths() -> list[str]:
    from main import app

    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        if not (methods & {"GET", "POST", "PUT", "PATCH", "DELETE"}):
            continue
        if path in INFRA_PATHS:
            continue
        paths.add(path)
    return sorted(paths)


# ------------------------------------------------------------------------------------- the ratchet
def test_every_user_facing_route_is_reachable_or_waived():
    """The ratchet. A route with no FE call site and no waiver fails here."""
    src = _fe_source_text()
    unreachable = [p for p in _user_facing_paths() if not _route_pattern(p).search(src)]
    undeclared = sorted(set(unreachable) - set(WAIVERS))

    assert not undeclared, (
        "These backend routes have NO frontend call site and NO waiver — they are shipped but "
        "unreachable:\n  "
        + "\n  ".join(undeclared)
        + "\n\nBuild the user-facing surface, or add a WAIVERS entry in this file with a tracking ID "
        "and a real reason. A capability a user cannot reach is not shipped."
    )


def test_no_stale_waivers():
    """The half that makes it a ratchet rather than a list of excuses.

    A waiver whose route is now reachable must be deleted, so the list can only shrink and a lane
    cannot bank its waiver after doing the work.
    """
    src = _fe_source_text()
    live = {p for p in _user_facing_paths() if _route_pattern(p).search(src)}
    stale = sorted(set(WAIVERS) & live)

    assert not stale, (
        "These routes are now REACHABLE from the frontend, so their waivers are stale and must be "
        "removed from WAIVERS:\n  " + "\n  ".join(stale)
    )


def test_waivers_reference_only_real_routes():
    """A waiver for a route that no longer exists is dead weight that hides the real list."""
    known = set(_user_facing_paths())
    orphans = sorted(set(WAIVERS) - known)
    # A waiver may legitimately pre-declare a route a lane is about to add (the frozen
    # /cloud/providers contract is exactly this), so those are allowed but must be named here.
    allowed_pending = {"/cloud/providers"}
    assert not (set(orphans) - allowed_pending), (
        "WAIVERS names routes that do not exist and are not pending implementation: "
        f"{sorted(set(orphans) - allowed_pending)}. Delete them."
    )


@pytest.mark.parametrize("path", sorted(WAIVERS))
def test_every_waiver_states_an_id_and_a_reason(path):
    """A waiver without an owner is a shrug. Enforce that it carries both."""
    tracking_id, reason = WAIVERS[path]
    assert tracking_id.strip(), f"{path}: waiver has no tracking ID"
    assert len(reason.strip()) > 40, f"{path}: waiver reason is too thin to be a real reason"


def test_infra_paths_each_state_why_they_are_exempt():
    """Category exemptions must be justified too, or the category becomes a loophole."""
    for path, reason in INFRA_PATHS.items():
        assert len(reason.strip()) > 20, f"{path}: infra exemption needs a stated reason"
