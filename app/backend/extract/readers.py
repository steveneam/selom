"""Layered metric reader — turn a skill's *output* into the panel's golden metric (live-repro gap #3).

The reproduction drive runs a panel's matched skill, then must read the panel's golden metric
(``de_total``, ``pc1_var``, …) back out of whatever the skill emitted. Skills carry their numbers in
**three** different places (``docs/reproduction-engine/skill-table-schemas.md``): a Statistics
``table`` (only 10 of ~30 skills), figure **strings** (PCA variance baked into the axis title), or
**trace arrays**. So this is not a table reader — it is layered, mirroring Selom's
``layered-deterministic-extraction`` philosophy:

* **L1 — skill-specific reader** (the accurate core). We almost always know ``panel.skill_id``, so a
  per-skill reader pulls the metric precisely from that skill's exact shape (``volcano``'s direction
  counts, ``pca``'s axis-title variance). Must-be-right.
* **L2 — generic reader** (best-effort gap-filler). No L1 entry → count directional rows / scan the
  figure strings for a percentage. Recall-first, lower confidence; degrades for unknown/new skills.
* **L3 — proprietary table synthesis** (the moat): when a skill emits *no* native table, this reader
  synthesizes a canonical one from the figure (``extract.synthesize``) and re-reads it, re-tagged
  ``L3``/synthesized at a reduced confidence (S3) — a real computed value re-shaped, so it MAY feed
  the score (S2), unlike a pixel-digitized read. **L4 — Pro AI** remains a separate, later tier.
  A metric no layer can reach returns ``None`` → the drive marks the panel ``needs_recipe``
  (reproducibility-axis only, **0 Selom-confidence defects**; never a false fail).

Pure functions over ``(skill_id, metric, figure, table)`` — no I/O, no skill execution. The drive
runs the skill (``reproduction.run_panel``) and hands the output here.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from extract.synthesize import synthesize_table
from skills._table import as_tables

# Reading layers + sources (provenance for the honest classification).
L1 = "L1"  # skill-specific
L2 = "L2"  # generic
L3 = "L3"  # proprietary table synthesis (extract.synthesize)
SRC_TABLE = "table"
SRC_FIGURE = "figure"
SRC_SYNTH = "synthesized"

# Directional vocab across skills (volcano up/down, diff_abundance expanding/shrinking, …).
_DIR_UP = {"up", "expanding", "increased", "gain", "enriched"}
_DIR_DOWN = {"down", "shrinking", "decreased", "loss", "depleted"}
# A metric is a *count* when it reads as "how many" — counts come from row tallies, not a cell.
_COUNT_RE = re.compile(r"(^|_)(n|total|count|num)($|_)|_(total|count|up|down)$", re.I)
_PCT_NUM_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*%")


class Reading(BaseModel):
    """One resolved metric: the value + where/how it was read (drives the honest scorecard)."""

    metric: str
    value: float | int | str | None
    layer: str          # L1 | L2
    source: str         # table | figure
    confidence: float = 1.0
    note: str = ""


# --- shared accessors ---------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _table_parts(table: dict | None) -> tuple[list[str], list[list]]:
    if not table:
        return [], []
    return list(table.get("columns", [])), list(table.get("rows", []))


def _fig_strings(figure: dict | None) -> list[str]:
    """Every human-readable string a figure carries — title, subtitle, axis titles, annotations.

    Plotly titles are ``{"text": …}`` or a bare string; this flattens both so a regex can sweep
    the lot (PCA variance, cluster/integration/regression/pvca all hide their numbers here)."""
    if not figure:
        return []
    out: list[str] = []
    layout = figure.get("layout", {}) or {}

    def _title_text(t) -> None:
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, dict):
            if isinstance(t.get("text"), str):
                out.append(t["text"])
            sub = t.get("subtitle")
            if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                out.append(sub["text"])

    _title_text(layout.get("title"))
    for ax in ("xaxis", "yaxis"):
        _title_text((layout.get(ax, {}) or {}).get("title"))
    for ann in layout.get("annotations", []) or []:
        if isinstance(ann, dict) and isinstance(ann.get("text"), str):
            out.append(ann["text"])
    return out


def _direction_col(columns: list[str], rows: list[list]) -> int | None:
    """The index of a direction-like column — by header (``direction``/``trend``) or by content
    (cells mostly in the up/down vocab). Lets the generic counter work across skill table shapes."""
    for i, c in enumerate(columns):
        if _norm(c) in {"direction", "trend"}:
            return i
    for i in range(len(columns)):
        vals = [str(r[i]).lower() for r in rows if i < len(r)]
        if vals and sum(v in _DIR_UP or v in _DIR_DOWN for v in vals) >= max(1, len(vals) // 2):
            return i
    return None


def de_counts(table: dict | None) -> tuple[int, int] | None:
    """``(up, down)`` regulated-row tallies from a canonical ``de_table``'s direction column,
    or ``None`` when the table carries no direction column.

    The single shared DE-count tally: ``_read_de_table`` (the grading read-back) and the figure-
    legend layer both reuse this rather than re-deriving the up/down split, so the count can never
    drift between the two (one source of truth, per the directional vocab above)."""
    columns, rows = _table_parts(table)
    di = _direction_col(columns, rows)
    if di is None:
        return None
    up = sum(1 for r in rows if di < len(r) and str(r[di]).lower() in _DIR_UP)
    down = sum(1 for r in rows if di < len(r) and str(r[di]).lower() in _DIR_DOWN)
    return up, down


def _title_total(table: dict | None) -> int | None:
    """The true total a capped ``de_table`` hides in its title: ``(top 300 of 1450 …)``."""
    title = (table or {}).get("title", "")
    m = re.search(r"top\s+\d+\s+of\s+(\d+)", str(title), re.I)
    return int(m.group(1)) if m else None


# --- L1: skill-specific readers -----------------------------------------------


def _read_de_table(metric: str, figure: dict | None, table: dict | None) -> Reading | None:
    """Shared DE-table reader for any skill emitting the canonical ``de_table``
    (gene·log2FC·padj·direction) — ``volcano`` and ``proteomics_de``. DE counts = directional
    row tallies; the true total comes from the title when the table is capped at 300 rows.
    (de_total = up + down, *not* the table's tested-protein row count — the trap the schema
    doc warns about for proteomics_de.)"""
    m = _norm(metric)
    if m not in {"detotal", "deup", "dedown"}:
        return None
    counts = de_counts(table)
    if counts is None:
        return None
    up, down = counts
    rows = _table_parts(table)[1]
    capped = len(rows) >= 300  # de_table max_rows; an exact count is no longer guaranteed
    note = "counted from de_table direction column"
    if m == "deup":
        value = up
    elif m == "dedown":
        value = down
    else:  # de_total = up + down (genes passing the threshold), not the title's tested-total
        value = up + down
        if capped:
            note += f"; table capped at {len(rows)} rows — DE total is a lower bound"
    return Reading(metric=metric, value=value, layer=L1, source=SRC_TABLE,
                   confidence=0.7 if capped else 1.0, note=note)


def _read_pca(metric: str, figure: dict | None, table: dict | None) -> Reading | None:
    """``pca`` bakes PC variance into the axis titles (``PC1 (39.7%)``) — no table."""
    m = _norm(metric)
    axis = {"pc1var": "xaxis", "pc2var": "yaxis"}.get(m)
    if axis is None:
        return None
    title = ((figure or {}).get("layout", {}).get(axis, {}) or {}).get("title")
    text = title.get("text") if isinstance(title, dict) else (title if isinstance(title, str) else "")
    hit = _PCT_NUM_RE.search(text or "")
    if not hit:
        return None
    return Reading(metric=metric, value=float(hit.group(1)), layer=L1, source=SRC_FIGURE,
                   confidence=1.0, note=f"read from {axis} title '{text}'")


def _read_umap(metric: str, figure: dict | None, table: dict | None) -> Reading | None:
    """``umap_scrna`` carries the analyzed dataset size as the number of *plotted points* —
    ``n_cells`` = total points across the embedding's scatter traces (one trace per cluster), no
    table. This is the read-back twin of ``extract.golden.extract_dataset_size`` (which lifts the
    printed ``n_cells``): when the matrix is matched, the UMAP's point count is graded against the
    paper's stated cell count. Returns ``None`` for any other metric (falls through to L2/L3)."""
    if _norm(metric) != "ncells":
        return None
    data = (figure or {}).get("data") or []
    total, seen = 0, False
    for tr in data:
        xs = tr.get("x") if isinstance(tr, dict) else None
        if isinstance(xs, (list, tuple)):
            total += len(xs)
            seen = True
    if not seen:
        return None
    return Reading(metric=metric, value=total, layer=L1, source=SRC_FIGURE, confidence=1.0,
                   note=f"counted {total} plotted points across {len(data)} UMAP trace(s)")


# skill_id -> its L1 reader. Adding a skill is one entry (and one function). volcano and
# proteomics_de share the canonical de_table, so both map to _read_de_table (proteomics_de
# needs L1 so de_total reads as up+down, not its tested-protein row count). umap_scrna reads
# n_cells off the plotted point count. The 8 other table-emitting skills (cepo/gsea/enrichment/
# pseudotime_genes/diff_abundance/markers/ssgsea/deg) resolve through the L2 generic reader by
# table key/count today; promote any to L1 as needed.
_SKILL_READERS = {"volcano": _read_de_table, "proteomics_de": _read_de_table, "pca": _read_pca,
                  "umap_scrna": _read_umap}


# --- L2: generic reader -------------------------------------------------------


def _read_count(metric: str, table: dict | None) -> Reading | None:
    """Count metrics (``n_*``/``*_total``/``de_up``/``de_down``) from row tallies — a row count is
    the count of *shown* rows (a lower bound when the table is capped; the title's total wins)."""
    if not _COUNT_RE.search(metric):
        return None
    columns, rows = _table_parts(table)
    if not rows:
        return None
    m = _norm(metric)
    di = _direction_col(columns, rows)
    if di is not None and (m.endswith("up") or m.endswith("down")):
        bucket = _DIR_UP if m.endswith("up") else _DIR_DOWN
        value = sum(1 for r in rows if di < len(r) and str(r[di]).lower() in bucket)
        return Reading(metric=metric, value=value, layer=L2, source=SRC_TABLE, confidence=0.6,
                       note="generic directional row count")
    total = _title_total(table)
    if total is not None and (m.endswith("total") or m.startswith("n")):
        return Reading(metric=metric, value=total, layer=L2, source=SRC_TABLE, confidence=0.7,
                       note="true total read from table title")
    return Reading(metric=metric, value=len(rows), layer=L2, source=SRC_TABLE, confidence=0.5,
                   note=f"count of {len(rows)} table rows (lower bound if capped)")


def _read_named_cell(metric: str, table: dict | None, key: str | None) -> Reading | None:
    """A named entity's value: find the row whose key-column cell matches ``key`` (or the metric),
    return its first numeric column (cepo gene DS, a named gsea term's NES, …)."""
    columns, rows = _table_parts(table)
    if not rows:
        return None
    want = _norm(key or metric)
    if not want:
        return None
    # the first string-valued column is the key column; the first numeric column is the value.
    str_cols = [i for i in range(len(columns))
                if any(i < len(r) and isinstance(r[i], str) for r in rows)]
    num_cols = [i for i in range(len(columns))
                if any(i < len(r) and isinstance(r[i], (int, float)) and not isinstance(r[i], bool)
                       for r in rows)]
    if not str_cols or not num_cols:
        return None
    ki, vi = str_cols[0], num_cols[0]
    for r in rows:
        if ki < len(r) and _norm(r[ki]) == want and vi < len(r):
            return Reading(metric=metric, value=r[vi], layer=L2, source=SRC_TABLE, confidence=0.6,
                           note=f"named-cell match '{r[ki]}' → column '{columns[vi]}'")
    return None


def _read_figure_number(metric: str, figure: dict | None) -> Reading | None:
    """A percentage/variance metric (``*_var``/``*_pct``/``*%``) lifted from a figure string."""
    m = _norm(metric)
    if not (m.endswith("var") or m.endswith("pct") or "percent" in m):
        return None
    for text in _fig_strings(figure):
        hit = _PCT_NUM_RE.search(text)
        if hit:
            return Reading(metric=metric, value=float(hit.group(1)), layer=L2, source=SRC_FIGURE,
                           confidence=0.4, note=f"first percentage in figure string '{text.strip()}'")
    return None


def _read_generic(metric: str, figure: dict | None, tables: list[dict],
                  key: str | None) -> Reading | None:
    """The generic read over N tables: try each table **in array order** and take the first that
    yields the metric (spec D4 — order is the runner's, and no `role` field is needed to pick).

    The figure reader stays the last resort rather than joining the per-table loop: it is the
    weakest layer (confidence 0.4), so a table read on the *second* table must still beat it. With
    one table this is byte-identical to the single-table order it replaces."""
    for t in tables:
        for reader in (
            lambda: _read_count(metric, t),
            lambda: _read_named_cell(metric, t, key),
        ):
            r = reader()
            if r is not None:
                return _tag_source(r, t)
    return _read_figure_number(metric, figure)


# --- public API ---------------------------------------------------------------


def _as_synthesized(r: Reading) -> Reading:
    """Re-tag a reading taken from an L3-synthesized table: distinct ``L3``/synthesized provenance
    and a reduced, capped confidence so it is never passed off as a native-table read (S3). The value
    is the engine's own number re-shaped, so it still MAY feed the score (S2)."""
    return r.model_copy(update={
        "layer": L3,
        "source": SRC_SYNTH,
        "confidence": round(min(r.confidence, 0.6) * 0.9, 3),
        "note": f"{r.note}; via L3-synthesized table",
    })


def _tag_source(r: Reading, table: dict) -> Reading:
    """Provenance follows the TABLE the value came out of, not the code path that fetched it.

    This used to be decided by position: only the reader's own L3 fallback branch re-tagged, so a
    synthesized table was known to be synthesized because of *where* it was built. A skill may now
    attach a native table AND its L3 summary in one list (`extract.synthesize.ALSO_SYNTHESIZE`), so
    that no longer holds — the second table would have been read at full native confidence, quietly
    OVERSTATING the provenance of a re-shaped value on a reproducibility score. Every synthesizer
    stamps ``synthesized: True`` (``synthesize._tbl``), so the flag on the table is the honest
    authority and this is the one place that reads it."""
    return _as_synthesized(r) if table.get("synthesized") else r


def read_metric(skill_id: str | None, metric: str, figure: dict | None,
                table: dict | list | None, *, key: str | None = None) -> Reading | None:
    """Resolve one golden ``metric`` from a skill's output — L1 (skill-specific), L2 (generic),
    then L3 (synthesize a table from the figure when the skill emits none).

    ``table`` is the wire union (``StatsTable | list[StatsTable] | None``); it is narrowed here,
    once, via ``as_tables``. ``key`` is an optional named entity (a gene/term/cell-type the golden
    refers to) for table cell lookup. Returns ``None`` when no layer can read it (→ the drive marks
    ``needs_recipe``)."""
    tables = as_tables(table)
    l1 = _SKILL_READERS.get(skill_id or "")
    if l1 is not None:
        # `or [None]` so a tableless skill still reaches the figure-reading L1s (pca, umap).
        for t in tables or [None]:
            r = l1(metric, figure, t)
            if r is not None:
                # A figure-reading L1 (pca/umap) took nothing from the table, so it keeps its own
                # provenance; a table-reading one inherits the table's.
                return _tag_source(r, t) if (t and r.source == SRC_TABLE) else r
    r = _read_generic(metric, figure, tables, key)
    if r is not None:
        return r
    # L3 — no native table yielded the metric: synthesize a canonical table from the figure
    # (read-not-recompute) and re-read it, re-tagged as synthesized. Only when the skill emits no
    # native table (S5: never overrides a real one); a skill with a synthesizer otherwise -> None.
    #
    # ⚑ This gate reads `not tables`, NOT `table is None`. Under the normalizer the latter is
    # permanently False for a caller that passes a list, which would silently kill synthesis for
    # every tableless skill and land it on NEEDS_RECIPE — a plumbing regression wearing the costume
    # of an honest verdict. `[]` must behave exactly as `None` did; guarded by G2b.
    if not tables and skill_id:
        synth = synthesize_table(skill_id, figure)
        if synth is not None:
            # No explicit re-tag here any more: `_read_generic` reads the table's own
            # `synthesized` flag, so this branch and an inline synthesized table are labelled by
            # the SAME rule. Tagging in both places would compound the confidence penalty twice.
            r = _read_generic(metric, figure, [synth], key)
            if r is not None:
                return r
    return None


def panel_extractor_readings(panel, figure: dict | None,
                             table: dict | list | None) -> dict[str, Reading]:
    """Every golden metric that resolved, as its full ``Reading`` — value **plus provenance**.

    The rich half of ``panel_extractor``. It exists because the reader already knows how it got the
    number — ``layer`` (L1/L2/**L3**), ``source`` (table/figure/**synthesized**) and its own
    ``confidence`` — and the scorecard was the one consumer that never received any of it: a metric
    the reader rated 0.45 off an L3-SYNTHESIZED table scored VERIFIED / 100 Selom-confidence,
    indistinguishable from a value read off the engine's own table (DECISIONS #16).

    The omit-never-``None`` rule lives HERE, and ``panel_extractor`` derives from it, so the two
    cannot drift on the distinction between "read a value, validate it" and "no reading →
    needs_recipe" — the latter must never become a Selom-confidence FAIL.
    """
    out: dict[str, Reading] = {}
    for gold in getattr(panel, "golden", []) or []:
        r = read_metric(getattr(panel, "skill_id", None), gold.metric, figure, table)
        if r is not None and r.value is not None:
            out[gold.metric] = r
    return out


def panel_extractor(panel, figure: dict | None, table: dict | list | None) -> dict:
    """A ``reproduction.run_panel``-compatible extractor: read every golden metric on ``panel``.

    Only metrics a layer could resolve are returned; an unreadable golden is **omitted** (not set
    to ``None``) — see ``panel_extractor_readings``, which owns that rule and this derives from.

    Deliberately still ``{metric: value}``: ``validate_panel`` compares these against the goldens
    with ``classify_metric``, so handing it ``Reading`` objects would break the comparison at every
    call site. A caller that wants provenance asks for the readings instead of re-reading — a
    second ``read_metric`` pass would re-run L3 SYNTHESIS for every tableless panel, paying the
    whole cost twice to recover something the first pass already had.
    """
    return {k: r.value for k, r in panel_extractor_readings(panel, figure, table).items()}


def panel_readings(panel, figure: dict | None, table: dict | list | None) -> list[Reading]:
    """Every golden's resolution attempt (found or not) — the drive's honest per-metric record."""
    readings: list[Reading] = []
    for gold in getattr(panel, "golden", []) or []:
        r = read_metric(getattr(panel, "skill_id", None), gold.metric, figure, table)
        readings.append(r or Reading(metric=gold.metric, value=None, layer=L2, source=SRC_TABLE,
                                      confidence=0.0, note="no reader resolved this metric"))
    return readings
