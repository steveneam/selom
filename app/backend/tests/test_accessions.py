"""Accession recognizer (extract/accessions.py, Slice 5 Phase A) — recognize + classify + link.

Tested over the REAL availability-statement phrasings the calibration papers use (Yoshimura's GEO
statement with its citation-marker trap; the supplementary-table "ST" trap; raw/controlled honesty),
not hopeful mocks — so the regexes are pinned to what real papers print. No network is touched.
"""

from __future__ import annotations

from extract.accessions import (
    CONTROLLED,
    OPEN,
    RAW,
    SEC_AVAILABILITY,
    SEC_BODY,
    find_accessions,
    report,
)

# The verbatim Yoshimura (Wu/Little 2023) availability statement, citation markers and all.
YOSHIMURA = (
    "Data, Materials, and Software Availability. The accession number for sn-multiome and CUT&RUN "
    "sequencing datasets in this paper is GEO: GSE213152 (77), and that for bulk ATAC-seq dataset "
    "is GEO: GSE227061 (78). Previously published sn-multiome data for human adult kidneys are "
    "available in GEO: GSE151302 (79)."
)


def _by_id(text):
    return {a.id: a for a in find_accessions(text)}


def test_yoshimura_real_statement_recovers_three_geo_accessions():
    accs = find_accessions(YOSHIMURA)
    ids = [a.id for a in accs]
    assert ids == ["GSE213152", "GSE227061", "GSE151302"]   # the (77)/(78)/(79) markers are ignored
    for a in accs:
        assert a.repo == "geo" and a.access == OPEN and a.ingestable
        assert a.section == SEC_AVAILABILITY
        assert a.url == f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={a.id}"


def test_dedup_repeated_accession_collapses_to_one():
    # GSE213152 also appears in a URL later in the same paper — still one accession.
    text = YOSHIMURA + " See https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE213152 ."
    assert [a.id for a in find_accessions(text)].count("GSE213152") == 1


def test_raw_reads_are_classified_needs_quantification():
    text = ("Data Availability. Raw sequencing reads are deposited in the Sequence Read Archive "
            "under BioProject PRJNA734567 (run SRR12345678).")
    accs = _by_id(text)
    assert accs["PRJNA734567"].access == RAW and not accs["PRJNA734567"].ingestable
    assert "quantification" in accs["PRJNA734567"].note
    assert accs["SRR12345678"].repo == "sra" and accs["SRR12345678"].access == RAW


def test_controlled_access_is_flagged_cannot_autofetch():
    text = ("Data Availability. Individual-level data are available through dbGaP (phs001234.v1.p1) "
            "and the Genome Sequence Archive for Human under accession HRA000762.")
    accs = _by_id(text)
    assert accs["phs001234.v1.p1"].repo == "dbgap" and accs["phs001234.v1.p1"].access == CONTROLLED
    assert not accs["phs001234.v1.p1"].ingestable and "application" in accs["phs001234.v1.p1"].note
    assert accs["HRA000762"].repo == "gsa" and accs["HRA000762"].access == CONTROLLED


def test_supplementary_table_ST_refs_do_not_become_metabolomics_studies():
    # The real precision trap: "Table ST6 / ST2" are supplementary tables (JEV/RPGRIP1 ledgers),
    # NOT Metabolomics Workbench studies (those are ST + 6 digits, e.g. ST000123).
    table_refs = "Marker genes are listed in Table ST6 and Table ST2 (see also ST10)."
    assert find_accessions(table_refs) == []
    real_mw = "Metabolomics data are available at the Metabolomics Workbench (Study ST000123)."
    accs = _by_id(real_mw)
    assert accs["ST000123"].repo == "metabolomics_workbench" and accs["ST000123"].access == OPEN


def test_zenodo_and_figshare_dois_link_to_processed_artifacts():
    text = ("Code and processed data are deposited at Zenodo (https://doi.org/10.5281/zenodo.7654321) "
            "and figshare (10.6084/m9.figshare.19123456).")
    accs = _by_id(text)
    z = accs["10.5281/zenodo.7654321"]
    assert z.repo == "zenodo" and z.access == OPEN and z.ingestable
    assert z.url == "https://doi.org/10.5281/zenodo.7654321"
    assert accs["10.6084/m9.figshare.19123456"].repo == "figshare"


def test_arrayexpress_and_ena_recognized():
    text = ("Microarray data are in ArrayExpress (E-MTAB-9876); raw reads are in the European "
            "Nucleotide Archive under PRJEB45678.")
    accs = _by_id(text)
    assert accs["E-MTAB-9876"].repo == "arrayexpress" and accs["E-MTAB-9876"].access == OPEN
    assert accs["PRJEB45678"].repo == "ena" and accs["PRJEB45678"].access == RAW


def test_section_weighting_availability_beats_body():
    # The same id in the body and in the availability statement is tagged from the statement.
    text = ("We re-analyzed GSE151302 in Figure 3. ... Data Availability. The data are in "
            "GEO: GSE151302.")
    a = _by_id(text)["GSE151302"]
    assert a.section == SEC_AVAILABILITY  # availability hit wins over the earlier body mention


def test_body_only_accession_is_tagged_body():
    a = _by_id("We compared against the reference atlas GSE151302 throughout.")["GSE151302"]
    assert a.section == SEC_BODY


def test_report_summary_line_is_honest():
    rep = report(YOSHIMURA)
    assert rep.has_data and rep.n_open_ingestable == 3
    line = rep.summary_line()
    assert "3 accession" in line and "fetchable" in line
    assert report("no data here").summary_line() == "no dataset accession recognized in the paper text"


# --- Slice 5B: the per-repo download handoff (which file to grab, and how) ----


def test_open_geo_download_hint_names_the_processed_matrix():
    # The single useful sentence for someone staring at a GEO page: grab the processed matrix.
    a = _by_id(YOSHIMURA)["GSE213152"]
    assert a.download_hint and "Supplementary file" in a.download_hint
    assert "matrix" in a.download_hint.lower() and "raw reads" in a.download_hint.lower()


def test_raw_download_hint_is_honest_not_a_handoff():
    # A raw-reads accession must NOT send the user chasing a file Selom can't ingest.
    a = _by_id("Data Availability. Raw reads are in SRA under PRJNA734567.")["PRJNA734567"]
    assert "not directly usable" in a.download_hint and "quantif" in a.download_hint


def test_controlled_download_hint_says_apply():
    a = _by_id("Data Availability. Data are in dbGaP (phs001234.v1.p1).")["phs001234.v1.p1"]
    assert "apply" in a.download_hint.lower() and "can't be downloaded" in a.download_hint


def test_geo_platform_download_hint_is_not_data():
    # GPL is a platform annotation record, not a dataset → no file to attach.
    a = _by_id("We used the Illumina platform GPL24676 for sequencing.")["GPL24676"]
    assert not a.ingestable and "not a dataset" in a.download_hint


def test_zenodo_and_pride_download_hints_are_repo_specific():
    accs = _by_id("Data are at Zenodo (10.5281/zenodo.7654321) and PRIDE (PXD012345).")
    assert ".xlsx" in accs["10.5281/zenodo.7654321"].download_hint.lower() \
        or ".csv" in accs["10.5281/zenodo.7654321"].download_hint.lower()
    assert "quantification" in accs["PXD012345"].download_hint and "*.raw" in accs["PXD012345"].download_hint
