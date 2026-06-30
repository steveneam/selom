"""B4 reproducibility bundle — provenance unit tests + the /run bundle contract.

The stub engine is forced so this runs with zero heavy deps, like the golden tests.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from companions import provenance
from main import app
from skills.contract import load_skill

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_sha256_file_matches_hashlib(tmp_path):
    blob = b"some bytes\x00\x01pretending to be an h5ad"
    f = tmp_path / "matrix.h5ad"
    f.write_bytes(blob)
    assert provenance.sha256_file(str(f)) == hashlib.sha256(blob).hexdigest()


def test_environment_snapshot_shape():
    env = provenance.environment_snapshot()
    assert env["python"] and env["platform"]
    assert env["engine_policy"] == "stub"
    assert isinstance(env["packages"], dict)


def test_build_records_typed_params_and_input(tmp_path):
    blob = b"x" * 128
    f = tmp_path / "demo.h5ad"
    f.write_bytes(blob)
    spec = load_skill("cluster")
    # Raw query-style param (a string) must land in the bundle coerced to its type.
    bundle = provenance.build(spec, str(f), "demo.h5ad", {"resolution": "1.5"})

    assert bundle["skill"]["id"] == "cluster"
    assert bundle["skill"]["version"] == spec.version
    assert bundle["skill"]["title"] == spec.title
    assert bundle["skill"]["engine"] == "python"
    # C5: the figure is self-describing — it carries the immutable param_spec for its
    # skill_version, verbatim, so the FE can render the Inputs with no describe round-trip.
    assert bundle["skill"]["param_spec"] == spec.param_spec
    assert "resolution" in bundle["skill"]["param_spec"]  # the knob we tuned is present
    assert bundle["params"]["resolution"] == 1.5  # coerced float, not "1.5"
    assert bundle["params"]["n_pcs"] == 50  # default filled in
    assert bundle["input"]["filename"] == "demo.h5ad"
    assert bundle["input"]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert bundle["input"]["n_bytes"] == 128


def test_stamp_ai_actions_discards_forged_attribution():
    """The chokepoint (NEXT#1) keeps ONLY the descriptive delta and re-derives every attribution
    field server-side — a forged actor/model/approved_by/approved_at cannot survive."""
    forged = [
        {
            "action_id": "a1",
            "type": "set_param",
            "target": "resolution",
            "prompt": "tighten",
            # all forged — must be overwritten:
            "actor": "human",
            "model": "evil-model",
            "approved_by": "attacker",
            "approved_at": "1999-01-01T00:00:00Z",
            "extra_forged_key": "should be dropped",
        }
    ]
    out = provenance.stamp_ai_actions(
        forged, model="gw-model", approved_by="tenant-7", approved_at="2026-06-30T10:00:00+00:00"
    )
    assert len(out) == 1
    rec = out[0]
    # Descriptive fields pass through.
    assert rec["action_id"] == "a1"
    assert rec["type"] == "set_param"
    assert rec["target"] == "resolution"
    assert rec["prompt"] == "tighten"
    # Attribution is the injected server values, never the forged ones.
    assert rec["actor"] == "ai"
    assert rec["model"] == "gw-model"
    assert rec["approved_by"] == "tenant-7"
    assert rec["approved_at"] == "2026-06-30T10:00:00+00:00"
    # No extra/forged keys leak into the immutable record.
    assert set(rec) == {
        "action_id", "actor", "type", "target", "prompt", "model", "approved_by", "approved_at",
    }


def test_stamp_ai_actions_tolerates_missing_descriptive_fields():
    """A sparse delta (only type+target, the validated minimum) stamps clean with empty descriptives."""
    out = provenance.stamp_ai_actions(
        [{"type": "set_param", "target": "x"}],
        model="m", approved_by="u", approved_at="t",
    )
    assert out[0]["action_id"] == "" and out[0]["prompt"] == ""
    assert out[0]["actor"] == "ai" and out[0]["model"] == "m"


def test_run_endpoint_returns_figure_provenance_methods():
    res = client.post(
        "/skills/cluster/run?resolution=2.0",
        files={"matrix": ("demo.h5ad", b"dummy", "application/octet-stream")},
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"figure", "provenance", "methods"}
    assert body["figure"]["data"]
    assert body["provenance"]["params"]["resolution"] == 2.0
    assert body["provenance"]["input"]["sha256"]
    # C5: the param_spec rides along on every run so the persisted figure is self-describing.
    assert body["provenance"]["skill"]["param_spec"]
    assert "resolution" in body["provenance"]["skill"]["param_spec"]
    assert "resolution 2.0" in body["methods"]["text"]
