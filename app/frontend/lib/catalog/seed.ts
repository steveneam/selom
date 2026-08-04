import { liveSkill } from "./live-skills";
import { SELOM_SEED } from "./selom-seed.generated";
import type { SkillCatalogEntry } from "./types";

/**
 * Seed of the Skill Store inventory — the offline twin of `GET /skills` plus a curated long tail.
 *
 * TWO HALVES, and only one of them is written by hand:
 *  · **Selom-native** — spread from `./selom-seed.generated.ts`, produced by
 *    `scripts/gen-catalog-seed.mjs` from the backend's own `skill.json` files. This half used to be
 *    hand-listed and went **19 of 44 skills stale**, which nothing could see until a real browser
 *    drove the Workbench [[selom-shipped-not-reachable]]. Regenerate with `npm run gen:seed`;
 *    `registry-completeness.test.ts` fails on drift, so it cannot go quietly stale again.
 *  · **ClawBio / bioSkills** — a curated slice standing in for the full ~600-skill catalog
 *    (540 bioSkills + 88 ClawBio). These ship no `skill.json`, so the copy is genuinely authored.
 *
 * `tier: "verified"` = runs now (Selom-native scverse runners + ClawBio runnable).
 * `tier: "community"` = browsable + installable-as-intent; runs later in a sandbox.
 *
 * The seed is the FALLBACK, never the authority: `getSkill` prefers the live registry (see below).
 */

/** True catalog sizes (for the honest coverage meter — design §6.4). */
export const CATALOG_TOTAL_ESTIMATE = 628; // 540 bioSkills + 88 ClawBio
export const BIOSKILLS_COUNT = 540;
export const CLAWBIO_COUNT = 88;

const e = (x: SkillCatalogEntry): SkillCatalogEntry => x;

export const CATALOG: SkillCatalogEntry[] = [
  // ── Selom-native (the launch wedge — Verified, run now) ───────────────────
  // GENERATED from the backend's own skill.json files, not hand-listed: this block went 19
  // skills stale and nothing could see it. `npm run gen:seed` rewrites it; the drift guard in
  // registry-completeness.test.ts fails the build if anyone forgets. Everything BELOW is
  // hand-authored curation for sources that ship no skill.json.
  ...SELOM_SEED,

  // ── ClawBio runnable (Verified — wrap the ~29 production pipelines) ────────
  e({
    id: "clawbio.scrna-orchestrator",
    name: "scRNA Orchestrator",
    summary: "End-to-end QC → clustering → marker detection for single-cell RNA-seq.",
    source: "clawbio", category: "single-cell", omics: ["scRNA-seq"],
    tier: "verified", status: "production", engine: "python",
    inputFormats: [".h5ad", ".csv"], chainsWith: ["selom.deg", "selom.volcano"],
    outputs: ["figure", "report", "tables"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/scrna-orchestrator" }, version: "1.0.0", popularity: 85,
  }),
  e({
    id: "clawbio.gwas-lookup",
    name: "GWAS Lookup",
    summary: "Query GWAS associations for variants/genes; Manhattan + region plots.",
    source: "clawbio", category: "population-genetics", omics: ["genomics"],
    tier: "verified", status: "production", engine: "python",
    inputFormats: [".vcf", ".csv"], chainsWith: ["clawbio.ancestry-pca"],
    outputs: ["figure", "report"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/gwas-lookup" }, version: "1.0.0", popularity: 70,
  }),
  e({
    id: "clawbio.ancestry-pca",
    name: "Ancestry PCA",
    summary: "Population-structure PCA from genotypes with reference projection.",
    source: "clawbio", category: "population-genetics", omics: ["genomics"],
    tier: "verified", status: "production", engine: "python",
    inputFormats: [".vcf"], chainsWith: ["clawbio.gwas-lookup"],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/ancestry-pca" }, version: "1.0.0", popularity: 61,
  }),
  e({
    id: "clawbio.variant-annotation",
    name: "Variant Annotation",
    summary: "Annotate a VCF (VEP/ClinVar/gnomAD) with ACMG-style classification.",
    source: "clawbio", category: "variant-calling", omics: ["genomics"],
    tier: "verified", status: "production", engine: "python",
    inputFormats: [".vcf"], chainsWith: ["clawbio.gwas-lookup"],
    outputs: ["report", "tables"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/variant-annotation" }, version: "1.0.0", popularity: 67,
  }),
  e({
    id: "clawbio.metagenomics-profiler",
    name: "Metagenomics Profiler",
    summary: "Taxonomic profiling (MetaPhlAn/Kraken2) → abundance bar/krona.",
    source: "clawbio", category: "metagenomics", omics: ["metagenomics"],
    tier: "verified", status: "beta", engine: "python",
    inputFormats: [".fastq", ".fasta"], chainsWith: [],
    outputs: ["figure", "report"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/metagenomics-profiler" }, version: "0.9.0", popularity: 48,
  }),
  e({
    id: "clawbio.pharmgx-reporter",
    name: "PharmGx Reporter",
    summary: "Pharmacogenomic report from consumer/clinical genotypes.",
    source: "clawbio", category: "pharmacogenomics", omics: ["genomics"],
    tier: "verified", status: "production", engine: "python",
    inputFormats: [".txt", ".vcf"], chainsWith: ["clawbio.variant-annotation"],
    outputs: ["report"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/pharmgx-reporter" }, version: "1.0.0", popularity: 53,
  }),
  e({
    id: "clawbio.galaxy-bridge",
    name: "Galaxy Bridge",
    summary: "Route an input to one of 8,000+ Galaxy tools and pull results back.",
    source: "clawbio", category: "workflow", omics: ["genomics", "transcriptomics"],
    tier: "community", status: "beta", engine: "agent-sandbox",
    inputFormats: [".fastq", ".bam", ".vcf"], chainsWith: [],
    outputs: ["report", "tables"], license: "MIT",
    provenance: { repo: "ClawBio/ClawBio", path: "skills/galaxy-bridge" }, version: "0.7.0", popularity: 44,
  }),

  // ── bioSkills long tail (Community — browsable now, Foundry-ported later) ──
  e({
    id: "bioskills.rnaseq-workflow",
    name: "RNA-seq Workflow",
    summary: "Reference bulk RNA-seq pipeline: QC → align (STAR) → count → DE.",
    source: "bioskills", category: "workflow", omics: ["bulk RNA-seq"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq"], chainsWith: ["selom.deg"],
    outputs: ["report", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "rnaseq-workflow" }, version: "—", popularity: 59,
  }),
  e({
    id: "bioskills.variant-calling",
    name: "Somatic Variant Calling",
    summary: "Tumor/normal calling (BWA → GATK4 Mutect2) with filtering guidance.",
    source: "bioskills", category: "variant-calling", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".bam", ".cram"], chainsWith: ["clawbio.variant-annotation"],
    outputs: ["report", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "variant-calling" }, version: "—", popularity: 57,
  }),
  e({
    id: "bioskills.chip-seq",
    name: "ChIP-seq Peaks",
    summary: "Align → peak-call (MACS2) → annotate; signal + peak-overlap plots.",
    source: "bioskills", category: "chip-seq", omics: ["epigenomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq", ".bam"], chainsWith: [],
    outputs: ["figure", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "chip-seq" }, version: "—", popularity: 41,
  }),
  e({
    id: "bioskills.atac-seq",
    name: "ATAC-seq Accessibility",
    summary: "Open-chromatin pipeline: QC → peaks → differential accessibility.",
    source: "bioskills", category: "epigenomics", omics: ["epigenomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq", ".bam"], chainsWith: ["bioskills.chip-seq"],
    outputs: ["figure", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "atac-seq" }, version: "—", popularity: 38,
  }),
  e({
    id: "bioskills.spatial-transcriptomics",
    name: "Spatial Transcriptomics",
    summary: "Visium/Xenium QC, clustering, and spatially-variable gene maps.",
    source: "bioskills", category: "single-cell", omics: ["spatial"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".h5ad"], chainsWith: ["selom.umap_scrna"],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "spatial-transcriptomics" }, version: "—", popularity: 49,
  }),
  e({
    id: "bioskills.trajectory-analysis",
    name: "Trajectory / Pseudotime",
    summary: "Infer developmental trajectories and order cells along pseudotime.",
    source: "bioskills", category: "single-cell", omics: ["scRNA-seq"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".h5ad"], chainsWith: ["selom.umap_scrna"],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "trajectory-analysis" }, version: "—", popularity: 46,
  }),
  e({
    id: "bioskills.cnv-calling",
    name: "Copy-number (CNVkit)",
    summary: "Call and segment copy-number from tumor sequencing; genome plot.",
    source: "bioskills", category: "copy-number", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".bam"], chainsWith: [],
    outputs: ["figure", "tables"], license: "Apache-2.0",
    provenance: { repo: "GPTomics/bioSkills", path: "cnv-calling" }, version: "—", popularity: 33,
  }),
  e({
    id: "bioskills.hic-contact-maps",
    name: "Hi-C Contact Maps",
    summary: "3D genome contact-matrix processing and TAD/compartment plots.",
    source: "bioskills", category: "epigenomics", omics: ["epigenomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq", ".cool"], chainsWith: [],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "hic-contact-maps" }, version: "—", popularity: 27,
  }),
  e({
    id: "bioskills.clip-seq",
    name: "CLIP-seq Binding",
    summary: "RNA–protein binding sites (PureCLIP) with ENCODE-style QC.",
    source: "bioskills", category: "clip-seq", omics: ["transcriptomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq", ".bam"], chainsWith: [],
    outputs: ["figure", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "clip-seq" }, version: "—", popularity: 22,
  }),
  e({
    id: "bioskills.orthofinder",
    name: "Orthology (OrthoFinder3)",
    summary: "Infer orthogroups + gene trees across species; synteny overview.",
    source: "bioskills", category: "comparative-genomics", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fasta"], chainsWith: [],
    outputs: ["report", "tables"], license: "GPL-3.0",
    provenance: { repo: "GPTomics/bioSkills", path: "orthofinder" }, version: "—", popularity: 31,
  }),
  e({
    id: "bioskills.genome-assembly",
    name: "Genome Assembly",
    summary: "Long-read assembly → polish → QC (BUSCO) with contiguity plots.",
    source: "bioskills", category: "genome-assembly", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq"], chainsWith: ["bioskills.genome-annotation"],
    outputs: ["report"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "genome-assembly" }, version: "—", popularity: 25,
  }),
  e({
    id: "bioskills.genome-annotation",
    name: "Genome Annotation",
    summary: "Structural + functional annotation of an assembled genome.",
    source: "bioskills", category: "genome-annotation", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fasta"], chainsWith: ["bioskills.genome-assembly"],
    outputs: ["report", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "genome-annotation" }, version: "—", popularity: 23,
  }),
  e({
    id: "bioskills.immunoinformatics-tcr",
    name: "TCR/BCR Repertoire",
    summary: "Immune repertoire analysis (MixCR) with clonality + diversity plots.",
    source: "bioskills", category: "immunoinformatics", omics: ["transcriptomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fastq"], chainsWith: [],
    outputs: ["figure", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "immunoinformatics-tcr" }, version: "—", popularity: 29,
  }),
  e({
    id: "bioskills.crispr-screen",
    name: "CRISPR Screen (MAGeCK)",
    summary: "Pooled screen analysis: count → test → rank essential genes.",
    source: "bioskills", category: "crispr", omics: ["genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".csv", ".fastq"], chainsWith: ["selom.enrichment"],
    outputs: ["figure", "tables"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "crispr-screen" }, version: "—", popularity: 35,
  }),
  e({
    id: "bioskills.methylation",
    name: "DNA Methylation",
    summary: "Bisulfite/array methylation: DMR detection + methylation tracks.",
    source: "bioskills", category: "epigenomics", omics: ["epigenomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".bam", ".csv"], chainsWith: [],
    outputs: ["figure", "tables"], license: "Artistic-2.0",
    provenance: { repo: "GPTomics/bioSkills", path: "methylation" }, version: "—", popularity: 21,
  }),
  e({
    id: "bioskills.metabolomics-xcms",
    name: "Metabolomics (XCMS)",
    summary: "LC-MS peak picking → alignment → differential metabolite analysis.",
    source: "bioskills", category: "metabolomics", omics: ["metabolomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".mzML"], chainsWith: ["selom.enrichment"],
    outputs: ["figure", "tables"], license: "GPL-2.0",
    provenance: { repo: "GPTomics/bioSkills", path: "metabolomics-xcms" }, version: "—", popularity: 30,
  }),
  e({
    id: "bioskills.flow-cytometry",
    name: "Flow Cytometry",
    summary: "Gating + dimensionality reduction for cytometry (FCS) data.",
    source: "bioskills", category: "flow-cytometry", omics: ["proteomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".fcs"], chainsWith: [],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "flow-cytometry" }, version: "—", popularity: 19,
  }),
  e({
    id: "bioskills.perceptual-palettes",
    name: "Perceptual Palettes",
    summary: "Colourblind-safe, perceptually-uniform palettes for omics figures.",
    source: "bioskills", category: "data-visualization", omics: ["transcriptomics", "proteomics", "genomics"],
    tier: "community", status: "community", engine: "agent-sandbox",
    inputFormats: [".csv"], chainsWith: ["selom.heatmap", "selom.umap_scrna"],
    outputs: ["figure"], license: "MIT",
    provenance: { repo: "GPTomics/bioSkills", path: "perceptual-palettes" }, version: "—", popularity: 26,
  }),
];

/**
 * Resolve a skill by catalog id — the LIVE registry first, the static seed second.
 *
 * The live lookup is not a nicety: the seed is hand-maintained and runs behind the backend, and
 * `registry.ts`'s stated contract is that the backend is the source of truth for what runs now. Seed-
 * only resolution silently rendered every post-seed skill as its raw id with a "Queued" badge and a
 * disabled Apply — see `live-skills.ts` for the measurement and why the overlay is a separate module.
 *
 * A component that NAMES or GATES a skill through this should call `useLiveSkills()` so it re-renders
 * when the registry lands; otherwise it can keep a first paint taken before the fetch resolved.
 */
export function getSkill(id: string): SkillCatalogEntry | undefined {
  return liveSkill(id) ?? CATALOG.find((s) => s.id === id);
}

/** Distinct categories present in the seed, alphabetized. */
export const CATEGORIES: string[] = Array.from(new Set(CATALOG.map((s) => s.category))).sort();

/** Distinct omics facets present in the seed, alphabetized. */
export const OMICS: string[] = Array.from(new Set(CATALOG.flatMap((s) => s.omics))).sort();

/** Verified (runnable-now) count in the seed — for the honesty meter copy. */
export const VERIFIED_SEEDED = CATALOG.filter((s) => s.tier === "verified").length;
