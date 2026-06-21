"""Accession recognizer (Slice 5, Phase A) — find the datasets a paper *cites but does not attach*.

The Harmony/Yoshimura cold drives surfaced a meta-finding: famous methods/atlas papers deposit
**code + R objects + repository accessions**, not ingestable analysis matrices (the only attached
"data" is a QC table or an R source package). So a paper's real data lives behind a GEO/SRA/GSA/…
accession in its *Data Availability* statement — and the matcher, seeing no usable supplement,
either reports a blank ``no_golden`` or force-feeds the wrong file. This module reads the accessions
out of the text deterministically, so the diagnostic shows **honest data provenance** ("the data is
GEO: GSE213152, open & fetchable" / "controlled — requires application") instead of a mismatch.

**Phase A only (this module): recognize + classify + link.** Pure regex over ``bundle.text`` — no
network, no new dependency (deterministic URLs, never GEOparse on the shipped path). Each accession
is typed by repository and by **access class** — the load-bearing honesty:

* ``open``       — processed / analysis-ready data is reachable (GEO series, ArrayExpress, PRIDE,
  MetaboLights/Workbench, Zenodo/Figshare/Dryad). ``ingestable`` → a Phase-B fetch *could* feed the
  matcher.
* ``raw``        — raw sequencing reads only (SRA / ENA / GSA-CRA). NOT ingestable as-is: "needs
  quantification" (the parked BAM-ingest path, [[selom-bam-ingest]]).
* ``controlled`` — application-gated (dbGaP / EGA / GSA-Human HRA). NOT ingestable: "requires a
  data-access application; cannot auto-fetch" — surfaced honestly, never a silent failure.

**Phase B (fetch + ingest) is GATED and deferred** (network + size cap + cache + likely async — ASK
first, [[ask-before-docker-wsl]]). This module only points at the data; it never downloads it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# --- access classes (the honesty axis) ----------------------------------------
OPEN = "open"              # processed/analysis-ready data reachable → fetchable (Phase B)
RAW = "raw"                # raw reads only → needs quantification (parked BAM-ingest)
CONTROLLED = "controlled"  # application-gated → cannot auto-fetch

# --- where in the paper an accession was found (provenance weight) ------------
SEC_AVAILABILITY = "availability"  # inside the Data/Code-Availability statement (high confidence)
SEC_BODY = "body"                  # elsewhere in the text


class Accession(BaseModel):
    """One dataset accession recognized in the paper text (Phase A: recognize + classify + link)."""

    repo: str                       # geo | sra | ena | arrayexpress | gsa | pride | metabolights |
    #                                 metabolomics_workbench | zenodo | figshare | dryad | dbgap | ega
    id: str                         # GSE213152 · PRJNA… · PXD… · 10.5281/zenodo.123 …
    access: str                     # open | raw | controlled
    ingestable: bool                # could a (gated) Phase-B fetch feed the matcher with this?
    url: str                        # deterministic landing/record URL (no network used to build it)
    label: str = ""                 # human repository name ("Gene Expression Omnibus")
    section: str = SEC_BODY         # availability | body
    note: str = ""                  # honest guidance, esp. for raw/controlled


# --- repository registry ------------------------------------------------------
# Each entry: (compiled pattern, repo, label, access, ingestable, url-builder, honest note).
# Patterns are deliberately specific (anchored prefixes + digit-length floors) so they do not fire
# on prose. The two real precision traps the calibration papers exposed are handled here:
#   • citation markers — "GEO: GSE213152 (77)" — the pattern anchors on the ID, ignoring "(77)".
#   • supplementary-table refs — "Table ST6", "ST2" — Metabolomics-Workbench study IDs are ST + 6
#     digits (ST000123), so requiring ``\d{6,}`` separates a real study from a table label.
_RAW_NOTE = "raw sequencing reads — needs quantification before analysis (parked: BAM ingest)"
_CTRL_NOTE = "controlled access — requires a data-access application; cannot auto-fetch"


def _u(fmt):
    return lambda m: fmt.format(id=m)


_REGISTRY: list[tuple[re.Pattern, str, str, str, bool, object, str]] = [
    # GEO (NCBI) — series/sample = processed-friendly; platform = annotation, not data.
    (re.compile(r"\bGSE\d{3,}\b"), "geo", "Gene Expression Omnibus", OPEN, True,
     _u("https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}"), ""),
    (re.compile(r"\bGSM\d{3,}\b"), "geo", "Gene Expression Omnibus (sample)", OPEN, True,
     _u("https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}"), ""),
    (re.compile(r"\bGPL\d{3,}\b"), "geo", "Gene Expression Omnibus (platform)", OPEN, False,
     _u("https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}"),
     "platform annotation, not a dataset"),
    # SRA (NCBI) — raw reads.
    (re.compile(r"\bPRJNA\d{3,}\b"), "sra", "NCBI BioProject", RAW, False,
     _u("https://www.ncbi.nlm.nih.gov/bioproject/?term={id}"), _RAW_NOTE),
    (re.compile(r"\bSRP\d{3,}\b"), "sra", "Sequence Read Archive", RAW, False,
     _u("https://www.ncbi.nlm.nih.gov/sra/?term={id}"), _RAW_NOTE),
    (re.compile(r"\bSRR\d{3,}\b"), "sra", "Sequence Read Archive (run)", RAW, False,
     _u("https://www.ncbi.nlm.nih.gov/sra/?term={id}"), _RAW_NOTE),
    # ENA (EBI) — raw reads.
    (re.compile(r"\bPRJEB\d{3,}\b"), "ena", "European Nucleotide Archive", RAW, False,
     _u("https://www.ebi.ac.uk/ena/browser/view/{id}"), _RAW_NOTE),
    (re.compile(r"\b(?:ERP|ERR|ERS)\d{3,}\b"), "ena", "European Nucleotide Archive", RAW, False,
     _u("https://www.ebi.ac.uk/ena/browser/view/{id}"), _RAW_NOTE),
    # ArrayExpress / BioStudies (EBI) — processed-friendly. Uppercase letters only (E-MTAB / E-GEOD
    # / E-PROT), so a hyphenated word like "E-mail-2" never matches.
    (re.compile(r"\bE-[A-Z]{4}-\d+\b"), "arrayexpress", "ArrayExpress", OPEN, True,
     _u("https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{id}"), ""),
    # GSA (NGDC / CNCB) — CRA/PRJCA = raw; HRA = human, controlled.
    (re.compile(r"\bHRA\d{3,}\b"), "gsa", "Genome Sequence Archive for Human", CONTROLLED, False,
     _u("https://ngdc.cncb.ac.cn/gsa-human/browse/{id}"), _CTRL_NOTE),
    (re.compile(r"\bCRA\d{3,}\b"), "gsa", "Genome Sequence Archive", RAW, False,
     _u("https://ngdc.cncb.ac.cn/gsa/browse/{id}"), _RAW_NOTE),
    (re.compile(r"\bPRJCA\d{3,}\b"), "gsa", "BioProject (NGDC)", RAW, False,
     _u("https://ngdc.cncb.ac.cn/bioproject/browse/{id}"), _RAW_NOTE),
    # PRIDE (EBI) — proteomics; processed result files usually deposited.
    (re.compile(r"\bPXD\d{3,}\b"), "pride", "PRIDE", OPEN, True,
     _u("https://www.ebi.ac.uk/pride/archive/projects/{id}"), ""),
    # MetaboLights (EBI) + Metabolomics Workbench (study ST + >=6 digits — not a table ref).
    (re.compile(r"\bMTBLS\d{2,}\b"), "metabolights", "MetaboLights", OPEN, True,
     _u("https://www.ebi.ac.uk/metabolights/{id}"), ""),
    (re.compile(r"\bST\d{6,}\b"), "metabolomics_workbench", "Metabolomics Workbench", OPEN, True,
     _u("https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID={id}"), ""),
    # Generalist repositories (DOIs) — processed/analysis artifacts.
    (re.compile(r"\b10\.5281/zenodo\.\d+\b", re.I), "zenodo", "Zenodo", OPEN, True,
     _u("https://doi.org/{id}"), ""),
    (re.compile(r"\b10\.6084/m9\.figshare\.\d+(?:\.v\d+)?\b", re.I), "figshare", "figshare", OPEN,
     True, _u("https://doi.org/{id}"), ""),
    (re.compile(r"\b10\.5061/dryad\.\w+\b", re.I), "dryad", "Dryad", OPEN, True,
     _u("https://doi.org/{id}"), ""),
    # Controlled-access human repositories.
    (re.compile(r"\bphs\d{6}(?:\.v\d+\.p\d+)?\b"), "dbgap", "dbGaP", CONTROLLED, False,
     _u("https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={id}"), _CTRL_NOTE),
    (re.compile(r"\bEGA[SD]\d{6,}\b"), "ega", "European Genome-phenome Archive", CONTROLLED, False,
     _u("https://ega-archive.org/datasets/{id}"), _CTRL_NOTE),
]

# Headers that open a Data/Code-Availability statement (weight accessions found inside it).
_AVAIL_HEADER_RE = re.compile(
    r"(data,?\s+materials,?\s+and\s+software\s+availability"
    r"|data\s+(?:and\s+(?:code|materials)\s+)?availability"
    r"|code\s+availability"
    r"|availability\s+of\s+(?:the\s+)?data"
    r"|accession\s+(?:number|code)s?"
    r"|data\s+access(?:ibility)?\s+statement)", re.I)
_AVAIL_WINDOW = 1500  # chars after a header treated as the availability statement (statements run short)


def availability_spans(text: str) -> list[tuple[int, int]]:
    """The character ranges that make up the paper's Data/Code-Availability statement(s).

    Used only to *weight* a found accession (``section`` = availability vs body) — recognition
    scans the whole text either way (the patterns are specific enough), so a paper with an
    unconventional header still has its accessions recognized, just tagged ``body``."""
    return [(m.start(), min(len(text), m.start() + _AVAIL_WINDOW))
            for m in _AVAIL_HEADER_RE.finditer(text)]


def _in_availability(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(lo <= pos < hi for lo, hi in spans)


def find_accessions(text: str) -> list[Accession]:
    """Recognize + classify every dataset accession in the paper text (Phase A, deterministic).

    Deduped by ``(repo, id)``; an accession found inside the availability statement wins over a
    body mention of the same id. Order: availability-statement accessions first (most actionable),
    then body, each group in first-appearance order. No network, no dependency — Phase B (fetch)
    is gated and deferred."""
    if not text:
        return []
    spans = availability_spans(text)
    best: dict[tuple[str, str], tuple[int, Accession]] = {}
    for pattern, repo, label, access, ingestable, url_fn, note in _REGISTRY:
        for m in pattern.finditer(text):
            acc_id = m.group(0)
            in_avail = _in_availability(m.start(), spans)
            key = (repo, acc_id)
            prev = best.get(key)
            # keep the availability-section hit over a plain body hit (or the earliest otherwise).
            if prev is not None and not (in_avail and prev[1].section == SEC_BODY):
                continue
            best[key] = (m.start(), Accession(
                repo=repo, id=acc_id, access=access, ingestable=ingestable, url=url_fn(acc_id),
                label=label, section=SEC_AVAILABILITY if in_avail else SEC_BODY, note=note))
    rows = [v for _, v in sorted(best.values(), key=lambda t: t[0])]
    rows.sort(key=lambda a: a.section != SEC_AVAILABILITY)  # availability first (stable)
    return rows


class AccessionReport(BaseModel):
    """Roll-up of a paper's cited datasets — the data-provenance half of the gap report (Slice 5)."""

    accessions: list[Accession] = Field(default_factory=list)

    @property
    def n_open_ingestable(self) -> int:
        return sum(1 for a in self.accessions if a.ingestable)

    @property
    def has_data(self) -> bool:
        return bool(self.accessions)

    def summary_line(self) -> str:
        """One honest sentence on what data the paper points at (for the diagnostic header)."""
        if not self.accessions:
            return "no dataset accession recognized in the paper text"
        by_access: dict[str, int] = {}
        for a in self.accessions:
            by_access[a.access] = by_access.get(a.access, 0) + 1
        parts = ", ".join(f"{n} {k}" for k, n in sorted(by_access.items()))
        fetch = self.n_open_ingestable
        tail = f"; {fetch} fetchable (Phase B, gated)" if fetch else "; none auto-fetchable"
        return f"{len(self.accessions)} accession(s) — {parts}{tail}"


def report(text: str) -> AccessionReport:
    """The paper's accession roll-up (recognize → classify → link), ready to surface in the gap
    report and Product A's data-check."""
    return AccessionReport(accessions=find_accessions(text))
