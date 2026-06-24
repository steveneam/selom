"""Pure-stdlib reader for iWorx LabScribe ``.iwxdata`` ERG exports → a long waveform table.

An ``.iwxdata`` file is a ZIP holding one acquisition session (one eye, one flash series — scotopic
green, photopic, or another lab's protocol): per-sweep text headers ``blkN/blk_setting.txt`` +
per-sweep binary channel data ``blkN/CH000.dat``. This module decodes it into the canonical
``erg_waveforms_long`` shape the ``erg_traces`` skill consumes, so a native ``.iwxdata`` file can
drop straight into Selom and be recognized as ERG by FORMAT (engine.cleaning L1), not just by column
keywords. The intensity-group COUNT is read from the file (not assumed) and the calibrated energy
ladder is filled in per-protocol from the registry below (see ``Protocol``/``resolve_protocol``).

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

# ---- protocol registry (the "fill in the blanks" calibration layer) --------------------
# An .iwxdata file is self-describing about how many intensity GROUPS it holds and their order
# (the SWEEP_INFO block-ID intensity index, read below) — but NOT about each group's calibrated
# flash energy: the device flash_param repeats across ND-filter steps (scotopic Group1–4 all read
# 0.7), so cd·s/m² is lab calibration that lives OUTSIDE the file. Therefore decode is fully
# file-driven (ANY group count — 7 scotopic, 5 photopic, or another lab's ladder) and this small
# registry fills the blanks: the calibrated ladder + adaptation per known protocol. An unrecognised
# protocol still decodes — honestly, with ordinal Group labels and intensity left unknown until its
# ladder is registered here (owner steer 2026-06-24: solve the group-count blocker, don't fork a
# photopic skill).
@dataclass(frozen=True)
class Protocol:
    name: str                       # adaptation: "scotopic" | "photopic" | "" (unrecognised)
    n_groups: int                   # expected intensity-group count (0 = accept whatever decodes)
    log_energies: tuple = ()        # calibrated log cd·s/m² per group; () = uncalibrated (a "blank")
    sweep_counts: tuple = ()        # positional split for SWEEP_INFO-less files (else unused)


# Scotopic green: 7 intensities, the validated CMRI ladder (Group1 dim … Group7 bright).
SCOTOPIC = Protocol("scotopic", 7, (-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1), (10, 10, 10, 10, 10, 5, 5))
# Photopic (light-adapted): 5 flash steps — count confirmed from the real Experiment-10/11 files;
# the cd·s/m² ladder is pending the owner's photopic calibration sheet (register it on the tuple
# below the moment it's supplied, and photopic rows light up with real intensities automatically).
PHOTOPIC = Protocol("photopic", 5, (), (10, 10, 10, 5, 5))
_KNOWN = (SCOTOPIC, PHOTOPIC)

# Back-compat alias (the scotopic ladder used to be the only protocol; mirrors _erg.INTENSITIES_LOG).
GROUP_LOG_ENERGIES = SCOTOPIC.log_energies
# Map a protocol's adaptation name → the canonical stimulus_type the figure skills filter on, so a
# combined scotopic+photopic cohort doesn't collide on shared Group labels. Mirrors
# _erg._ADAPT_STIM (kept local so this module stays pure-stdlib — no numpy on the decode path).
_STIMULUS_TYPE = {"scotopic": "scotopic_flash", "photopic": "photopic_flash"}

_SCOTOPIC_HINTS = ("scotop",)
_PHOTOPIC_HINTS = ("photop", "potop")   # "potop" tolerates the real "Potopic UV" filename typo


def detect_stimulus(path: str) -> str:
    """Scotopic/photopic hint from the filename ('' if neither) — the device records the protocol
    name only in the filename, so it disambiguates two protocols that share a group count."""
    low = os.path.basename(path).lower()
    if any(h in low for h in _SCOTOPIC_HINTS):
        return "scotopic"
    if any(h in low for h in _PHOTOPIC_HINTS):
        return "photopic"
    return ""


def resolve_protocol(stim_hint: str, n_groups: int) -> Protocol:
    """Pick the calibration protocol: a filename hint wins (it carries the merge target + ladder),
    else match by decoded group count, else a generic pass-through (ordinal labels, no calibration —
    the honest default for an unrecognised lab/protocol until its ladder is registered)."""
    for p in _KNOWN:
        if stim_hint and p.name == stim_hint:
            return p
    for p in _KNOWN:
        if n_groups and p.n_groups == n_groups:
            return p
    return Protocol(stim_hint, n_groups, (), ())


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
    """A decoded eye: one averaged, baseline-corrected trace per intensity group (µV). The group
    count is file-driven (7 scotopic, 5 photopic, …); ``protocol`` carries the calibration."""

    sample_id: str
    condition: str                    # biological group from the filename (strain), or "ERG"
    eye: str                          # "LE" / "RE" / ""
    groups: list[list[float]]         # one averaged trace per intensity group, ≤NUM_CH_POINTS µV
    n_sweeps: int = 0
    sweep_counts: tuple = field(default_factory=tuple)
    protocol: Protocol = SCOTOPIC     # resolved stimulus protocol (calibration ladder + adaptation)


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


def _canonical_groups(records: list[tuple], target: int = 0) -> list[list[int]]:
    """Collapse per-sweep records into intensity groups by the block-ID intensity index (first-seen
    order). When ``target`` > 0 and MORE groups decode than the protocol expects (a re-acquired or
    aborted run created an extra index), merge short runs forward — by shared flash param, else the
    smallest neighbour — until ``target`` remain (the validated scotopic behaviour). ``target`` == 0
    (unknown protocol) keeps every decoded group untouched — we never mangle an unrecognised ladder."""
    order: list[int] = []
    by_idx: dict[int, list[tuple]] = {}
    for blk, inten, fp in records:
        if inten not in by_idx:
            by_idx[inten] = []
            order.append(inten)
        by_idx[inten].append((blk, fp))
    groups = [by_idx[i] for i in order]

    guard = 0
    while target and len(groups) > target and guard < 50:
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


def _positional_groups(blks: list[int], sweep_counts: tuple) -> list[list[int]]:
    """Fallback when SWEEP_INFO is unavailable: split by the resolved protocol's fixed sweep counts."""
    out, idx = [], 0
    for c in sweep_counts:
        out.append(blks[idx:idx + c])
        idx += c
    return out


def load_eye(path: str, scale: float = UV_PER_RAW, protocol: Protocol | None = None) -> Eye:
    """Decode an .iwxdata file → an :class:`Eye`. Groups sweeps into intensities by the file's own
    SWEEP_INFO block-ID index (so the group COUNT is file-driven — 7 scotopic, 5 photopic, or any
    other lab's count), averages within each, and baseline-corrects (subtracts the pre-stim mean).
    The calibrated intensity ladder + adaptation come from the resolved :class:`Protocol`
    (filename-hinted; pass ``protocol`` to override). An unrecognised protocol still decodes — with
    ordinal Group labels and intensity left unknown. Raises ``ValueError`` only when no sweeps decode,
    or SWEEP_INFO is absent on an unknown protocol (then the grouping is genuinely undetermined)."""
    parsed = parse_filename(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    if parsed:
        mouse, eye, strain = parsed
        sample_id, condition = f"{mouse}_{eye}", strain
    else:
        mouse = eye = ""
        sample_id, condition = stem, "ERG"

    stim_hint = detect_stimulus(path)
    with zipfile.ZipFile(path) as zf:
        blks = _sorted_blocks(zf)
        if not blks:
            raise ValueError(f"{os.path.basename(path)}: no CH000.dat sweeps found — not a LabScribe ERG export")
        records = []
        for blk in blks:
            si = _read_sweep_info(zf, blk)
            records.append((blk, si[0] if si else None, si[1] if si else None))

        if any(r[1] is None for r in records):          # no SWEEP_INFO → need a known positional split
            proto = protocol or resolve_protocol(stim_hint, 0)
            if not proto.sweep_counts:
                raise ValueError(
                    f"{os.path.basename(path)}: no SWEEP_INFO and unrecognised protocol "
                    f"{stim_hint or '(none)'!r} — cannot determine the intensity grouping")
            grouped = _positional_groups(blks, proto.sweep_counts)
        else:
            raw_count = len({r[1] for r in records})    # distinct block-ID intensity indices
            proto = protocol or resolve_protocol(stim_hint, raw_count)
            # Merge down only when MORE groups decoded than the protocol expects (aborted/re-acquired
            # runs); an unknown protocol (target 0) keeps every decoded group as-is.
            target = proto.n_groups if (proto.n_groups and raw_count > proto.n_groups) else 0
            grouped = _canonical_groups(records, target=target)

        groups: list[list[float]] = []
        for blk_list in grouped:
            block = [decode_dat(zf.read(f"blk{b}/CH000.dat"), scale=scale) for b in blk_list]
            npts = min(len(s) for s in block)
            avg = [sum(s[i] for s in block) / len(block) for i in range(npts)]
            base = sum(avg[:_PRESTIM_SAMPLES]) / _PRESTIM_SAMPLES
            groups.append([v - base for v in avg])

    return Eye(sample_id=sample_id, condition=condition, eye=eye, groups=groups,
               n_sweeps=len(blks), sweep_counts=tuple(len(g) for g in grouped), protocol=proto)


def waveforms_long(eye: Eye) -> list[dict]:
    """Project a decoded :class:`Eye` → the canonical ``erg_waveforms_long`` rows (one row per
    intensity-group × sample): ``sample_id, condition, condition_order, intensity_group,
    intensity_log_cd_s_m2, stimulus_type, time_ms, voltage_uv, role`` — exactly what ``erg_traces``
    consumes. ``intensity_log_cd_s_m2`` is the protocol's calibrated energy (``None`` for an
    uncalibrated protocol, e.g. photopic pending its ladder); ``stimulus_type`` tags the adaptation
    (``scotopic_flash``/``photopic_flash``/"") so a combined scotopic+photopic cohort doesn't collide
    on the shared ``GroupN`` labels (the figure skills filter on it via ``_erg.resolve_flash_mode``)."""
    t = time_axis_ms()
    proto = eye.protocol
    energies = proto.log_energies
    stim = _STIMULUS_TYPE.get(proto.name, "")
    rows: list[dict] = []
    for gi, trace in enumerate(eye.groups):
        grp = f"Group{gi + 1}"
        log = energies[gi] if gi < len(energies) else None
        for i, v in enumerate(trace):
            rows.append({
                "sample_id": eye.sample_id, "condition": eye.condition, "condition_order": 1,
                "intensity_group": grp, "intensity_log_cd_s_m2": log, "stimulus_type": stim,
                "time_ms": round(t[i], 4), "voltage_uv": round(v, 4), "role": "representative",
            })
    return rows


def read_iwxdata(path: str):
    """Decode an .iwxdata file → a pandas DataFrame in the ``erg_waveforms_long`` shape."""
    import pandas as pd

    return pd.DataFrame(waveforms_long(load_eye(path)))
