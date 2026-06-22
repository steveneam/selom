/**
 * Cited-dataset accessions (Slice 5B — the deposit-data handoff). Famous papers deposit their data
 * behind a repository accession (GEO / SRA / Zenodo / …) and attach only a QC table, so the panels
 * that need the real matrix classify `data_unmatched`. The backend recognizes those accessions off
 * the paper text (no fetch) and rides them on the run contract; this is the wire shape + the per-
 * access-class display vocabulary the Score stage uses to hand the user a link + download
 * instructions, then back to the per-panel picker. Mirrors `extract.accessions.Accession`.
 */

export type AccessClass = "open" | "raw" | "controlled";

/** One dataset the paper cites but did not attach. */
export interface Accession {
  repo: string;
  id: string;
  access: AccessClass;
  ingestable: boolean; // could this become a file you drop into the picker?
  url: string; // the repository record/landing page (built deterministically; no fetch)
  label: string; // human repository name ("Gene Expression Omnibus")
  section: string; // "availability" | "body" — where in the paper it was found
  note: string;
  download_hint: string; // "which file to grab, and how" — honest for raw/controlled
}

/** Per-access-class display metadata — one source for the badge label/tone across the surface. */
export const ACCESS_META: Record<
  AccessClass,
  { label: string; color: string; short: string }
> = {
  open: { label: "Open", color: "#10b981", short: "publicly downloadable" },
  raw: { label: "Raw reads", color: "#f59e0b", short: "needs quantification first" },
  controlled: { label: "Controlled", color: "#ef4444", short: "application required" },
};

/** A small rollup for the section lead-in (how much of the cited data is actually fetchable). */
export function accessionSummary(accessions: Accession[]): {
  total: number;
  ingestable: number;
} {
  return {
    total: accessions.length,
    ingestable: accessions.filter((a) => a.ingestable).length,
  };
}
