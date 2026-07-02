"""WS2.6 — the unified run-path error taxonomy (``routers/_errors.py`` ``RunError``).

Three inconsistent styles used to reach the FE from a run — the engine degrading to ``None``, the
router raising an ad-hoc ``HTTPException`` (a structured dict OR a bare string), and a skill runner
raising ``ValueError`` (a bare-string 400). This locks the unification: every run-path failure now
serializes to ONE envelope ``detail = {error, category, message, fix, **context}`` (mirroring the
QC-flag shape), and the three categories — ``bad_input`` / ``unsupported`` / ``internal`` — all map
onto that single shape. A drift guard keeps the core run body (``routers/_run.py``) on the taxonomy.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from config import settings
from main import app
from routers import _run as _run_module
from routers._errors import BAD_INPUT, CATEGORIES, INTERNAL, UNSUPPORTED, RunError, unknown_skill

client = TestClient(app)

_CSV = ("matrix.csv", b"gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\nB2M,5,8\n", "text/csv")


def _assert_envelope(detail, *, error: str, category: str):
    """Every taxonomy error carries the same four fields; `category` is one of the closed set."""
    assert isinstance(detail, dict), f"detail must be the structured envelope, got {type(detail)}"
    for key in ("error", "category", "message", "fix"):
        assert key in detail, f"envelope missing {key!r}: {detail}"
    assert detail["error"] == error
    assert detail["category"] == category
    assert detail["category"] in CATEGORIES
    assert isinstance(detail["message"], str) and detail["message"]
    assert isinstance(detail["fix"], str)


# --- unit: the RunError model + constructors --------------------------------------------------

def test_constructors_pair_category_to_default_status():
    assert RunError.bad_input("c", "m").status_code == 400
    assert RunError.unsupported("c", "m").status_code == 404
    assert RunError.internal("c", "m").status_code == 500
    # A gate / conflict / timeout overrides the default while keeping its category.
    assert RunError.bad_input("c", "m", status_code=422).category == BAD_INPUT
    assert RunError.unsupported("c", "m", status_code=409).category == UNSUPPORTED
    assert RunError.internal("c", "m", status_code=504).category == INTERNAL


def test_context_rides_along_verbatim_next_to_the_four_fields():
    err = RunError.bad_input("param_out_of_range", "bad", fix="fix it", errors=["x must be <= 5"])
    d = err.detail
    _assert_envelope(d, error="param_out_of_range", category=BAD_INPUT)
    assert d["fix"] == "fix it"
    assert d["errors"] == ["x must be <= 5"]          # structured context preserved, not swallowed


def test_shared_unknown_skill_builder_is_unsupported_404():
    err = unknown_skill("nope")
    assert err.status_code == 404
    _assert_envelope(err.detail, error="unknown_skill", category=UNSUPPORTED)
    assert "nope" in err.detail["message"]


# --- functional: all three categories surface the SAME envelope through the API ---------------

def test_bad_input_param_out_of_range(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    r = client.post("/skills/volcano/run?fc_threshold=100", files={"matrix": _CSV})
    assert r.status_code == 400
    detail = r.json()["detail"]
    _assert_envelope(detail, error="param_out_of_range", category=BAD_INPUT)
    assert any("fc_threshold" in m for m in detail["errors"])   # the pre-taxonomy `errors` context


def test_unsupported_unknown_skill_is_uniform_404_on_the_multipart_run_path(monkeypatch):
    # /skills/{id}/run had NO upfront guard and 500'd on an unknown skill while /jobs + /run-dataset
    # 404'd — WS2.6 maps the load_skill FileNotFoundError at the shared chokepoint so it's uniform.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    r = client.post("/skills/does_not_exist/run", files={"matrix": _CSV})
    assert r.status_code == 404
    _assert_envelope(r.json()["detail"], error="unknown_skill", category=UNSUPPORTED)


def test_internal_skill_timeout(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    monkeypatch.setattr(settings, "skill_timeout_s", 1)

    def hang(*args, **kwargs):
        time.sleep(3)
        return {"data": [], "layout": {}}, None

    monkeypatch.setattr(_run_module, "run_bundle_with_table", hang)
    monkeypatch.setattr(_run_module, "run_skill_with_table", hang)
    r = client.post("/skills/volcano/run?override=true", files={"matrix": _CSV})
    assert r.status_code == 504
    _assert_envelope(r.json()["detail"], error="skill_timeout", category=INTERNAL)


def test_bad_input_skill_run_failure_carries_the_real_cause(monkeypatch):
    # The skill-runner ValueError (a DATA problem) — the style that used to be a bare-string 400 that
    # fell through the FE's generic "try again" frame. Now the same bad_input envelope as the gates.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    r = client.post(
        "/skills/erg_intensity_response/run",
        files={"matrix": ("plain.csv", b"a,b,c\n1,2,3\n4,5,6\n", "text/csv")},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    _assert_envelope(detail, error="skill_run_failed", category=BAD_INPUT)
    assert "required columns" in detail["message"]      # the real cause, surfaced verbatim
    assert detail["fix"]                                 # an actionable next step, not just the cause


# --- drift guard: the core run body stays on the taxonomy -------------------------------------

def test_run_body_raises_only_through_the_taxonomy():
    # routers/_run.py is _execute_skill_run — the shared run body. Every failure it surfaces must go
    # through RunError (the taxonomy), never a bare HTTPException, so a new gate can't reintroduce an
    # ad-hoc shape. (data.py keeps 2 artifact-GET 404s — a separate lineage-retrieval feature.)
    src = (Path(__file__).resolve().parent.parent / "routers" / "_run.py").read_text(encoding="utf-8")
    assert "HTTPException(" not in src, "routers/_run.py must raise RunError, not a bare HTTPException"
