"""Section segmentation — the highest-leverage extractor upgrade (spec §Design + legend-hardening).

Split PDF text into ``methods | results | refs | body`` + per-figure ``legends`` so the matcher can
weight methods > legends > results > body and, crucially, **exclude References** — a tool named only
in the bibliography ("Korsunsky et al. Harmony…") is not evidence the paper used it. Pure regex,
offline, no model.

Real-PDF hardening (session 33, ``legend-hardening-scope.md``): figure captions in extracted PDF
text are messy — the marker often reflows to a letter-spaced ``F IG U R E `` line with the figure
**number stripped off**, inline between Results paragraphs, and the bibliography arrives with **no
``References`` header**. So caption detection de-spaces the marker, bounds each caption block, strips
running-head/footer cruft, and recovers the figure number **ordinally** from the in-text figure
references (owner-resolved H1); a header-less citation-dense tail is detected heuristically and
excluded.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# A header line: a short line that is (optionally numbered) one of the known section names.
# Order matters — the most specific names first so "Materials and Methods" wins over "Methods".
# Discussion/Introduction/Abstract/Acknowledgements/Supporting Information route to ``body`` (low
# weight) so their prose never carries results weight (legend-hardening Fix B).
_HEADERS = (
    ("methods", r"materials?\s+and\s+methods|star\s*\*?\s*methods|online\s+methods|"
                r"experimental\s+procedures|methods(?:\s+summary)?"),
    ("refs", r"references|bibliography|literature\s+cited"),
    ("body", r"discussion(?:\s+and\s+conclusions?)?|introduction|abstract|acknowledge?ments?|"
             r"supporting\s+information|supplementary\s+information"),
    ("results", r"results(?:\s+and\s+discussion)?"),
)
_HEADER_RE = re.compile(
    r"^\s*(?:\d+\s*[.)]?\s*)?(?:" + "|".join(f"(?P<{name}>{pat})" for name, pat in _HEADERS) + r")\s*:?\s*$",
    re.I,
)
_PAGE_MARKER = re.compile(r"=+\s*PAGE\s+\d+\s*=+", re.I)

# In-text figure reference: "Figure 1a", "Fig. 3c)", "Fig 4". A leading letter is forbidden so we
# don't match mid-word; ``Figure S1`` yields no match (no digit follows the marker) — supplementary
# figures are excluded from the main-figure pool automatically.
_INTEXT_FIG = re.compile(r"(?<![A-Za-z])Fig(?:ure|\.)?\s*(\d+)", re.I)

# A figure-caption marker on its own line. Journals vary the separator widely — "Figure 4 |"
# (Nature), "Fig. 2." (Cell), "Figure 1:" / "FIGURE 1 —" (Wiley/em-dash) — so the punctuation class
# spans ``. : | ) — – -``. ``_INLINE`` carries a number + any same-line caption text; ``_BARE`` is the
# de-spaced marker token (number optional) for the garbled letter-spaced "F IG U R E " reflow.
_SEP = r"[.:|)—–-]"
_MARKER_INLINE = re.compile(rf"^fig(?:ure)?\.?\s*(\d+)\s*{_SEP}\s*(.*)$", re.I)
# Bare marker, de-spaced. A trailing ``\W*`` absorbs an unmappable figure-number glyph: some journals
# render the number in a custom font whose digits extract as private-use-area codepoints (e.g.
# "F IG U R E <U+F6DC>") — non-word junk we can't decode, so the number is recovered ordinally (H1).
_MARKER_BARE = re.compile(rf"^fig(?:ure|\.)?(\d+)?{_SEP}?\W*$", re.I)
# Inline caption whose figure number renders as a Private-Use-Area font glyph, with the caption text
# on the SAME (long) line: "FIGURE <U+F6DC> Müller glia… (a)…". This is the Wiley/JEV production form
# that ``_MARKER_INLINE`` misses (no real ``\d`` after the marker) and the long-line guard rejects —
# the number is undecodable from the glyph, so it is recovered ordinally like the bare form.
_PUA = f"[{chr(0xE000)}-{chr(0xF8FF)}]"  # Unicode Private Use Area (custom-font figure digits)
_MARKER_GLYPH = re.compile(rf"^fig(?:ure)?\.?\s+{_PUA}+\s+(.*)$", re.I)
# A leading manuscript / preprint line-number ("305 Fig. 1. …" in bioRxiv submissions) breaks the
# ^figure anchor; stripped LOCALLY (marker-matching only, not a whole-document rewrite) so a
# line-numbered preprint's otherwise-clean captions are still detected.
_LINENO = re.compile(r"^\d{1,4}\s+")

# sub-panel marker "(a)" / "(A)" — the strongest "this is a caption" signal.
_SUBPANEL = re.compile(r"\([a-z]\)", re.I)

# a reference-LIST entry (not an inline citation): a year in its own parens followed by a period,
# or a DOI tail. Inline cites like "(Smith et al., 2021)" lack the "(YYYY)." shape, so the Discussion
# never trips the detector (legend-hardening Fix B / decision H4).
_REF_LINE = re.compile(r"\(\d{4}[a-z]?\)\.|https?://(?:dx\.)?doi\.org|\bdoi:\s*10\.", re.I)

# running-head / footer cruft that interleaves caption blocks after extraction.
_RUNNING_HEAD = re.compile(r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+)*\s+et\s+al\.?$")

_CAP_MAX_LINES = 14  # a caption is a short paragraph; bound the block so it can't swallow prose.
_REFS_MIN_LINES = 10  # require a clearly citation-dense tail before excluding it.
_REFS_GAP = 8         # max line distance between consecutive citation lines still counted as ONE
                      # bibliography (absorbs wrapped author lists); a larger jump separates a stray
                      # in-text citation from the trailing reference cluster.


class SectionedText(BaseModel):
    """A paper split into routing sections. ``legends`` is keyed by figure number → caption text;
    ``refs`` is captured for completeness but never matched (the false-positive guard)."""

    methods: str = ""
    results: str = ""
    refs: str = ""
    body: str = ""
    legends: dict[str, str] = Field(default_factory=dict)
    # per-figure caption provenance: "structured" (clean numbered marker, L1) or "recovered"
    # (garbled/bare marker + ordinal number recovery, L2).
    legend_tiers: dict[str, str] = Field(default_factory=dict)


def _header(line: str) -> str | None:
    """The section a header line opens, or ``None``. Bounded length so a sentence that merely
    contains 'methods' isn't misread as the Methods header."""
    if len(line) > 60:
        return None
    m = _HEADER_RE.match(line)
    if not m:
        return None
    return next(name for name, val in m.groupdict().items() if val)


def _intext_main_figs(text: str) -> list[int]:
    """Main (non-supplementary) figure numbers referenced anywhere in the text, sorted ascending —
    the ordinal pool for recovering stripped caption numbers (decision H1)."""
    return sorted({int(m.group(1)) for m in _INTEXT_FIG.finditer(text)})


def _despace(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _marker(line: str) -> tuple[bool, str | None, str]:
    """Classify a line as a figure-caption marker. Returns ``(is_marker, number|None, inline_text)``.
    Handles four real-PDF caption forms: the clean inline ("Figure 1. <caption…>", which may be a
    long line — its ``Fig N <sep>`` structure is the guard); the inline custom-font-glyph form
    ("FIGURE <U+F6DC> <caption…>", number recovered ordinally); a line-numbered manuscript prefix
    ("305 Fig. 1. …", stripped locally before matching); and the garbled bare form (a letter-spaced
    "F IG U R E " with the number reflowed away, which must be a SHORT line so a sentence containing
    'figure' can't masquerade as one)."""
    s = line.strip()
    if not s:
        return (False, None, "")
    # L2 recovery: a manuscript / preprint line-number prefix ("305 Fig. 1. …") breaks the ^figure
    # anchor — try the de-numbered candidate first, then the raw line.
    s2 = _LINENO.sub("", s, count=1)
    for cand in ((s2, s) if s2 != s else (s,)):
        m = _MARKER_INLINE.match(cand)
        if m:
            return (True, m.group(1), m.group(2).strip())
        g = _MARKER_GLYPH.match(cand)  # "FIGURE <glyph> <caption inline>" — number recovered ordinally
        if g and _looks_like_caption(g.group(1)):
            return (True, None, g.group(1).strip())
    if len(s) > 40:
        return (False, None, "")
    m2 = _MARKER_BARE.match(_despace(s))  # "F IG U R E" -> "FIGURE"
    if m2:
        return (True, m2.group(1), "")
    return (False, None, "")


def _is_cruft(line: str) -> bool:
    """Interleaved header/footer noise inside a caption block (blank lines, bare page numbers,
    a running head like 'CIOANCA et al.')."""
    s = line.strip()
    if len(s) <= 3:  # blank, page numbers, stray "of"
        return True
    return bool(_RUNNING_HEAD.match(s))


def _looks_like_caption(body: str) -> bool:
    """A caption gate: a sub-panel run, or a title-length sentence — not a stray 'FIGURE' token."""
    return bool(_SUBPANEL.search(body)) or len(body) >= 12


def _assign_numbers(
    blocks: list[tuple[str | None, str]], pool: list[int]
) -> tuple[dict[str, str], dict[str, str]]:
    """Map caption blocks → ``(legends, tiers)``. Explicit-numbered blocks win and are ``structured``;
    numberless blocks take the next in-text main-figure number in document order (ordinal recovery,
    H1) and are ``recovered``, falling back to a plain 1..N ordinal when the in-text pool is too small."""
    explicit = {int(n) for (n, _) in blocks if n}
    n_missing = sum(1 for (n, _) in blocks if not n)
    avail = [n for n in pool if n not in explicit]
    if len(avail) < n_missing:
        gen = (i for i in range(1, len(blocks) + len(explicit) + 1) if i not in explicit)
        avail = [next(gen) for _ in range(n_missing)]
    out: dict[str, str] = {}
    tiers: dict[str, str] = {}
    ai = 0
    for num, body in blocks:
        if num:
            fig, tier = num, "structured"
        else:
            fig, tier = str(avail[ai]), "recovered"
            ai += 1
        out[fig] = (out[fig] + " " + body).strip() if fig in out else body
        if tiers.get(fig) != "structured":  # a structured block wins the tier for a shared figure
            tiers[fig] = tier
    return out, tiers


def _extract_captions(
    lines: list[str], pool: list[int]
) -> tuple[set[int], dict[str, str], dict[str, str]]:
    """Find caption blocks anywhere in the document; return ``(caption_lines, legends, legend_tiers)``.
    Caption lines are excised from the section buckets so their terms are matched **only** as legends
    (no double-counting). Each block runs from its marker to the next marker, bounded to
    ``_CAP_MAX_LINES`` and stopped at any section header so it can't swallow prose.

    Layering (L1/L2 gate): clean **numbered** markers are the structured layer and are always kept;
    bare / garbled / glyph-numbered markers are the recovery sweep and are only accepted when the
    numbered set is insufficient to cover the in-text figures — so a well-structured paper never pays
    the recovery layer's precision cost."""
    marks = [(i, num, rem) for i, ln in enumerate(lines) for (is_m, num, rem) in [_marker(ln)] if is_m]
    if not marks:
        return set(), {}, {}
    use_recovery = sum(1 for _, num, _ in marks if num) < max(1, len(pool))
    raw: list[tuple[str | None, str, set[int]]] = []
    for j, (li, num, rem) in enumerate(marks):
        hard_end = marks[j + 1][0] if j + 1 < len(marks) else len(lines)
        end = min(hard_end, li + 1 + _CAP_MAX_LINES)
        parts: list[str] = [rem] if rem else []
        used: set[int] = {li}
        for k in range(li + 1, end):
            if _header(lines[k].strip()):  # never cross a section header
                break
            used.add(k)
            if _is_cruft(lines[k]):
                continue
            parts.append(lines[k])
        raw.append((num, re.sub(r"\s+", " ", " ".join(parts)).strip(), used))
    blocks = [(n, b, u) for (n, b, u) in raw if _looks_like_caption(b) and (n or use_recovery)]
    if not blocks:
        return set(), {}, {}
    legends, tiers = _assign_numbers([(n, b) for (n, b, _) in blocks], pool)
    cap_lines: set[int] = set().union(*(u for (_, _, u) in blocks))
    return cap_lines, legends, tiers


def _refs_start(lines: list[str]) -> int | None:
    """The first line of a header-less trailing reference list, or ``None``. Reference-LIST lines
    (a year in its own parens, or a DOI) essentially never occur outside the bibliography, so this
    finds the **final contiguous cluster** of them — absorbing internal wrap-gaps up to ``_REFS_GAP``
    lines, and ignoring a far-away stray in-text citation. Conservative (H4): requires ≥
    ``_REFS_MIN_LINES`` reference lines in the cluster and the cluster to start in the back of the
    document, so a methods/results paragraph that cites a few works never trips it."""
    n = len(lines)
    ref_idx = [i for i, ln in enumerate(lines) if _REF_LINE.search(ln)]
    if len(ref_idx) < _REFS_MIN_LINES:
        return None
    start = ref_idx[0]
    for a, b in zip(ref_idx, ref_idx[1:]):
        if b - a > _REFS_GAP:  # a non-citation stretch separates an earlier stray from the bibliography
            start = b
    cluster = sum(1 for i in ref_idx if i >= start)
    return start if (cluster >= _REFS_MIN_LINES and start > n * 0.4) else None


def segment(text: str) -> SectionedText:
    """Segment a paper's text into ``methods | results | refs | body`` + per-figure ``legends``.

    Caption blocks are detected globally (so garbled inline legends are caught) and excised from the
    other buckets. A header-less reference tail is detected heuristically and excluded. Lines before
    any recognised header are ``body`` (abstract/intro)."""
    text = _PAGE_MARKER.sub("\n", text)
    lines = text.split("\n")
    cap_lines, legends, legend_tiers = _extract_captions(lines, _intext_main_figs(text))
    # L1 refs = an explicit header; L2 refs = a header-less citation-dense tail (only when no header).
    has_refs_header = any(_header(ln.strip()) == "refs" for ln in lines)
    refs_start = None if has_refs_header else _refs_start(lines)

    buckets: dict[str, list[str]] = {"methods": [], "results": [], "refs": [], "body": []}
    cur = "body"
    for i, line in enumerate(lines):
        if refs_start is not None and i >= refs_start:
            buckets["refs"].append(line)
            continue
        h = _header(line.strip())
        if h:
            cur = h
            continue
        if i in cap_lines:  # caption text is matched only via legends (no double-counting)
            continue
        buckets[cur].append(line)
    return SectionedText(
        methods="\n".join(buckets["methods"]).strip(),
        results="\n".join(buckets["results"]).strip(),
        refs="\n".join(buckets["refs"]).strip(),
        body="\n".join(buckets["body"]).strip(),
        legends=legends,
        legend_tiers=legend_tiers,
    )
