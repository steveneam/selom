"""Tests for the Diagnosys Espion/Celeris parser (``skills._celeris``).

CI-safe: the structural logic is tested via unit tests + a synthetic reduced-CSV fixture (no
real-data dependency). The full multi-table ``.TXT`` (Contents/Stimulus tables, all three modes)
is validated by opt-in tests against the staged samples, skipped when those files are absent.
"""
from __future__ import annotations

import csv

import pytest

from config import datasets_dir
from skills import _celeris

# Staged real samples (opt-in; see $SELOM_DATASETS_DIR/diagnosys-erg/README.md).
_DATASETS = datasets_dir()
_FULL_TXT = (_DATASETS / "diagnosys-erg/full-txt-exp8/453_AAV_C1 - Long RK-PROM1-3’UTR-BPolyA_10+E9.TXT") if _DATASETS else None
_REDUCED_CSV = (_DATASETS / "diagnosys-erg/reduced-csv/dr1.CSV") if _DATASETS else None


# ---- pure-helper unit tests ------------------------------------------------------------
def test_sniff_delimiter():
    assert _celeris.sniff_delimiter("a\tb\tc") == "\t"
    assert _celeris.sniff_delimiter("a,b,c") == ","


@pytest.mark.parametrize("desc,st,adapt,inten,hz", [
    ("DA 0.01 cd.s/m²", "scotopic_flash", "dark", 0.01, None),
    ("DA 10 cd.s/m²", "scotopic_flash", "dark", 10.0, None),
    ("LA Single 3.0 Flash", "photopic_flash", "light", 3.0, None),
    ("LA 30 Hz Flicker", "flicker", "light", None, 30.0),
    ("LA 10 Hz Flicker", "flicker", "light", None, 10.0),
])
def test_classify_stimulus(desc, st, adapt, inten, hz):
    c = _celeris.classify_stimulus(desc)
    assert c["stimulus_type"] == st
    assert c["adaptation"] == adapt
    assert c["intensity_cd_s_m2"] == inten
    assert c["flicker_hz"] == hz


def test_canon_marker_case_folds_b():
    # The B (scotopic) / b (photopic) split is a template convention, not a different feature.
    assert _celeris._canon_marker("B") == "b"
    assert _celeris._canon_marker("b") == "b"
    assert _celeris._canon_marker("a") == "a"
    assert _celeris._canon_marker("c-wave") == "c-wave"
    assert _celeris._canon_marker("N1") == "n1"


def test_repair_split_rows_rejoins_a_split_field():
    # A logical record split across two physical lines (the Mac CR artefact): "3/7/22" ⏎ "024,…".
    rows = [["a", "b", "c", "d", "e"],       # width 5 (the expected record width)
            ["0", "M", "3/7/22"],            # short — split inside the date field
            ["024", "1", "RE"]]              # continuation: last cell of prev + first cell here reunite
    fixed = _celeris._repair_split_rows(rows, expected=5)
    # The two physical rows merge into one record of the expected width (3 + 3 − 1 = 5).
    assert len(fixed) == 2
    assert fixed[0] == ["a", "b", "c", "d", "e"]
    assert fixed[1] == ["0", "M", "3/7/22024", "1", "RE"]


def test_contents_bounds():
    rows = [
        ["Contents Table"],
        ["Table", "Left", "Top", "Right", "Bottom"],
        ["Spreadsheet", "1", "1", "50", "100"],
        ["Marker Table", "10", "4", "22", "81"],
        ["Data Table", "38", "4", "84", "100"],
        ["", "", "", "", ""],
    ]
    b = _celeris._contents_bounds(rows)
    assert b["Marker Table"].left == 10 and b["Marker Table"].bottom == 81
    assert b["Data Table"].right == 84
    assert "Spreadsheet" in b


def test_data_blocks():
    headers = ["Step", "Column", "Chan", "Result", "Column", "Trials",
               "Step 1", "Chan 1", "Chan 2", "Chan 3", "Chan 4", "Step 2", "Chan 1", "Chan 2"]
    blocks = _celeris._data_blocks(headers)
    # "Step" alone (no Chan after) is the index column, not a block; "Step 1"/"Step 2" are blocks.
    assert [b[0] for b in blocks] == [1, 2]
    assert len(blocks[0][2]) == 4  # Step 1 has 4 channels
    assert len(blocks[1][2]) == 2  # Step 2 has 2 channels


def test_infer_stimulus():
    assert _celeris._infer_stimulus({"a", "b"})["stimulus_type"] == "scotopic_flash"
    assert _celeris._infer_stimulus({"n1", "p1"})["stimulus_type"] == "flicker"


# ---- synthetic reduced-CSV integration (banner-scan path, CI-safe) ---------------------
def _build_reduced_csv(path: str):
    """A minimal reduced (comma) export: Marker Table + Data Table only, no Contents/Stimulus —
    exercises the banner-scan locator, unit normalization, case-fold, channel→eye, baseline."""
    W = 25
    def blank():
        return [""] * W

    rows = [blank()]
    rows[0][0], rows[0][13] = "Marker Table", "Data Table"
    mh = ["Group", "Name", "Cage #", "Age", "Date", "S", "C", "R", "Eye", "Name", "uV", "ms"]
    dh = ["Step", "Column", "Chan", "Result", "Column", "Trials",
          "Step 1", "Chan 1", "Chan 2", "Step 2", "Chan 1", "Chan 2"]
    r1 = blank()
    for i, h in enumerate(mh):
        r1[i] = h
    for i, h in enumerate(dh):
        r1[13 + i] = h
    rows.append(r1)
    r2 = blank()
    for c in (19, 22):
        r2[c] = "Time (ms)"
    for c in (20, 21, 23, 24):
        r2[c] = "Result (nV)"
    rows.append(r2)

    markers = [
        ("1", "1", "RE", "a", "-20", "24"), ("1", "1", "RE", "B", "300", "60"),
        ("1", "2", "LE", "a", "-18", "23"), ("1", "2", "LE", "B", "280", "62"),
        ("2", "1", "RE", "a", "-40", "21"), ("2", "1", "RE", "B", "320", "56"),
        ("2", "2", "LE", "a", "-35", "21"), ("2", "2", "LE", "B", "290", "57"),
    ]
    times = ["-2", "-1", "0", "1", "2"]
    s1c1 = ["0", "0", "100000", "300000", "200000"]   # nV → /1000 µV
    s1c2 = ["0", "0", "90000", "280000", "180000"]
    s2c1 = ["0", "0", "110000", "320000", "210000"]
    s2c2 = ["0", "0", "95000", "290000", "185000"]
    for i in range(max(len(markers), len(times))):
        row = blank()
        if i < len(markers):
            s, c, eye, nm, uv, ms = markers[i]
            for j, v in enumerate(["0", "M1", "", "30d", "1/1/2024", s, c, "1", eye, nm, uv, ms]):
                row[j] = v
        if i < len(times):
            row[13] = "1"
            row[19], row[20], row[21] = times[i], s1c1[i], s1c2[i]
            row[22], row[23], row[24] = times[i], s2c1[i], s2c2[i]
        rows.append(row)

    with open(path, "w", newline="", encoding="latin-1") as fh:
        csv.writer(fh).writerows(rows)


def test_reduced_csv_end_to_end(tmp_path):
    path = str(tmp_path / "synthetic.CSV")
    _build_reduced_csv(path)

    assert _celeris.is_diagnosys_export(path)
    exp = _celeris.load_export(path)

    # No Stimulus Table → scotopic inferred from the {a,b} marker vocabulary.
    assert set(exp.stimulus) == {1, 2}
    assert all(exp.stimulus[s]["stimulus_type"] == "scotopic_flash" for s in (1, 2))

    # Channel → eye from the Marker Table C column.
    assert exp.channel_eye == {1: "RE", 2: "LE"}

    # Markers: 8 rows; the uppercase B case-folds to b.
    mk = _celeris.markers_long(exp)
    assert len(mk) == 8
    assert {m["marker_name"] for m in mk} == {"a", "b"}

    # Metrics a/b view: step1 RE a=-20 b=300 (B folded to the b column).
    met = _celeris.metrics_long(exp)
    re1 = next(r for r in met if r["eye"] == "RE" and r["step"] == 1)
    assert re1["a_wave_uv"] == -20.0 and re1["b_wave_uv"] == 300.0

    # Waveforms: nV→µV (300000 nV → 300 µV at the peak), baseline ≈ 0 (pre-stim t<0 mean), RE/LE only.
    df = _celeris.read_celeris(path)
    assert sorted(df["eye"].unique()) == ["LE", "RE"]
    assert sorted(df["channel"].unique()) == [1, 2]
    re_s1 = df[(df["eye"] == "RE") & (df["step"] == 1)]
    assert abs(re_s1["voltage_uv"].max() - 300.0) < 1e-6

    # Group ranking within a mode: two scotopic steps → Group1, Group2.
    assert set(df["intensity_group"].unique()) == {"Group1", "Group2"}


def test_ingest_routes_diagnosys_to_erg(tmp_path):
    """engine.ingest recognizes a Diagnosys .CSV (by magic header, before the generic csv loader),
    materializes it to the canonical waveforms, and engine.cleaning profiles it as ERG-certain by
    FORMAT (R-ingest-1) — not the weaker content guess, and never a proteomics false-positive."""
    from engine.cleaning import ERG, profile_data
    from engine.ingest import ingest
    from engine.models import GENERIC_TABLE

    path = str(tmp_path / "synthetic.CSV")
    _build_reduced_csv(path)
    bundle = ingest(path)
    cols = [str(c).lower() for c in bundle.payload.columns]
    assert "voltage_uv" in cols and "time_ms" in cols   # materialized waveforms, not the raw 2-table mess
    assert bundle.meta.get("erg_format") == "diagnosys_erg"  # the format signal the loader recorded
    # ERG isn't an omics Kind → the neutral GENERIC_TABLE (drives the FE to a neutral questionnaire,
    # never proteomics), with the real ERG type carried by the profile below.
    assert bundle.kind == GENERIC_TABLE
    prof = profile_data(bundle)
    assert prof.code == ERG and prof.confidence == "certain" and prof.reason.startswith("recognized")
    # No spurious proteomics runner-up — the candidate list is ERG + the neutral table only.
    assert "proteomics" not in {c.code for c in prof.candidates}


def test_not_a_diagnosys_export(tmp_path):
    path = str(tmp_path / "plain.csv")
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("gene,logFC,padj\nFOO,1.2,0.01\n")
    assert not _celeris.is_diagnosys_export(path)
    with pytest.raises(ValueError):
        _celeris.load_export(path)


# ---- opt-in real-sample validation -----------------------------------------------------
@pytest.mark.skipif(_FULL_TXT is None or not _FULL_TXT.exists(), reason="staged full-TXT sample absent")
def test_real_full_txt_all_three_modes():
    exp = _celeris.load_export(_FULL_TXT)
    assert "Dark & Light Adapted" in exp.meta.get("Protocol", "")
    kinds = {s: exp.stimulus[s]["stimulus_type"] for s in exp.stimulus}
    assert sum(v == "scotopic_flash" for v in kinds.values()) == 5
    assert sum(v == "photopic_flash" for v in kinds.values()) == 2
    assert sum(v == "flicker" for v in kinds.values()) == 2
    # Scotopic ranked dimmest→brightest: Group1 = lowest log intensity.
    df = _celeris.read_celeris(_FULL_TXT)
    sc = df[df["stimulus_type"] == "scotopic_flash"]
    g1 = sc[sc["intensity_group"] == "Group1"]["intensity_log_cd_s_m2"].iloc[0]
    g5 = sc[sc["intensity_group"] == "Group5"]["intensity_log_cd_s_m2"].iloc[0]
    assert g1 < g5
    # Device a/b markers present for scotopic steps.
    met = [m for m in _celeris.metrics_long(exp) if m["stimulus_type"] == "scotopic_flash"]
    assert all(m["a_wave_uv"] is not None and m["b_wave_uv"] is not None for m in met)
    # Trace feed is one channel per eye (OP/secondary channels excluded).
    assert sorted(df["eye"].unique()) == ["LE", "RE"]
    assert sorted(df["channel"].unique()) == [1, 2]


@pytest.mark.skipif(_REDUCED_CSV is None or not _REDUCED_CSV.exists(), reason="staged reduced-CSV sample absent")
def test_real_reduced_csv():
    exp = _celeris.load_export(_REDUCED_CSV)
    met = _celeris.metrics_long(exp)
    # 7 scotopic steps × 2 eyes, device a/b present; b folded from B.
    assert len({(m["eye"], m["step"]) for m in met}) == 14
    assert all(m["stimulus_type"] == "scotopic_flash" for m in met)
