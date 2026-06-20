/**
 * Pure helpers for the Reproduction supplementary-materials intake (umbrella §10 stage 2).
 *
 * Kind inference mirrors the backend ingest contract one-for-one
 * (app/backend/extract/ingest.py `_SUFFIX_KIND`): the file suffix designates whether a supplement
 * is an extended-methods PDF or a supplementary *table* (xlsx / xls / xlsm → "xlsx", csv → "csv").
 * No bytes are read here — only the filename — so this stays a trivially testable, offline unit.
 */

import type { SupplementKind } from "./types";

/** Suffix → kind, matching the backend's accepted supplement formats. */
const SUFFIX_KIND: Record<string, SupplementKind> = {
  pdf: "pdf",
  xlsx: "xlsx",
  xls: "xlsx",
  xlsm: "xlsx",
  csv: "csv",
};

/** The `accept` attribute for the dropzone — the formats the backend ingest contract handles. */
export const SUPPLEMENT_ACCEPT =
  ".pdf,.xlsx,.xls,.xlsm,.csv,application/pdf,text/csv," +
  "application/vnd.ms-excel," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** Infer a supplement's kind from its filename, or `null` if the suffix isn't a supported format. */
export function supplementKind(filename: string): SupplementKind | null {
  const dot = filename.lastIndexOf(".");
  if (dot < 0 || dot === filename.length - 1) return null;
  const ext = filename.slice(dot + 1).toLowerCase();
  return SUFFIX_KIND[ext] ?? null;
}

/** Human label for a supplement kind — what the file carries for reproduction. */
export const KIND_LABEL: Record<SupplementKind, string> = {
  pdf: "Extended methods",
  xlsx: "Supplementary table",
  csv: "Supplementary table",
};

/** Compact byte-size for display (e.g. "12 KB", "3.4 MB"); empty for an unknown size. */
export function formatBytes(n?: number): string {
  if (n == null || !Number.isFinite(n) || n < 0) return "";
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}
