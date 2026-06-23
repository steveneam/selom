"""Pure-stdlib reader for **Diagnosys Espion / Celeris** ERG exports → Selom's canonical ERG tables.

A Diagnosys export is a single delimited file holding several *side-by-side* tables (each table
owns a column range; tables have different row counts, so a short table's columns are blank in the
later rows). Two export shapes are supported:

* **Full multi-table ``.TXT``** (TAB-delimited) — the richest, the primary target. Row 1 names the
  tables (``Contents Table``, ``Header Table``, ``Marker Table``, ``Summary Table``, ``Stimulus
  Table``, ``Data Table``); the **Contents Table** lists every sub-table's exact ``Left/Top/Right/
  Bottom`` spreadsheet bounds (a built-in locator). The **Stimulus Table** maps each step to a
  description + intensity (``DA 0.01 cd.s/m²`` / ``LA Single 3.0 Flash`` / ``LA 30 Hz Flicker``), so
  adaptation state, intensity and flicker frequency are *read*, not inferred.
* **Reduced ``.CSV``** (COMMA-delimited) — ``Marker Table`` + ``Data Table`` only, no Contents/
  Stimulus tables; stimulus type is then *inferred* from the marker vocabulary.

Emits the canonical tables the existing ERG skills consume (see ``docs/erg-module/spec.md`` +
``docs/diagnosys-erg/spec.md``):

* ``erg_markers_long`` — every device marker (``a``/``B``/``b``/``c-wave``/``N1``/``P1``/…), µV + ms.
* ``erg_metrics_long`` — the a/b view (``a_wave_uv``/``b_wave_uv`` + implicit times) the current
  ``erg_intensity_response`` / ``erg_bwave_bar`` read **unchanged**.
* ``erg_waveforms_long`` — tidy baseline-corrected waveforms (nV→µV) the ``erg_traces`` grid reads.

Pure stdlib on the parse path (``csv``/``re``/``math``); pandas is imported lazily only to assemble
the final frames (mirrors ``skills/_iwx.py``).
"""

from __future__ import annotations

import csv
import io
import math
import os
import re
from dataclasses import dataclass, field

# Tables that may appear, in left-to-right banner order.
_TABLE_NAMES = (
    "Contents Table", "Header Table", "Marker Table",
    "Summary Table", "Stimulus Table", "Data Table",
)
_PRESTIM_MS = 0.0  # baseline = mean of samples with time_ms < 0 (pre-flash)


# ---- low-level read --------------------------------------------------------------------
def sniff_delimiter(header_line: str) -> str:
    """TAB for the full ``.TXT`` export, comma for the reduced ``.CSV``."""
    return "\t" if "\t" in header_line else ","


def read_rows(path: str) -> tuple[list[list[str]], str]:
    """Read the export into rows of string cells. Normalizes CR/CRLF/LF, decodes latin-1 (Espion
    writes µ/² as 0xB5/0xB2). Returns ``(rows, delimiter)``."""
    with open(path, encoding="latin-1") as fh:
        text = fh.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    first = text.split("\n", 1)[0]
    delim = sniff_delimiter(first)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    return rows, delim


def is_diagnosys_export(path: str) -> bool:
    """Magic-header sniff: row 1 names both a Marker Table and a Data Table (the format signal,
    independent of the ``.csv``/``.txt`` extension). Cheap — reads only the first line."""
    try:
        with open(path, encoding="latin-1") as fh:
            first = fh.readline()
    except OSError:
        return False
    low = first.lower()
    return "marker table" in low and "data table" in low


# ---- table location --------------------------------------------------------------------
@dataclass
class _Bounds:
    """1-indexed spreadsheet bounds of a sub-table (inclusive)."""

    left: int
    top: int
    right: int
    bottom: int


def _repair_split_rows(rows: list[list[str]], expected: int) -> list[list[str]]:
    """Rejoin a logical record split across two physical lines (a stray newline inside a field —
    the Mac CR artefact seen in real exports, e.g. a date ``3/7/2024`` → ``3/7/22`` ⏎ ``024,…``).
    A short row whose last cell + the next row's first cell reunite to the expected width is merged."""
    if expected <= 0:
        return rows
    out: list[list[str]] = []
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        if 0 < len(row) < expected and i + 1 < n:
            nxt = rows[i + 1]
            merged = row[:-1] + [row[-1] + nxt[0]] + nxt[1:]
            if len(merged) == expected:
                out.append(merged)
                i += 2
                continue
        out.append(row)
        i += 1
    return out


def _contents_bounds(rows: list[list[str]]) -> dict[str, _Bounds]:
    """Parse the Contents Table (always the left-most table: columns ``Table|Left|Top|Right|
    Bottom``) → ``{table_name: _Bounds}``. Empty if there is no Contents Table (reduced CSV)."""
    # The Contents Table header row is the one whose first cells are Table/Left/Top/Right/Bottom.
    hdr_row = None
    for r, row in enumerate(rows[:6]):
        cells = [c.strip() for c in row[:5]]
        if cells[:5] == ["Table", "Left", "Top", "Right", "Bottom"]:
            hdr_row = r
            break
    if hdr_row is None:
        return {}
    bounds: dict[str, _Bounds] = {}
    for row in rows[hdr_row + 1:]:
        name = (row[0] if row else "").strip()
        if not name:
            continue
        if name not in _TABLE_NAMES and name != "Spreadsheet":
            break  # past the Contents Table
        try:
            bounds[name] = _Bounds(int(row[1]), int(row[2]), int(row[3]), int(row[4]))
        except (ValueError, IndexError):
            continue
    return bounds


def _banner_bounds(rows: list[list[str]]) -> dict[str, _Bounds]:
    """Fallback locator for the reduced CSV (no Contents Table): scan row 1 for the table banners
    → column ranges (a banner spans from its column to just before the next banner). Rows span the
    whole sheet (the caller trims blank trailing rows per table)."""
    if not rows:
        return {}
    banner = rows[0]
    starts: list[tuple[int, str]] = []
    for i, cell in enumerate(banner):
        name = cell.strip()
        if name in _TABLE_NAMES:
            starts.append((i + 1, name))  # 1-indexed
    bounds: dict[str, _Bounds] = {}
    width = max(len(r) for r in rows)
    for k, (col, name) in enumerate(starts):
        right = (starts[k + 1][0] - 1) if k + 1 < len(starts) else width
        bounds[name] = _Bounds(col, 2, right, len(rows))
    return bounds


def _slice(rows: list[list[str]], b: _Bounds) -> tuple[list[str], list[list[str]]]:
    """Return ``(headers, data_rows)`` for a sub-table given its bounds. Headers come from the
    table's header row (row 2 of the sheet); data rows are ``top..bottom`` clipped to the column
    range. Trailing all-blank rows in the range are dropped (robust to differing table lengths)."""
    lo, hi = b.left - 1, b.right
    headers = [c.strip() for c in rows[1][lo:hi]] if len(rows) > 1 else []
    data: list[list[str]] = []
    for r in range(b.top - 1, min(b.bottom, len(rows))):
        seg = rows[r][lo:hi]
        if any(c.strip() for c in seg):
            data.append(seg)
    return headers, data


# ---- stimulus classification -----------------------------------------------------------
_INTENSITY_RE = re.compile(r"(-?[\d.]+)\s*cd")
_FLASH_INTENSITY_RE = re.compile(r"([\d.]+)\s*flash", re.IGNORECASE)  # "LA Single 3.0 Flash" → 3.0
_FLICKER_RE = re.compile(r"([\d.]+)\s*hz", re.IGNORECASE)


def classify_stimulus(description: str) -> dict:
    """Read a Stimulus-Table description → stimulus metadata (the authoritative L1 signal).

    ``DA 0.01 cd.s/m²`` → scotopic flash · ``LA Single 3.0 Flash`` → photopic flash ·
    ``LA 30 Hz Flicker`` → flicker. ``DA``/``LA`` set the adaptation; ``Hz`` sets flicker_hz."""
    d = (description or "").strip()
    low = d.lower()
    adaptation = "light" if low.startswith("la") or "light" in low else (
        "dark" if low.startswith("da") or "dark" in low else "")
    flicker = _FLICKER_RE.search(d)
    if "flicker" in low or flicker:
        st = "flicker"
    elif "flash" in low or "cd" in low:
        st = "photopic_flash" if adaptation == "light" else "scotopic_flash"
    else:
        st = ""
    # Intensity (cd·s/m²): the number before "cd"; for a photopic single flash with no cd token,
    # the number before "Flash". Flicker carries a frequency (Hz), not an intensity.
    inten_v = None
    if st != "flicker":
        m = _INTENSITY_RE.search(d) or _FLASH_INTENSITY_RE.search(d)
        if m:
            inten_v = float(m.group(1))
    return {
        "description": d,
        "stimulus_type": st,
        "adaptation": adaptation,
        "intensity_cd_s_m2": inten_v,
        "flicker_hz": float(flicker.group(1)) if flicker else None,
    }


def _infer_stimulus(markers: set[str]) -> dict:
    """Fallback (reduced CSV, no Stimulus Table): infer type from the marker vocabulary.
    ``a`` present ⇒ flash; only ``N1``/``P1`` ⇒ flicker; a ``c``/``c-wave`` marker noted."""
    m = {x.lower() for x in markers}
    has_flicker = bool(m & {"n1", "p1"})
    has_flash = "a" in m
    if has_flicker and not has_flash:
        st = "flicker"
    elif has_flash:
        st = "scotopic_flash"  # adaptation unknown without the Stimulus Table
    else:
        st = ""
    return {"description": "", "stimulus_type": st, "adaptation": "",
            "intensity_cd_s_m2": None, "flicker_hz": None}


# ---- the export model ------------------------------------------------------------------
@dataclass
class CelerisExport:
    """A parsed Diagnosys export."""

    sample_id: str
    condition: str
    meta: dict = field(default_factory=dict)              # Header Table (Protocol, Version, …)
    stimulus: dict = field(default_factory=dict)          # step(int) → classify_stimulus(...)
    channel_eye: dict = field(default_factory=dict)       # channel(int) → eye (RE/LE/…)
    markers: list[dict] = field(default_factory=list)     # erg_markers_long rows
    waveforms: list[dict] = field(default_factory=list)   # erg_waveforms_long rows


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _header_index(headers: list[str], *names: str) -> int | None:
    """First column index whose (normalized) header matches any of ``names``."""
    want = {_norm(n) for n in names}
    for i, h in enumerate(headers):
        if _norm(h) in want:
            return i
    return None


def _condition_from_path(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.strip()


def _parse_header(rows, bounds) -> dict:
    if "Header Table" not in bounds:
        return {}
    headers, data = _slice(rows, bounds["Header Table"])
    pi = _header_index(headers, "Parameter")
    vi = _header_index(headers, "Value")
    if pi is None or vi is None:
        return {}
    meta = {}
    for row in data:
        if len(row) > max(pi, vi) and row[pi].strip():
            meta[row[pi].strip()] = row[vi].strip()
    return meta


def _parse_stimulus(rows, bounds) -> dict[int, dict]:
    if "Stimulus Table" not in bounds:
        return {}
    headers, data = _slice(rows, bounds["Stimulus Table"])
    si = _header_index(headers, "Step")
    di = _header_index(headers, "Description")
    if si is None or di is None:
        return {}
    out: dict[int, dict] = {}
    for row in data:
        try:
            step = int(float(row[si]))
        except (ValueError, IndexError):
            continue
        desc = row[di].strip() if len(row) > di else ""
        out[step] = classify_stimulus(desc)
    return out


def _parse_markers(rows, bounds) -> tuple[list[dict], dict[int, str]]:
    """Marker Table → marker rows + the channel→eye map (from the ``C``/``Eye`` columns)."""
    if "Marker Table" not in bounds:
        return [], {}
    headers, data = _slice(rows, bounds["Marker Table"])
    ci = {k: _header_index(headers, *v) for k, v in {
        "step": ("S", "Step"), "channel": ("C", "Chan"), "result": ("R", "Result"),
        "eye": ("Eye",), "uv": ("uV", "µV"), "ms": ("ms",),
    }.items()}
    # Two "Name" columns: animal (before Eye) + marker (after Eye). Take the one after Eye.
    eye_i = ci["eye"] if ci["eye"] is not None else 0
    marker_i = None
    for i, h in enumerate(headers):
        if _norm(h) == "name" and i > eye_i:
            marker_i = i
            break

    rows_out: list[dict] = []
    ch_eye: dict[int, str] = {}
    for row in data:
        def cell(key):
            i = ci[key]
            return row[i].strip() if (i is not None and len(row) > i) else ""

        eye = cell("eye")
        ch = cell("channel")
        try:
            ch_i = int(float(ch))
            if eye and ch_i not in ch_eye:
                ch_eye[ch_i] = eye
        except ValueError:
            ch_i = None
        marker = (row[marker_i].strip() if (marker_i is not None and len(row) > marker_i) else "")
        if not marker:
            continue
        try:
            step = int(float(cell("step")))
        except ValueError:
            continue
        amp = _to_float(cell("uv"))
        ims = _to_float(cell("ms"))
        rows_out.append({
            "step": step, "channel": ch_i, "eye": eye,
            "marker_name": marker, "marker_canon": _canon_marker(marker),
            "amplitude_uv": amp, "implicit_ms": ims,
        })
    return rows_out, ch_eye


def _canon_marker(name: str) -> str:
    """Case-fold the b-wave (``b``≡``B`` — the photopic/scotopic template difference is not a
    different feature); leave other markers as-is (lower-cased)."""
    n = name.strip()
    if n in ("a", "B", "b"):
        return n.lower()
    return n.lower()


def _to_float(s: str):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _data_blocks(headers: list[str]) -> list[tuple[int, int, list[int]]]:
    """Find each waveform step-block in the Data-Table headers → ``(step_no, time_col, chan_cols)``.
    A ``Step N`` header is the time column; the consecutive ``Chan k`` headers after it are its
    channels (indices are relative to the Data-Table slice)."""
    blocks: list[tuple[int, int, list[int]]] = []
    i = 0
    step_re = re.compile(r"step\s*(\d+)", re.IGNORECASE)
    while i < len(headers):
        m = step_re.fullmatch(headers[i].strip())
        if m:
            step = int(m.group(1))
            chans = []
            j = i + 1
            while j < len(headers) and headers[j].strip().lower().startswith("chan"):
                chans.append(j)
                j += 1
            if chans:  # a real waveform block (not the leading "Step" index column)
                blocks.append((step, i, chans))
                i = j
                continue
        i += 1
    return blocks


def _parse_waveforms(rows, bounds, stimulus, channel_eye, sample_id, condition):
    if "Data Table" not in bounds:
        return []
    headers, data = _slice(rows, bounds["Data Table"])
    blocks = _data_blocks(headers)
    if not blocks:
        return []

    # Order flash steps by intensity → Group1 (dimmest) … GroupN, ranked WITHIN each mode so a
    # scotopic series and a photopic series each start at Group1 (never interleaved).
    group_of: dict[int, str] = {}
    for kind in ("scotopic_flash", "photopic_flash"):
        steps_k = sorted((s for s in stimulus if stimulus[s]["stimulus_type"] == kind),
                         key=lambda s: (stimulus[s]["intensity_cd_s_m2"] or 0.0))
        for r, s in enumerate(steps_k, start=1):
            group_of[s] = f"Group{r}"

    # Primary recording channel per eye = the lowest channel index mapping to that eye; later
    # channels for the same eye (e.g. the OP-filtered band) are "secondary"; channels with no eye
    # are "aux". The trace grid feeds on the primary ERG channel per eye (see read_celeris).
    primary: dict[str, int] = {}
    for ch in sorted(channel_eye):
        if channel_eye[ch]:
            primary.setdefault(channel_eye[ch], ch)

    out: list[dict] = []
    for step, t_col, chan_cols in blocks:
        info = stimulus.get(step, {})
        st = info.get("stimulus_type", "")
        inten = info.get("intensity_cd_s_m2")
        log_i = math.log10(inten) if (inten and inten > 0) else None
        for k, c_col in enumerate(chan_cols, start=1):
            # collect (time, voltage_uv) for this step×channel, baseline-correct
            ts, vs = [], []
            for row in data:
                if len(row) <= max(t_col, c_col):
                    continue
                t = _to_float(row[t_col])
                v = _to_float(row[c_col])
                if t is None or v is None:
                    continue
                ts.append(t)
                vs.append(v / 1000.0)  # nV → µV
            if not ts:
                continue
            pre = [v for t, v in zip(ts, vs) if t < _PRESTIM_MS]
            base = sum(pre) / len(pre) if pre else 0.0
            eye = channel_eye.get(k, "")
            role = "primary" if (eye and primary.get(eye) == k) else ("secondary" if eye else "aux")
            for t, v in zip(ts, vs):
                out.append({
                    "sample_id": sample_id, "condition": condition, "condition_order": 1,
                    "eye": eye, "channel": k, "channel_role": role, "step": step,
                    "stimulus_type": st, "adaptation": info.get("adaptation", ""),
                    "flicker_hz": info.get("flicker_hz"),
                    "intensity_group": group_of.get(step, f"Step{step}"),
                    "intensity_cd_s_m2": inten, "intensity_log_cd_s_m2": log_i,
                    "time_ms": round(t, 4), "voltage_uv": round(v - base, 4),
                    "role": "representative",
                })
    return out


# ---- top-level -------------------------------------------------------------------------
def load_export(path: str, *, condition: str | None = None) -> CelerisExport:
    """Parse a Diagnosys Espion/Celeris export → :class:`CelerisExport`. Raises ``ValueError`` if
    the file carries no recognizable Marker/Data table."""
    rows, _delim = read_rows(path)
    if not rows or not is_diagnosys_export(path):
        raise ValueError(f"{os.path.basename(path)}: not a Diagnosys Espion/Celeris export "
                         "(no Marker Table / Data Table header).")

    bounds = _contents_bounds(rows)
    if bounds:
        # Integrity check: the Spreadsheet bound should match the physical row count; a mismatch
        # means a split line — repair, then re-locate.
        spread = bounds.get("Spreadsheet")
        if spread and spread.bottom != len(rows):
            rows = _repair_split_rows(rows, max(len(r) for r in rows))
            bounds = _contents_bounds(rows) or bounds
    else:
        rows = _repair_split_rows(rows, max(len(r) for r in rows))
        bounds = _banner_bounds(rows)
    if "Marker Table" not in bounds and "Data Table" not in bounds:
        raise ValueError(f"{os.path.basename(path)}: could not locate the Marker/Data tables.")

    sample_id = _condition_from_path(path)
    condition = condition or sample_id
    meta = _parse_header(rows, bounds)
    stimulus = _parse_stimulus(rows, bounds)
    markers, channel_eye = _parse_markers(rows, bounds)

    # No Stimulus Table (reduced CSV) → infer stimulus type per step from the markers.
    if not stimulus and markers:
        by_step: dict[int, set] = {}
        for m in markers:
            by_step.setdefault(m["step"], set()).add(m["marker_canon"])
        stimulus = {s: _infer_stimulus(v) for s, v in by_step.items()}

    waveforms = _parse_waveforms(rows, bounds, stimulus, channel_eye, sample_id, condition)
    return CelerisExport(sample_id=sample_id, condition=condition, meta=meta, stimulus=stimulus,
                         channel_eye=channel_eye, markers=markers, waveforms=waveforms)


def markers_long(exp: CelerisExport) -> list[dict]:
    """Every device marker → ``erg_markers_long`` rows (a/B/b/c-wave/N1/P1/…)."""
    out = []
    for m in exp.markers:
        info = exp.stimulus.get(m["step"], {})
        inten = info.get("intensity_cd_s_m2")
        out.append({
            "sample_id": exp.sample_id, "condition": exp.condition,
            "eye": m["eye"], "channel": m["channel"], "step": m["step"],
            "stimulus_type": info.get("stimulus_type", ""), "adaptation": info.get("adaptation", ""),
            "intensity_cd_s_m2": inten,
            "intensity_log_cd_s_m2": math.log10(inten) if (inten and inten > 0) else None,
            "flicker_hz": info.get("flicker_hz"),
            "marker_name": m["marker_canon"], "amplitude_uv": m["amplitude_uv"],
            "implicit_ms": m["implicit_ms"],
        })
    return out


def metrics_long(exp: CelerisExport) -> list[dict]:
    """The a/b view the existing ``erg_intensity_response`` / ``erg_bwave_bar`` read: one row per
    (eye, step) with the device a-wave + b-wave amplitude (µV) and implicit time (ms)."""
    by_key: dict[tuple, dict] = {}
    for m in markers_long(exp):
        key = (m["eye"], m["step"])
        rec = by_key.setdefault(key, {
            "sample_id": exp.sample_id, "condition": exp.condition, "condition_order": 1,
            "eye": m["eye"], "intensity_group": None, "step": m["step"],
            "intensity_cd_s_m2": m["intensity_cd_s_m2"],
            "intensity_log_cd_s_m2": m["intensity_log_cd_s_m2"],
            "stimulus_type": m["stimulus_type"],
            "a_wave_uv": None, "b_wave_uv": None,
            "a_wave_implicit_ms": None, "b_wave_implicit_ms": None,
        })
        if m["marker_name"] == "a":
            rec["a_wave_uv"], rec["a_wave_implicit_ms"] = m["amplitude_uv"], m["implicit_ms"]
        elif m["marker_name"] == "b":
            rec["b_wave_uv"], rec["b_wave_implicit_ms"] = m["amplitude_uv"], m["implicit_ms"]
    # intensity_group from the waveform grouping (Group1..N for flash steps)
    grp = {w["step"]: w["intensity_group"] for w in exp.waveforms}
    for rec in by_key.values():
        rec["intensity_group"] = grp.get(rec["step"], f"Step{rec['step']}")
    return list(by_key.values())


def waveforms_long(exp: CelerisExport) -> list[dict]:
    """The canonical ``erg_waveforms_long`` rows the ``erg_traces`` grid consumes."""
    return exp.waveforms


def read_celeris(path: str, *, condition: str | None = None, primary_only: bool = True):
    """Parse a Diagnosys export → the canonical ``erg_waveforms_long`` DataFrame (the ingest
    materialize path, mirroring ``_iwx.read_iwxdata``). By default keeps only the **primary ERG
    channel per eye** (one trace per eye per step — what the trace grid wants); pass
    ``primary_only=False`` to keep secondary/OP + aux channels too. Use :func:`load_export` for all
    tables (markers, metrics, waveforms)."""
    import pandas as pd

    df = pd.DataFrame(waveforms_long(load_export(path, condition=condition)))
    if primary_only and not df.empty and "channel_role" in df.columns:
        df = df[df["channel_role"] == "primary"].reset_index(drop=True)
    return df
