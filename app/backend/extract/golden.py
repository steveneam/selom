"""Golden-target + methods-digest extraction (E2) — the high-value, novel front-half.

Numbers that exist as selectable PDF text are read from the **text layer at confidence 1.0**
(no vision, no hallucination — E2); the vision LLM is reserved for semantics/association
(deferred). Slice-1 ships the most load-bearing reads:

* :func:`extract_de_counts` — differential-expression counts (total / up / down) + the stated
  threshold + a best-effort figure ref, from the paper's own phrasing
  (``"180 ... differentially expressed, with 61 upregulated and 119 downregulated"``).
* :func:`extract_methods_digest` — the STAR-Methods recipe (tool / normalization / threshold /
  filter) via a lexicon.
* :func:`find_figures_vs_methods` — guard-2 inconsistency capture when the same quantity is
  printed twice with different values (e.g. RPGRIP1 signature = 78 in results, 181 in methods).

Plus the bridge into the engine: :func:`to_golden` / :func:`to_engine_panels` produce the
``Golden``/``Panel`` objects that ``build_ledger()`` hand-encodes today.
"""

from __future__ import annotations

import re

import reproduction as R

from .classify import CaptionRuleClassifier, Classifier, classify_scope
from .models import (
    SOURCE_FIGURE,
    ExtractedSpec,
    GoldenTarget,
    MethodsDigest,
    PanelDraft,
)

# --- methods-digest lexicon ---------------------------------------------------

_TOOLS = (
    "edgeR", "DESeq2", "pyDESeq2", "limma", "voom", "fgsea", "gseapy", "GSEA", "Seurat",
    "scanpy", "CIBERSORT", "enrichR", "FindAllMarkers", "FindMarkers", "Harmony",
    "SCTransform", "topTable", "lmFit", "eBayes", "Slingshot", "monocle", "DoubletFinder",
    "emptyDrops", "Cepo", "GLM-PCA", "glmLRT", "Louvain", "Leiden",
)
_NORMALIZATIONS = (
    "TMM", "RLE", "VST", "CPM", "RPKM", "FPKM", "TPM", "SCTransform", "LogNormalize",
    "quantile normali", "z-score", "log2", "variance stabilis", "variance stabiliz",
)
_THRESHOLD_RE = re.compile(
    r"(?:adj(?:usted)?\.?\s*|FDR[ -]?|BH[ -]?)?[pq][\s-]*(?:value|val)?\s*[<≤]\s*0?\.\d+",
    re.I,
)
_FILTER_RE = re.compile(
    r"(?:CPM|counts?|reads?|\|log2?FC\||log2?\s*fold\s*change)\s*[<>≥≤]\s*\d*\.?\d+", re.I
)


def _uniq(seq):
    seen, out = set(), []
    for s in seq:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _has_token(token: str, text: str) -> bool:
    """Lexicon hit with a LEADING word boundary (not loose substring) — so 'RLE' doesn't fire
    inside 'Mo[rle]y' yet 'TMM' still matches '(TMM)'. No trailing boundary, so phrase prefixes
    ('variance stabilis') still match 'variance stabilised'."""
    return re.search(r"\b" + re.escape(token), text, re.I) is not None


def extract_methods_digest(text: str, *, panel_key: str = "") -> MethodsDigest:
    """Parse the methods recipe from PDF text via the lexicon (the pure 'grep' half of
    grep-then-vision). Returns the tools / normalizations / thresholds / filters present."""
    flat = re.sub(r"\s+", " ", text)
    tools = [t for t in _TOOLS if _has_token(t, flat)]
    norms = [n for n in _NORMALIZATIONS if _has_token(n, flat)]
    thresholds = _uniq(m.group(0).strip() for m in _THRESHOLD_RE.finditer(flat))
    filters = _uniq(m.group(0).strip() for m in _FILTER_RE.finditer(flat))
    return MethodsDigest(panel_key=panel_key, tools=_uniq(tools), normalizations=_uniq(norms),
                         thresholds=thresholds, filters=filters)


# --- differential-expression count extraction (text-layer-exact) --------------

_UP_RE = re.compile(r"(\d+)[^.\d]{0,45}?up[\s-]?regulated", re.I)
_DOWN_RE = re.compile(r"(\d+)[^.\d]{0,45}?down[\s-]?regulated", re.I)
_FIG_RE = re.compile(r"Figures?\s*([0-9]+\s*[a-z]?)", re.I)
_TOTAL_RE = re.compile(r"(\d+)[^.\d]{0,45}?differentially expressed", re.I)


def _num(rx: re.Pattern, win: str) -> int | None:
    m = rx.search(win)
    return int(m.group(1)) if m else None


def _sentence_bounds(flat: str, pos: int) -> tuple[int, int]:
    """The sentence containing ``pos`` (split on '. '). Bounding to one sentence stops a
    neighbouring count sentence from bleeding into this one (the 12/23-vs-61/119 cross-talk)."""
    left = flat.rfind(". ", 0, pos)
    left = 0 if left == -1 else left + 2
    right = flat.find(". ", pos)
    right = len(flat) if right == -1 else right + 1
    return left, right


def _nearest_figure(win: str, anchor: int) -> tuple[str, str]:
    """Best-effort figure/panel for a count, the non-supplementary ref nearest the anchor.

    Precise panel assignment is the (deferred) segmentation/vision job; this is the honest
    text-only heuristic — good enough to label the count, flagged best-effort."""
    refs = []
    for m in _FIG_RE.finditer(win):
        label = re.sub(r"\s+", "", m.group(1))
        if label[:1].isalpha():  # "S1e" supplementary — skip for main-figure assignment
            continue
        refs.append((label, abs(m.start() - anchor)))
    if not refs:
        return "", ""
    label = min(refs, key=lambda t: t[1])[0]
    fig = re.match(r"(\d+)", label).group(1)
    panel = label[len(fig):]
    return fig, panel


def extract_de_counts(text: str, paper_id: str = "") -> list[GoldenTarget]:
    """Recover differential-expression counts (de_total / de_up / de_down) from the text layer.

    Anchors on each ``"differentially expressed"`` mention; emits a target group only when BOTH
    up- and down-counts are present in the window (so methods sentences like 'top 100 most
    differentially expressed genes' are skipped). ``de_total`` is set to ``up + down`` (the
    arithmetic truth — avoids conflating a neighbouring 'top 50' heatmap count), with the
    printed total noted if it differs. Deduped by (up, down); the entry with a real figure ref
    and a stated threshold wins."""
    flat = re.sub(r"\s+", " ", text)
    best: dict[tuple[int, int], dict] = {}
    for anchor in re.finditer(r"differentially expressed", flat, re.I):
        left, right = _sentence_bounds(flat, anchor.start())
        win = flat[left:right]
        up, down = _num(_UP_RE, win), _num(_DOWN_RE, win)
        if up is None or down is None:
            continue  # not a count sentence (no up/down in this sentence)
        total = up + down
        printed_total = _num(_TOTAL_RE, win)
        thr = _THRESHOLD_RE.search(win)
        # Counts come from the tight sentence; the figure ref often sits in the PRECEDING
        # sentence ("volcano plot (Figure 4e). In total, 180 ... differentially expressed"),
        # so search one sentence wider — nearest-distance still keeps an in-sentence ref.
        fig_left = _sentence_bounds(flat, left - 2)[0] if left > 0 else 0
        fig, panel = _nearest_figure(flat[fig_left:right], anchor.start() - fig_left)
        note = f"threshold {thr.group(0).strip()}" if thr else ""
        if printed_total is not None and printed_total != total:
            note = (note + "; " if note else "") + f"printed total {printed_total}"
        cand = {"up": up, "down": down, "total": total, "fig": fig, "panel": panel, "note": note,
                "score": (1 if fig else 0) + (1 if thr else 0)}
        key = (up, down)
        if key not in best or cand["score"] > best[key]["score"]:
            best[key] = cand
    out: list[GoldenTarget] = []
    for c in best.values():
        common = dict(paper_id=paper_id, figure=c["fig"], panel=c["panel"], unit="",
                      source=SOURCE_FIGURE, confidence=1.0)
        out.append(GoldenTarget(metric="de_total", value=c["total"], note=c["note"], **common))
        out.append(GoldenTarget(metric="de_up", value=c["up"], note=c["note"], **common))
        out.append(GoldenTarget(metric="de_down", value=c["down"], note=c["note"], **common))
    return out


# --- inconsistency capture (guard 2: figures ≠ methods) -----------------------


def find_figures_vs_methods(metric: str, values: list[int | float], *,
                            printed_in: list[str] | None = None,
                            note: str = "") -> R.Inconsistency | None:
    """Guard 2 — when the SAME quantity is printed with two+ different values (e.g. RPGRIP1
    signature = 78 in results vs 181 in methods), record both as an inconsistency. Returns
    ``None`` when the values agree (no inconsistency)."""
    distinct = sorted({v for v in values})
    if len(distinct) < 2:
        return None
    return R.Inconsistency(
        kind="figures_vs_methods",
        printed_in=printed_in or [],
        conflicting_value=[f"{metric}={v}" for v in distinct],
        note=note or f"{metric} printed as {distinct} in different places — capture both",
    )


# --- orchestration: PDF text → ExtractedSpec ----------------------------------


def build_extracted_spec(ingested, paper_id: str, *, classifier: Classifier | None = None,
                         text: str | None = None) -> ExtractedSpec:
    """Assemble the slice-1 target spec from an ingested paper: methods digest + DE-count
    goldens + coarse per-panel drafts (scope + chart form).

    ``ingested`` is an :class:`~extract.ingest.IngestedPaper`, an
    :class:`~extract.ingest.PaperBundle` (E7 — DE counts read the main paper's figures, the
    methods digest reads the whole corpus incl. supplement extended-methods), or pass ``text=``
    directly in tests."""
    if text is not None:
        methods_body = counts_body = text
    elif hasattr(ingested, "main"):  # PaperBundle: counts from the figures, methods from the corpus
        counts_body = ingested.main.text
        methods_body = ingested.text
    else:                            # single IngestedPaper
        methods_body = counts_body = ingested.text
    classifier = classifier or CaptionRuleClassifier()
    methods = [extract_methods_digest(methods_body)]
    goldens = extract_de_counts(counts_body, paper_id)
    panels: list[PanelDraft] = []
    seen: set[str] = set()
    for g in goldens:
        if g.panel_key in seen:
            continue
        seen.add(g.panel_key)
        chart_form, conf = classifier.classify_chart(g.note)
        panels.append(PanelDraft(paper_id=paper_id, figure=g.figure, panel=g.panel,
                                 chart_form=chart_form, scope=classify_scope(g.note),
                                 caption=g.note, confidence=conf))
    return ExtractedSpec(paper_id=paper_id, panels=panels, goldens=goldens, methods=methods)


# --- bridge into the engine ---------------------------------------------------


def to_golden(t: GoldenTarget) -> R.Golden:
    """Convert an extracted :class:`GoldenTarget` into the engine's ``Golden``."""
    return R.Golden(metric=t.metric, value=t.value, unit=t.unit, source=t.source,
                    confidence=t.confidence, note=t.note, inconsistency_ref=t.inconsistency_ref)


def to_engine_panels(spec: ExtractedSpec, *, feasibility=None) -> list[R.Panel]:
    """Group the spec's goldens by panel into engine ``Panel`` objects — the auto-generated
    form of what ``build_ledger()`` hand-encodes (coarse in slice-1; segmentation refines it).

    When a Skill Keyword Index ``feasibility`` map is passed (fast-follow #1), each panel's
    ``skill_id`` is stamped from its figure's route (the figure's top in-scope skill), and an
    out-of-scope figure overrides ``scope`` with the mapped engine scope. ``feasibility=None``
    leaves the output byte-identical to before (``skill_id`` stays ``None``). The route resolves to
    figure granularity, so every panel of a figure inherits that figure's primary skill — see
    ``extract.routing.engine.route_to_panels`` for the rationale."""
    from .routing.models import is_skill, scope_of, skill_id  # lazy: routing depends on engine bits

    routes = {fr.figure: fr for fr in (feasibility.figures if feasibility else [])}
    drafts = {d.key: d for d in spec.panels}
    by_panel: dict[str, list[GoldenTarget]] = {}
    for t in spec.goldens:
        by_panel.setdefault(t.panel_key, []).append(t)
    panels: list[R.Panel] = []
    for key, targets in by_panel.items():
        d = drafts.get(key)
        scope = d.scope if d else R.TRANSCRIPTOMIC
        sid = None
        fr = routes.get(targets[0].figure)
        if fr and fr.top:
            in_scope = [skill_id(c.target) for c in fr.candidates if is_skill(c.target)]
            if in_scope:  # any in-scope skill -> stamp the top-ranked one (mixed figures stay in-scope)
                sid = in_scope[0]
            else:         # purely out-of-scope figure -> the routed scope wins over the draft's
                scope = scope_of(fr.top)
        panels.append(R.Panel(
            paper_id=spec.paper_id, figure=targets[0].figure, panel=targets[0].panel,
            chart_form=(d.chart_form if d else ""), scope=scope, skill_id=sid,
            golden=[to_golden(t) for t in targets],
        ))
    return panels
