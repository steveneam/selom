"""Pure-stdlib reader for iWorx LabScribe ``.iwxdata`` ERG exports → a long waveform table.

An ``.iwxdata`` file is a ZIP holding one acquisition session (one eye, one scotopic flash
series): per-sweep text headers ``blkN/blk_setting.txt`` + per-sweep binary channel data
``blkN/CH000.dat``. This module decodes it into the canonical ``erg_waveforms_long`` shape the
``erg_traces`` skill consumes, so a native ``.iwxdata`` file can drop straight into Selom and be
recognized as ERG by FORMAT (engine.cleaning L1), not just by column keywords.

Decode (cracked empirically vs the lab's control oracle; see the original `iwx_parse.py`):
``CH000.dat`` = 128-byte header + NUM_CH_POINTS records of [8-byte **big-endian** float64 +
2 pad bytes]; stored values are mV at the ±2.5 mV gain → microvolts via ``UV_PER_RAW = 100``
(per-group Pearson r = 0.88–0.96 vs the oracle). Pure stdlib (zipfile/struct/re) — no numpy on
the decode path; pandas is imported lazily only to assemble the final frame.
"""

from __future__ import annotations

import os
import re
import struct
import zipfile
from dataclasses import dataclass, field

# ---- format constants (from acq_setting.txt; see module docstring) ---------------------
HEADER_BYTES = 128
RECORD_BYTES = 10            # 8-byte double + 2 pad
DOUBLE_FMT = ">d"           # big-endian IEEE float64
NUM_CH_POINTS = 1500        # samples per sweep
SPEED_HZ = 5000.0           # sampling rate → 0.2 ms/sample, 300 ms sweep
UV_PER_RAW = 100.0          # microvolts per stored raw unit
_PRESTIM_SAMPLES = 50       # first 10 ms → baseline (subtracted)

# Scotopic protocol: 7 flash intensities; the log flash energies (log cd·s/m²) for Group1..7.
GROUP_LOG_ENERGIES = (-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1)
GROUP_SWEEP_COUNTS = (10, 10, 10, 10, 10, 5, 5)   # fallback positional split (sums to 60)
N_GROUPS = 7


# ---- low-level decode ------------------------------------------------------------------
def decode_dat(blob: bytes, scale: float = UV_PER_RAW) -> list[float]:
    """Decode one ``CH000.dat`` byte string → samples in microvolts (raw float64 × scale)."""
    n = min((len(blob) - HEADER_BYTES) // RECORD_BYTES, NUM_CH_POINTS)
    out, off = [], HEADER_BYTES
    for _ in range(n):
        out.append(struct.unpack_from(DOUBLE_FMT, blob, off)[0] * scale)
        off += RECORD_BYTES
    return out


def time_axis_ms(n: int = NUM_CH_POINTS) -> list[float]:
    step = 1000.0 / SPEED_HZ
    return [i * step for i in range(n)]


# ---- per-eye model ---------------------------------------------------------------------
@dataclass
class Eye:
    """A decoded eye: ``N_GROUPS`` averaged, baseline-corrected intensity traces (µV)."""

    sample_id: str
    condition: str                    # biological group from the filename (strain), or "ERG"
    eye: str                          # "LE" / "RE" / ""
    groups: list[list[float]]         # N_GROUPS traces, each ≤NUM_CH_POINTS µV samples
    n_sweeps: int = 0
    sweep_counts: tuple = field(default_factory=tuple)


_FNAME_RE = re.compile(r"(?P<strain>C57Bl6|C57|Rd10)\s*#?\s*(?P<mouse>\d+).*?_\s*(?P<eye>LE|RE)\b",
                       re.IGNORECASE)


def parse_filename(path: str) -> tuple[str, str, str] | None:
    """(mouse, eye, strain) from an .iwxdata filename, or ``None`` if it doesn't match the
    study's naming (e.g. ``C57Bl6 #677_LE Scotopic Green.iwxdata`` → ('677','LE','C57'))."""
    m = _FNAME_RE.search(os.path.basename(path))
    if not m:
        return None
    strain = m.group("strain")
    return m.group("mouse"), m.group("eye").upper(), ("C57" if strain.upper().startswith("C57") else strain)


def _sorted_blocks(zf: zipfile.ZipFile) -> list[int]:
    idxs = {int(m.group(1)) for n in zf.namelist()
            if (m := re.match(r"blk(\d+)/", n)) and n.endswith("CH000.dat")}
    return sorted(idxs)


_SWEEP_INFO_RE = re.compile(r"SWEEP_INFO\s+(\d+)\s+([\d.]+)\s+(\d+)")


def _read_sweep_info(zf: zipfile.ZipFile, blk: int):
    """(intensity_index, flash_param, block_id) for blkN, or ``None``. The block_id packs the
    intensity index in its high 16 bits — a self-describing grouping key (robust to re-acquired
    or aborted sweeps)."""
    try:
        txt = zf.read(f"blk{blk}/blk_setting.txt").decode("latin-1", "replace")
    except KeyError:
        return None
    m = _SWEEP_INFO_RE.search(txt)
    if not m:
        return None
    block_id = int(m.group(3))
    return (block_id >> 16, float(m.group(2)), block_id)


def _canonical_groups(records: list[tuple]) -> list[list[int]]:
    """Collapse per-sweep records into the 7 protocol intensities by the block-ID intensity
    index, merging short aborted runs forward (by shared flash param) until 7 remain."""
    order: list[int] = []
    by_idx: dict[int, list[tuple]] = {}
    for blk, inten, fp in records:
        if inten not in by_idx:
            by_idx[inten] = []
            order.append(inten)
        by_idx[inten].append((blk, fp))
    groups = [by_idx[i] for i in order]

    guard = 0
    while len(groups) > N_GROUPS and guard < 50:
        guard += 1
        merged = False
        for j in range(len(groups) - 1):
            if len(groups[j]) < 3:                      # short aborted run
                fp_j = groups[j][0][1]
                for k in range(j + 1, len(groups)):
                    if groups[k][0][1] == fp_j:
                        groups[k] = groups[j] + groups[k]
                        del groups[j]
                        merged = True
                        break
            if merged:
                break
        if not merged:                                  # fall back: merge smallest neighbour
            sizes = [len(g) for g in groups]
            j = sizes.index(min(sizes))
            tgt = j + 1 if j + 1 < len(groups) else j - 1
            groups[tgt] = groups[j] + groups[tgt]
            del groups[j]
    return [[blk for blk, _fp in g] for g in groups]


def _positional_groups(blks: list[int]) -> list[list[int]]:
    """Fallback when SWEEP_INFO is unavailable: split by the fixed protocol sweep counts."""
    out, idx = [], 0
    for c in GROUP_SWEEP_COUNTS:
        out.append(blks[idx:idx + c])
        idx += c
    return out


def load_eye(path: str, scale: float = UV_PER_RAW) -> Eye:
    """Decode an .iwxdata file → an :class:`Eye`. Groups sweeps by intensity, averages within
    each, and baseline-corrects (subtracts the pre-stim mean). Raises ``ValueError`` if the
    grouping doesn't yield the 7 scotopic intensities (e.g. a photopic file — honestly unsupported)."""
    parsed = parse_filename(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    if parsed:
        mouse, eye, strain = parsed
        sample_id, condition = f"{mouse}_{eye}", strain
    else:
        mouse = eye = ""
        sample_id, condition = stem, "ERG"

    with zipfile.ZipFile(path) as zf:
        blks = _sorted_blocks(zf)
        if not blks:
            raise ValueError(f"{os.path.basename(path)}: no CH000.dat sweeps found — not a LabScribe ERG export")
        records = []
        for blk in blks:
            si = _read_sweep_info(zf, blk)
            records.append((blk, si[0] if si else None, si[1] if si else None))
        grouped = _positional_groups(blks) if any(r[1] is None for r in records) else _canonical_groups(records)
        if len(grouped) != N_GROUPS:
            raise ValueError(
                f"{os.path.basename(path)}: got {len(grouped)} intensity groups, expected {N_GROUPS} "
                "(this reader supports the 7-intensity scotopic protocol)")

        groups: list[list[float]] = []
        for blk_list in grouped:
            block = [decode_dat(zf.read(f"blk{b}/CH000.dat"), scale=scale) for b in blk_list]
            npts = min(len(s) for s in block)
            avg = [sum(s[i] for s in block) / len(block) for i in range(npts)]
            base = sum(avg[:_PRESTIM_SAMPLES]) / _PRESTIM_SAMPLES
            groups.append([v - base for v in avg])

    return Eye(sample_id=sample_id, condition=condition, eye=eye, groups=groups,
               n_sweeps=len(blks), sweep_counts=tuple(len(g) for g in grouped))


def waveforms_long(eye: Eye) -> list[dict]:
    """Project a decoded :class:`Eye` → the canonical ``erg_waveforms_long`` rows (one row per
    intensity-group × sample): ``sample_id, condition, condition_order, intensity_group,
    intensity_log_cd_s_m2, time_ms, voltage_uv, role`` — exactly what ``erg_traces`` consumes."""
    t = time_axis_ms()
    rows: list[dict] = []
    for gi, trace in enumerate(eye.groups):
        grp = f"Group{gi + 1}"
        log = GROUP_LOG_ENERGIES[gi] if gi < len(GROUP_LOG_ENERGIES) else None
        for i, v in enumerate(trace):
            rows.append({
                "sample_id": eye.sample_id, "condition": eye.condition, "condition_order": 1,
                "intensity_group": grp, "intensity_log_cd_s_m2": log,
                "time_ms": round(t[i], 4), "voltage_uv": round(v, 4), "role": "representative",
            })
    return rows


def read_iwxdata(path: str):
    """Decode an .iwxdata file → a pandas DataFrame in the ``erg_waveforms_long`` shape."""
    import pandas as pd

    return pd.DataFrame(waveforms_long(load_eye(path)))
