import {
  Activity,
  Atom,
  Boxes,
  ChartScatter,
  Dna,
  FlaskConical,
  Grid3x3,
  Microscope,
  Network,
  Sigma,
  Waves,
  type LucideIcon,
} from "lucide-react";
import type { SkillCatalogEntry } from "./types";

/**
 * Modality colour system — the Skill Store reads as a colour-coded grid where
 * each skill carries the hue of its primary omics domain (the colour-coded-card
 * idea from the reference designs, made functional). Colours are drawn from the
 * figure chart colourway so store chrome and figure data stay one family.
 */
const PALETTE = [
  "#22d3ee", // cyan
  "#60a5fa", // blue
  "#a78bfa", // violet
  "#34d399", // green
  "#fb923c", // orange
  "#f472b6", // pink
  "#facc15", // yellow
  "#f87171", // red
];

const EXPLICIT: Record<string, string> = {
  "scrna-seq": "#22d3ee",
  "single-cell": "#22d3ee",
  scrna: "#22d3ee",
  "bulk rna-seq": "#60a5fa",
  "rna-seq": "#60a5fa",
  bulk: "#60a5fa",
  transcriptomics: "#60a5fa",
  proteomics: "#a78bfa",
  "mass-spec": "#a78bfa",
  metabolomics: "#34d399",
  spatial: "#f472b6",
  epigenomics: "#facc15",
  atac: "#facc15",
  genomics: "#f87171",
  variant: "#f87171",
  "multi-omics": "#fb923c",
  multiomics: "#fb923c",
  pathway: "#34d399",
};

function hashColor(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return PALETTE[Math.abs(h) % PALETTE.length];
}

export function modalityColor(omics: string | undefined): string {
  if (!omics) return "var(--primary)";
  const k = omics.toLowerCase().trim();
  return EXPLICIT[k] ?? hashColor(k);
}

/**
 * Editorial groups (App-Store shelves). The single source of truth for both the
 * Store's shelf layout AND each card's category colour — so a category like
 * "single-cell" reads the SAME colour everywhere, regardless of a skill's
 * modality. (Modality colour lives on the small omics chips, not the category.)
 */
export const CATEGORY_GROUPS: {
  title: string;
  subtitle: string;
  color: string;
  categories: string[];
}[] = [
  {
    title: "Single-cell & spatial",
    subtitle: "Cluster, embed, and explore cells — and where they sit in tissue.",
    color: "#22d3ee",
    categories: ["single-cell"],
  },
  {
    title: "Differential expression",
    subtitle: "Find what changes between conditions, with the stats done for you.",
    color: "#60a5fa",
    categories: ["differential-expression"],
  },
  {
    title: "Pathways & enrichment",
    subtitle: "Turn a gene list into biological meaning — GO, Reactome, and more.",
    color: "#34d399",
    categories: ["pathway-analysis"],
  },
  {
    title: "Figures & visualization",
    subtitle: "Publication-ready volcanoes, heatmaps, and colourblind-safe palettes.",
    color: "#a78bfa",
    categories: ["data-visualization"],
  },
  {
    title: "Proteomics & metabolomics",
    subtitle: "Mass-spec abundance, metabolites, and cytometry.",
    color: "#f472b6",
    categories: ["proteomics", "metabolomics", "flow-cytometry"],
  },
  {
    title: "Genomics & variants",
    subtitle: "Variants, ancestry, copy-number, and whole-genome workflows.",
    color: "#f87171",
    categories: [
      "population-genetics",
      "variant-calling",
      "copy-number",
      "comparative-genomics",
      "genome-assembly",
      "genome-annotation",
      "pharmacogenomics",
      "crispr",
    ],
  },
  {
    title: "Epigenomics",
    subtitle: "Chromatin accessibility, methylation, and 3D genome structure.",
    color: "#facc15",
    categories: ["epigenomics", "chip-seq"],
  },
  {
    title: "Workflows & pipelines",
    subtitle: "End-to-end reference pipelines from raw reads to results.",
    color: "#fb923c",
    categories: ["workflow", "metagenomics", "immunoinformatics", "clip-seq"],
  },
];

const CATEGORY_COLOR: Record<string, string> = Object.fromEntries(
  CATEGORY_GROUPS.flatMap((g) => g.categories.map((c) => [c, g.color])),
);

/** Stable colour for a category — consistent across every card in that category. */
export function categoryColor(category: string): string {
  return CATEGORY_COLOR[category] ?? "#8b98a9";
}

/** The card's primary hue = its category colour (not its modality). */
export function skillColor(skill: SkillCatalogEntry): string {
  return categoryColor(skill.category);
}

/** kebab-case source category → human Title Case ("single-cell" → "Single-cell"). */
const CATEGORY_LABELS: Record<string, string> = {
  "single-cell": "Single-cell",
  "differential-expression": "Differential expression",
  "data-visualization": "Visualization",
  "pathway-analysis": "Pathways & enrichment",
  proteomics: "Proteomics",
  "population-genetics": "Population genetics",
  "variant-calling": "Variant calling",
  "copy-number": "Copy number",
  "comparative-genomics": "Comparative genomics",
  "genome-assembly": "Genome assembly",
  "genome-annotation": "Genome annotation",
  pharmacogenomics: "Pharmacogenomics",
  metagenomics: "Metagenomics",
  metabolomics: "Metabolomics",
  "flow-cytometry": "Flow cytometry",
  epigenomics: "Epigenomics",
  "chip-seq": "ChIP-seq",
  "clip-seq": "CLIP-seq",
  immunoinformatics: "Immunoinformatics",
  crispr: "CRISPR",
  workflow: "Workflow",
};

export function humanizeCategory(category: string): string {
  return (
    CATEGORY_LABELS[category] ??
    category
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/**
 * A representative icon per skill, chosen from category/name keywords — so the
 * grid is scannable by analysis kind, not just colour.
 */
export function skillIcon(skill: SkillCatalogEntry): LucideIcon {
  const hay = `${skill.category} ${skill.name} ${skill.id}`.toLowerCase();
  if (/(umap|tsne|t-sne|embedding|cluster|dimension)/.test(hay)) return ChartScatter;
  if (/(deg|differential|volcano|expression|fold)/.test(hay)) return Activity;
  if (/(enrichment|pathway|gsea|go[-_ ]|ontology|network)/.test(hay)) return Network;
  if (/(heatmap|matrix|correlation)/.test(hay)) return Grid3x3;
  if (/(proteom|mass[-_ ]?spec|peptide|phospho)/.test(hay)) return FlaskConical;
  if (/(metabolom|compound|lipid)/.test(hay)) return Atom;
  if (/(variant|genom|mutation|vcf)/.test(hay)) return Dna;
  if (/(qc|quality|normal|batch)/.test(hay)) return Waves;
  if (/(stat|test|model|regression)/.test(hay)) return Sigma;
  if (/(single|scrna|cell)/.test(hay)) return Microscope;
  return Boxes;
}
