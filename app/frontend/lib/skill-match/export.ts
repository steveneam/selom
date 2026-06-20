/**
 * Skill-Match export — pure, deterministic, offline (no LLM, no backend).
 *
 * Turns the client-side routing result (paper metadata + skill inventory + per-figure routing) into
 * a single delimited document: TSV for "Copy" (pastes straight into Excel / Google Sheets) and CSV
 * for "Download". The three logical sections live in one sheet, separated by blank rows and a section
 * title row, so a later openpyxl backend can split them into real `.xlsx` sheets without changing the
 * data the FE already has. Serialization is RFC-4180-correct for CSV; TSV cells are sanitised (a tab
 * or newline inside a cell would break the paste) — the skill lists join on "; " so neither occurs.
 */

export interface ExportSkillRow {
  /** Catalog display name ("Leiden clustering"), the same label the chip shows. */
  name: string;
  slug: string;
  installed: boolean;
}

export interface ExportFigureRow {
  figure: string;
  /** In-scope skills the figure routed to, display names, top-ranked first. */
  skills: string[];
  tier: string; // "Structured" | "Recovered"
  confidencePct: number; // 0–100
  attribution: string; // human label
  /** Co-present out-of-scope readouts (human labels). */
  outOfScope: string[];
}

export interface SkillMatchExport {
  paper: {
    title?: string | null;
    authors?: string[] | null;
    venue?: string | null;
    year?: number | null;
    volume?: string | null;
    issue?: string | null;
    pages?: string | null;
    doi?: string | null;
    pmid?: string | null;
    filename: string;
  };
  skills: ExportSkillRow[];
  outOfScope: string[]; // human labels
  figures: ExportFigureRow[];
  unmatchedTerms: string[];
}

/** A labelled key/value row, dropped when the value is empty (keeps the paper block tidy). */
function kv(label: string, value: unknown): string[][] {
  const v = value == null || value === "" ? "" : String(value);
  return v ? [[label, v]] : [];
}

/**
 * Build the export as a 2D matrix of string cells. Ragged rows (varying column counts) are fine for
 * both CSV and TSV — Excel/Sheets pad short rows. Sections: Paper · Skill inventory · Per-figure
 * routing · unmatched terms, each preceded by a blank row + a title row.
 */
export function exportMatrix(data: SkillMatchExport): string[][] {
  const rows: string[][] = [];
  rows.push(["Skill Match", data.paper.filename]);

  // Paper
  rows.push([], ["Paper"]);
  rows.push(...kv("Title", data.paper.title || data.paper.filename));
  rows.push(...kv("Authors", (data.paper.authors ?? []).join("; ")));
  rows.push(...kv("Venue", data.paper.venue));
  rows.push(...kv("Year", data.paper.year));
  rows.push(...kv("Volume", data.paper.volume));
  rows.push(...kv("Issue", data.paper.issue));
  rows.push(...kv("Pages", data.paper.pages));
  rows.push(...kv("DOI", data.paper.doi));
  rows.push(...kv("PMID", data.paper.pmid));
  rows.push(...kv("Source file", data.paper.filename));

  // Skill inventory
  rows.push([], ["Skill inventory"], ["Skill", "Installed"]);
  if (data.skills.length === 0) rows.push(["(none detected)"]);
  for (const s of data.skills) rows.push([s.name, s.installed ? "yes" : "no"]);
  if (data.outOfScope.length > 0) {
    rows.push(["Out of scope (no Selom skill)"]);
    for (const o of data.outOfScope) rows.push([o]);
  }

  // Per-figure routing
  if (data.figures.length > 0) {
    rows.push([], ["Per-figure routing"]);
    rows.push(["Figure", "Skills", "Tier", "Confidence", "Attribution", "Out-of-scope readout"]);
    for (const f of data.figures) {
      rows.push([
        f.figure,
        f.skills.join("; "),
        f.tier,
        `${f.confidencePct}%`,
        f.attribution,
        f.outOfScope.join("; "),
      ]);
    }
  }

  // Skill-gap signal
  if (data.unmatchedTerms.length > 0) {
    rows.push([], ["Method terms with no Selom skill"]);
    for (const t of data.unmatchedTerms) rows.push([t]);
  }

  return rows;
}

/** RFC-4180 CSV escaping: quote a cell that holds the delimiter, a quote, or a newline. */
function escapeCsv(cell: string): string {
  return /[",\r\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell;
}

/** Serialize a cell matrix to a delimited string. CSV quotes; TSV strips tab/newline (can't quote). */
export function serializeMatrix(rows: string[][], delim: "," | "\t"): string {
  const cell = (c: string) =>
    delim === "," ? escapeCsv(c) : c.replace(/[\t\r\n]+/g, " ");
  return rows.map((r) => r.map(cell).join(delim)).join("\r\n");
}

export function toCSV(data: SkillMatchExport): string {
  return serializeMatrix(exportMatrix(data), ",");
}

export function toTSV(data: SkillMatchExport): string {
  return serializeMatrix(exportMatrix(data), "\t");
}

/** A safe download filename derived from the source file: "JEV.pdf" → "JEV-skill-match.csv". */
export function exportFilename(data: SkillMatchExport, ext = "csv"): string {
  const base = (data.paper.filename || "paper")
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[^\w.-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80) || "paper";
  return `${base}-skill-match.${ext}`;
}
