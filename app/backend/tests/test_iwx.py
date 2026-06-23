"""engine ingest of the native iWorx/LabScribe ``.iwxdata`` ERG format (skills._iwx).

Decode is verified deterministically against a SYNTHETIC .iwxdata ZIP built to the documented
binary format (no proprietary file needed → CI-safe). An opt-in test runs against a real staged
file when present. The headline: a dropped .iwxdata is recognized as ERG by FORMAT (certain) and
runs end-to-end through the path-based erg_traces skill via the materialized-CSV bridge.
"""

import os
import struct
import zipfile

import pytest

from engine import ingest, profile_data, plan_cleaning
from skills import _iwx


def _make_iwxdata(path, group_uv=(20, 50, 100, 200, 150, 120, 110)):
    """Write a minimal valid 7-intensity scotopic .iwxdata: 7 blocks, one sweep each, with a flat
    baseline (first 50 samples = 0 mV) then a constant plateau = group_uv[gi]/UV_PER_RAW mV, so the
    decoded+baseline-corrected trace reads group_uv[gi] µV after the pre-stim window."""
    header = b"\x00" * _iwx.HEADER_BYTES
    with zipfile.ZipFile(path, "w") as zf:
        for gi in range(7):
            mv = group_uv[gi] / _iwx.UV_PER_RAW
            samples = bytearray(header)
            for i in range(_iwx.NUM_CH_POINTS):
                v = 0.0 if i < _iwx._PRESTIM_SAMPLES else mv
                samples += struct.pack(_iwx.DOUBLE_FMT, v) + b"\x00\x00"
            zf.writestr(f"blk{gi}/CH000.dat", bytes(samples))
            block_id = ((gi + 1) << 16) | 1            # intensity index gi+1, sweep 1
            zf.writestr(f"blk{gi}/blk_setting.txt", f"SWEEP_INFO 1 {gi + 1}.0 {block_id}\n")


def test_decode_dat_roundtrip():
    blob = b"\x00" * _iwx.HEADER_BYTES + struct.pack(_iwx.DOUBLE_FMT, 1.5) + b"\x00\x00"
    assert _iwx.decode_dat(blob) == pytest.approx([150.0])  # 1.5 mV × 100 = 150 µV


def test_load_eye_groups_and_filename(tmp_path):
    p = tmp_path / "C57Bl6 #677_LE Scotopic Green.iwxdata"
    _make_iwxdata(str(p))
    eye = _iwx.load_eye(str(p))
    assert len(eye.groups) == 7
    assert eye.sample_id == "677_LE" and eye.condition == "C57" and eye.eye == "LE"
    # plateau (post-baseline) of each group matches the encoded µV
    assert eye.groups[2][1000] == pytest.approx(100.0, abs=1e-6)
    assert eye.groups[3][1000] == pytest.approx(200.0, abs=1e-6)


def test_waveforms_long_shape_and_columns(tmp_path):
    p = tmp_path / "Rd10 #289_RE Scotopic Green.iwxdata"
    _make_iwxdata(str(p))
    df = _iwx.read_iwxdata(str(p))
    assert set(["sample_id", "condition", "condition_order", "intensity_group",
                "intensity_log_cd_s_m2", "time_ms", "voltage_uv", "role"]).issubset(df.columns)
    assert len(df) == 7 * _iwx.NUM_CH_POINTS
    assert df["condition"].iloc[0] == "Rd10"
    assert sorted(df["intensity_group"].unique()) == [f"Group{i}" for i in range(1, 8)]


def test_unparseable_filename_falls_back(tmp_path):
    p = tmp_path / "mystery_export.iwxdata"
    _make_iwxdata(str(p))
    eye = _iwx.load_eye(str(p))
    assert eye.condition == "ERG" and eye.sample_id == "mystery_export"  # honest fallback, no crash


def test_ingest_iwxdata_is_erg_certain_and_materializes(tmp_path):
    p = tmp_path / "C57Bl6 #677_LE Scotopic Green.iwxdata"
    _make_iwxdata(str(p))
    b = ingest(str(p))
    assert b.kind == "generic_table"            # a tidy measurements table, honestly
    prof = profile_data(b)
    assert prof.code == "erg" and prof.confidence == "certain"   # L1 FORMAT layer — certain
    assert ".iwxdata" in prof.reason or "format" in prof.reason.lower()
    assert plan_cleaning(b, profile=prof).applies is False       # used as-is, no gene cleaning
    # the runner handle is a materialized CSV (so the path-based skill reads the decoded waveforms),
    # while provenance still points at the original .iwxdata
    assert b.path.endswith(".csv") and b.path != str(p)
    assert b.source.filename.endswith(".iwxdata")


def test_non_scotopic_protocol_errors_honestly(tmp_path):
    """A file that doesn't yield 7 intensity groups raises a clear ValueError (e.g. a photopic
    export) — never a silent wrong decode."""
    p = tmp_path / "C57Bl6 #677_LE Photopic UV.iwxdata"
    header = b"\x00" * _iwx.HEADER_BYTES
    with zipfile.ZipFile(str(p), "w") as zf:
        for gi in range(3):  # only 3 intensities → not the 7-intensity scotopic protocol
            zf.writestr(f"blk{gi}/CH000.dat", header + (struct.pack(_iwx.DOUBLE_FMT, 0.0) + b"\x00\x00") * 100)
            zf.writestr(f"blk{gi}/blk_setting.txt", f"SWEEP_INFO 1 {gi + 1}.0 {((gi + 1) << 16) | 1}\n")
    with pytest.raises(ValueError, match="expected 7"):
        _iwx.load_eye(str(p))


# --- opt-in: run against a real staged .iwxdata when present (owner machine / CMRI share) -----
_REAL = "D:/selom/graphify-out/scratch/iwx/C57Bl6 #677_LE Scotopic Green.iwxdata"


@pytest.mark.skipif(not os.path.exists(_REAL), reason="no real .iwxdata staged")
def test_real_iwxdata_runs_through_erg_traces():
    from skills.contract import run_bundle_with_table

    b = ingest(_REAL)
    fig, tbl = run_bundle_with_table("erg_traces", b, {})
    assert fig["layout"]["title"]["text"] == "Representative scotopic ERG"
    assert len(fig["data"]) == 7 and tbl and len(tbl["rows"]) == 7
