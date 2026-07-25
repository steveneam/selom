/**
 * scRNA cohort assembly — `POST /api/data/assemble-scrna` (L2-05).
 *
 * The sibling of `combineData` (`./inspect.ts`) for single-cell. A real GEO scRNA deposit arrives as
 * a SET of per-sample 10x matrices — loose `matrix.mtx.gz` / `barcodes.tsv.gz` / `features.tsv.gz`
 * triplets, or one `.h5ad` per sample — with no per-cell design in `obs`: the design lives in the
 * FILENAMES. The backend concatenates them into one AnnData and materializes `sample_id` into `obs`;
 * this returns the assembled `.h5ad` as a File, which the caller ingests through the ordinary
 * upload → inspect → run path.
 *
 * **Why this module exists at all:** `/data/assemble-scrna` shipped working in `11a115f` with no FE
 * call site whatsoever — the example that motivated the reachability ratchet
 * (`docs/reachability/backlog.md`). A capability a user cannot reach is not shipped.
 */

/** Summary of an assembly (backend `X-Assemble-Summary` header, from `engine.assemble.summarize`). */
export interface AssembleSummary {
  filename: string;
  n_files: number;
  n_cells: number;
  n_genes: number;
  n_samples: number;
  samples: string[];
  obs_columns: string[];
  per_sample_n: Record<string, number>;
  /** D3 lineage record for the assembled cohort, when the backend materialized one. */
  artifact_id?: string;
}

export interface AssembleResult {
  /** The assembled cohort as one `.h5ad` File — ingested by the caller like any dropped file. */
  file: File;
  summary: AssembleSummary;
}

/** The 10x triplet member names the backend groups on (`engine/assemble.py::_MEMBERS`). */
const TENX_MEMBER = /(matrix\.mtx|barcodes\.tsv|features\.tsv|genes\.tsv)(\.gz)?$/i;

/**
 * Is this multi-file drop a per-sample scRNA deposit rather than an ERG cohort?
 *
 * Deliberately narrow, because the two multi-file paths are mutually exclusive and guessing wrong
 * sends a user to the wrong error message: a 10x triplet member is unmistakable, and several
 * `.h5ad` files can only be per-sample matrices. Everything else (`.iwxdata`, Diagnosys `.txt`/
 * `.csv`) falls through to the ERG combine, which is where it belongs.
 */
export function looksLikeScrnaDeposit(files: File[]): boolean {
  if (files.length < 2) return false;
  if (files.some((f) => TENX_MEMBER.test(f.name))) return true;
  return files.every((f) => /\.h5ad$/i.test(f.name));
}

/**
 * Assemble per-sample scRNA matrices into one cohort. Returns `null` on failure so the caller can
 * surface an honest message — it never falls back to a partial or synthesized cohort, because a
 * silently-dropped sample is a design change nobody consented to
 * ([[mock-fallback-never-fabricates-data]]).
 *
 * `obsMap` is the optional design overlay: `{sample key → {obs field: value}}`. Omitted here for the
 * filename-only assembly the drop-zone offers; the confirmed-intake overlay is a later slice.
 */
export async function assembleScrna(
  files: File[],
  obsMap?: Record<string, Record<string, string>>,
): Promise<AssembleResult | null> {
  if (files.length < 1) return null;
  try {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    if (obsMap) fd.append("obs_map", JSON.stringify(obsMap));
    const res = await fetch("/api/data/assemble-scrna", { method: "POST", body: fd });
    if (!res.ok) return null;
    const raw = res.headers.get("X-Assemble-Summary");
    if (!raw) return null; // no summary ⇒ we can't describe what was assembled — don't pretend
    const summary = JSON.parse(raw) as AssembleSummary;
    const blob = await res.blob();
    const name = summary.n_samples
      ? `Assembled scRNA — ${summary.n_samples} samples (${files.length} files).h5ad`
      : summary.filename || "assembled_scrna.h5ad";
    return { file: new File([blob], name, { type: "application/octet-stream" }), summary };
  } catch {
    return null;
  }
}
