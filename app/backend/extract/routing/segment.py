"""Section segmentation — the highest-leverage extractor upgrade (spec §Design).

Split PDF text into ``methods | results | legends | refs | body`` so the matcher can weight
methods > legends > results > body and, crucially, **exclude References** — a tool named only in
the bibliography ("Korsunsky et al. Harmony…") is not evidence the paper used it. Pure regex,
offline, no model. Figure-legend blocks are split per ``Fig N`` so routing hits attach to a
specific figure (per-figure granularity, owner-resolved).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# A header line: a short line that is (optionally numbered) one of the known section names.
# Order matters — the most specific names first so "Materials and Methods" wins over "Methods".
_HEADERS = (
    ("methods", r"materials?\s+and\s+methods|star\s*\*?\s*methods|online\s+methods|"
                r"experimental\s+procedures|methods(?:\s+summary)?"),
    ("refs", r"references|bibliography|literature\s+cited"),
    ("legends", r"figure\s+legends|figure\s+captions|extended\s+data\s+figure\s+legends"),
    ("results", r"results(?:\s+and\s+discussion)?"),
)
_HEADER_RE = re.compile(
    r"^\s*(?:\d+\s*[.)]?\s*)?(?:" + "|".join(f"(?P<{name}>{pat})" for name, pat in _HEADERS) + r")\s*:?\s*$",
    re.I,
)
_PAGE_MARKER = re.compile(r"=+\s*PAGE\s+\d+\s*=+", re.I)

# A figure-caption start: "Fig. 1 | …", "Figure 2. …", "Fig 3: …" at a line/segment start.
_FIG_CAPTION = re.compile(r"(?:^|\n)\s*Fig(?:ure)?\.?\s*(\d+)\s*[.:|)]\s*", re.I)


class SectionedText(BaseModel):
    """A paper split into routing sections. ``legends`` is keyed by figure number → caption text;
    ``refs`` is captured for completeness but never matched (the false-positive guard)."""

    methods: str = ""
    results: str = ""
    refs: str = ""
    body: str = ""
    legends: dict[str, str] = Field(default_factory=dict)


def _header(line: str) -> str | None:
    """The section a header line opens, or ``None``. Bounded length so a sentence that merely
    contains 'methods' isn't misread as the Methods header."""
    if len(line) > 60:
        return None
    m = _HEADER_RE.match(line)
    if not m:
        return None
    return next(name for name, val in m.groupdict().items() if val)


def split_legends(text: str) -> dict[str, str]:
    """Split a figure-legends block into ``{figure_number: caption_text}``. Consecutive captions
    for the same figure are concatenated; the text runs until the next caption."""
    marks = list(_FIG_CAPTION.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        fig = m.group(1)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        out[fig] = (out[fig] + " " + body).strip() if fig in out else body
    return out


def segment(text: str) -> SectionedText:
    """Segment a paper's text. Lines before any recognised header are ``body`` (abstract/intro);
    once ``References`` opens, everything after it is ``refs`` (and excluded from matching).

    Legends come from an explicit "Figure legends" section when present; otherwise the whole
    document is scanned for caption-shaped blocks (best-effort — Nature-style papers often inline
    their legends). When no clean legends are found, per-figure routing falls back to the
    figure references inside the Results text (handled in ``route``)."""
    text = _PAGE_MARKER.sub("\n", text)
    buckets: dict[str, list[str]] = {"methods": [], "results": [], "refs": [], "body": [], "legends": []}
    cur = "body"
    for line in text.split("\n"):
        h = _header(line.strip())
        if h:
            cur = h
            continue
        buckets[cur].append(line)
    legends_raw = "\n".join(buckets["legends"]).strip()
    legends = split_legends(legends_raw) if legends_raw else split_legends(text)
    return SectionedText(
        methods="\n".join(buckets["methods"]).strip(),
        results="\n".join(buckets["results"]).strip(),
        refs="\n".join(buckets["refs"]).strip(),
        body="\n".join(buckets["body"]).strip(),
        legends=legends,
    )
