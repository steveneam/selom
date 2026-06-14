/**
 * Offline fixture for the gene-set catalog (gene-set builder Phase A).
 *
 * A small, representative slice of the real corpus (GO · WikiPathways · curated) so the
 * "Gene Sets" surface renders and applies with the backend down (`npm run dev:mock`).
 * Mirrors the GET /gene-sets contract in app/backend/main.py.
 */

import type { GeneSetCard, GeneSetDetail, GeneSetSearchResponse } from "@/lib/gene-sets/api";

interface FixtureSet extends GeneSetCard {
  genes: string[];
}

const SETS: FixtureSet[] = [
  {
    id: "curated:photo01", name: "Phototransduction & visual cycle", source: "curated",
    source_label: "Selom curated", license: "Selom (owned)",
    genes: ["RHO", "OPN1LW", "OPN1MW", "OPN1SW", "GNAT1", "GNAT2", "PDE6A", "PDE6B", "PDE6G",
      "CNGA1", "CNGB1", "GUCY2D", "GUCA1A", "RCVRN", "SAG", "GRK1", "RGS9", "SLC24A1", "RDH12", "RPE65"],
    size: 36, sample_genes: ["RHO", "GNAT1", "PDE6B", "CNGA1", "GUCY2D", "SAG", "GRK1", "RPE65"],
  },
  {
    id: "curated:cilium01", name: "Primary cilium & ciliopathy core", source: "curated",
    source_label: "Selom curated", license: "Selom (owned)",
    genes: ["IFT88", "IFT172", "IFT140", "CEP290", "BBS1", "BBS2", "ARL13B", "ARL3", "RPGR",
      "RPGRIP1", "CC2D2A", "NPHP1", "TMEM67", "MKS1", "AHI1", "INPP5E", "OFD1", "KIF7"],
    size: 45, sample_genes: ["IFT88", "CEP290", "BBS1", "ARL13B", "RPGR", "RPGRIP1", "NPHP1", "MKS1"],
  },
  {
    id: "wp:wp100", name: "Glutathione metabolism", source: "wikipathways",
    source_label: "WikiPathways", license: "CC0-1.0",
    genes: ["GPX1", "GPX2", "GSR", "GCLC", "GCLM", "GSS", "IDH1", "G6PD", "GGT1", "ANPEP"],
    size: 22, sample_genes: ["GPX1", "GSR", "GCLC", "GSS", "IDH1", "G6PD", "GGT1", "ANPEP"],
  },
  {
    id: "wp:wp107", name: "Translation factors", source: "wikipathways",
    source_label: "WikiPathways", license: "CC0-1.0",
    genes: ["EIF4E", "EIF4G1", "EIF2S1", "EEF1A1", "EEF2", "ETF1", "PABPC1", "EIF3A", "EIF1AX"],
    size: 48, sample_genes: ["EIF4E", "EIF4G1", "EIF2S1", "EEF1A1", "EEF2", "ETF1", "PABPC1", "EIF3A"],
  },
  {
    id: "wp:wp179", name: "Cell cycle", source: "wikipathways",
    source_label: "WikiPathways", license: "CC0-1.0",
    genes: ["CCNB1", "CCNE1", "CDK1", "CDK2", "CDK4", "CDC20", "RB1", "E2F1", "TP53", "MCM2"],
    size: 124, sample_genes: ["CCNB1", "CDK1", "CDK2", "CDK4", "RB1", "E2F1", "TP53", "MCM2"],
  },
  {
    id: "wp:wp306", name: "Focal adhesion", source: "wikipathways",
    source_label: "WikiPathways", license: "CC0-1.0",
    genes: ["ITGB1", "ITGA5", "FN1", "PXN", "VCL", "TLN1", "PTK2", "SRC", "AKT1", "MAPK1"],
    size: 199, sample_genes: ["ITGB1", "FN1", "PXN", "VCL", "PTK2", "SRC", "AKT1", "MAPK1"],
  },
  {
    id: "go:bp_photo", name: "GO:BP: phototransduction", source: "go",
    source_label: "Gene Ontology", license: "CC-BY-4.0",
    genes: ["RHO", "GNAT1", "PDE6A", "PDE6B", "CNGA1", "GUCY2D", "ARR3", "GRK1", "RCVRN", "SAG"],
    size: 41, sample_genes: ["RHO", "GNAT1", "PDE6A", "CNGA1", "GUCY2D", "GRK1", "RCVRN", "SAG"],
  },
  {
    id: "go:cc_outerseg", name: "GO:CC: photoreceptor outer segment", source: "go",
    source_label: "Gene Ontology", license: "CC-BY-4.0",
    genes: ["RHO", "PRPH2", "ROM1", "RP1", "ABCA4", "PDE6B", "GNAT1", "RCVRN", "GUCY2D", "CNGB1"],
    size: 58, sample_genes: ["RHO", "PRPH2", "ROM1", "RP1", "ABCA4", "PDE6B", "GNAT1", "CNGB1"],
  },
  {
    id: "go:bp_cilium", name: "GO:BP: cilium assembly", source: "go",
    source_label: "Gene Ontology", license: "CC-BY-4.0",
    genes: ["IFT88", "IFT172", "CEP290", "ARL13B", "BBS1", "BBS2", "NPHP1", "TMEM67", "CC2D2A", "MKS1"],
    size: 187, sample_genes: ["IFT88", "IFT172", "CEP290", "ARL13B", "BBS1", "NPHP1", "TMEM67", "MKS1"],
  },
  {
    id: "go:mf_gpcr", name: "GO:MF: G protein-coupled receptor activity", source: "go",
    source_label: "Gene Ontology", license: "CC-BY-4.0",
    genes: ["RHO", "OPN1LW", "OPN1MW", "ADRB1", "ADRB2", "DRD1", "HTR2A", "CNR1", "GRM1", "S1PR1"],
    size: 312, sample_genes: ["RHO", "OPN1LW", "ADRB2", "DRD1", "HTR2A", "CNR1", "GRM1", "S1PR1"],
  },
  {
    id: "ref:ciliacarta", name: "Ciliopathy genes (CiliaCarta)", source: "reference",
    source_label: "Reference panels", license: "Academic (CiliaCarta, van Dam 2013)",
    attribution: "CiliaCarta — van Dam et al., 2013",
    genes: ["IFT88", "CEP290", "BBS1", "ARL13B", "RPGR", "RPGRIP1", "NPHP1", "MKS1", "AHI1", "CC2D2A"],
    size: 935, sample_genes: ["IFT88", "CEP290", "BBS1", "ARL13B", "RPGR", "RPGRIP1", "NPHP1", "MKS1"],
  },
  {
    id: "ref:ups", name: "Proteostasis — ubiquitin–proteasome system", source: "reference",
    source_label: "Reference panels", license: "CMRI Fidelle (curated)",
    attribution: "CMRI Fidelle lab (curated, proteostasis network)",
    genes: ["PSMA1", "PSMA2", "PSMB5", "PSMC1", "PSMD1", "UBA1", "UBE2D1", "UBE3A", "CUL1", "FBXW7"],
    size: 1185, sample_genes: ["PSMA1", "PSMB5", "PSMC1", "UBA1", "UBE2D1", "UBE3A", "CUL1", "FBXW7"],
  },
];

function sources(): GeneSetSearchResponse["sources"] {
  const counts: Record<string, { label: string; license: string; n: number }> = {};
  for (const s of SETS) {
    counts[s.source] ??= { label: s.source_label, license: s.license, n: 0 };
    counts[s.source].n += 1;
  }
  // Inflate the displayed counts so the meter reads like the real corpus, not the fixture.
  const realish: Record<string, number> = { go: 7727, wikipathways: 921, curated: 2, reference: 5 };
  return Object.entries(counts).map(([key, v]) => ({
    key, label: v.label, license: v.license, n_sets: realish[key] ?? v.n,
  }));
}

function card({ genes: _genes, ...rest }: FixtureSet): GeneSetCard {
  return rest;
}

export function searchFixture(q: string, source: string | null, limit: number): GeneSetSearchResponse {
  const ql = q.trim().toLowerCase();
  let results = SETS.filter((s) => (!source || source === "all" ? true : s.source === source));
  if (ql) results = results.filter((s) => s.name.toLowerCase().includes(ql));
  return { sources: sources(), results: results.slice(0, limit).map(card) };
}

export function compileFixture(setIds: string[], op: string, name?: string) {
  const picked = SETS.filter((s) => setIds.includes(s.id));
  const lists = picked.map((s) => new Set(s.genes.map((g) => g.toUpperCase())));
  let combined = new Set<string>();
  if (lists.length) {
    combined = op === "intersect"
      ? lists.reduce((a, b) => new Set([...a].filter((g) => b.has(g))))
      : new Set(lists.flatMap((l) => [...l]));
  }
  const genes = [...combined].sort();
  return {
    genes,
    op: op === "intersect" ? "intersect" : "union",
    sources: picked.map((s) => ({
      id: s.id, name: s.name, source_label: s.source_label, license: s.license, size: s.size,
    })),
    missing: setIds.filter((id) => !picked.some((s) => s.id === id)),
    provenance: {
      op: op === "intersect" ? "intersect" : "union",
      n_in: combined.size, n_out: genes.length, n_remapped: 0, n_unrecognized: 0,
      normalized: false, licenses: [...new Set(picked.map((s) => s.license))].sort(),
    },
    ...(name ? { name } : {}),
  };
}

export function getFixtureSet(id: string): GeneSetDetail | null {
  const s = SETS.find((x) => x.id === id);
  if (!s) return null;
  return {
    ...card(s),
    genes: s.genes,
    provenance: {
      source: s.source, source_label: s.source_label, license: s.license,
      set_name: s.name, n_genes: s.genes.length,
    },
  };
}
