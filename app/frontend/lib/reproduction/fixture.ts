/**
 * Reproduction view fixture — the REAL engine output, generated from the three
 * captured ledgers (app/backend/papers_api.py via drive_captured()). NOT hand-authored:
 * regenerate by running papers_api.list_papers()/driven_ledger() and re-emitting.
 *
 * Used as the MSW mock (mocks/handlers.ts) AND the offline fallback for the live
 * /api/papers fetch (lib/reproduction/api.ts) — so the view is honest data either way.
 */
import type { Ledger, PaperSummary } from "./types";

export const REPRO_PAPERS: PaperSummary[] = [
  {
    "slug": "rpgrip1",
    "title": "RPGRIP1 retinal organoid (Loi et al. 2025, Stem Cell Reports)",
    "doi": "10.1016/j.stemcr.2025.102717",
    "geo": [
      "GSE293982",
      "GSE293984"
    ],
    "score": {
      "paper_id": "rpgrip1",
      "reproducibility": 63,
      "selom_confidence": 92,
      "tier": "deposit-faithful",
      "color": "#f59e0b",
      "n_scored": 7,
      "n_in_scope": 10,
      "n_out_of_scope": 3,
      "n_form_only": 3,
      "coverage": "7 scored / 10 in-scope · 3 out-of-scope · 3 form-only"
    },
    "n_panels": 13,
    "n_in_scope": 10,
    "findings": {
      "reproduced": 9,
      "paper_irreproducible": 2,
      "structural_limit": 2,
      "engine_delta": 1,
      "upstream_delta": 1,
      "selom_engine_bugs": 0
    },
    "provenance_divergences": [],
    "cells": [
      {
        "panel_key": "5sig",
        "reproducibility": 40,
        "tier": "irreproducible",
        "color": "#f97316",
        "attribution_icon": "📄",
        "in_scope": true
      },
      {
        "panel_key": "5C",
        "reproducibility": 84,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "5D",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "5E",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "5F",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "6A",
        "reproducibility": 92,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "6D",
        "reproducibility": 38,
        "tier": "irreproducible",
        "color": "#f97316",
        "attribution_icon": "🗄",
        "in_scope": true
      },
      {
        "panel_key": "6E",
        "reproducibility": 45,
        "tier": "irreproducible",
        "color": "#f97316",
        "attribution_icon": "🗄",
        "in_scope": true
      },
      {
        "panel_key": "6F",
        "reproducibility": 84,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "6G",
        "reproducibility": 84,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      }
    ]
  },
  {
    "slug": "jev",
    "title": "Retinal EV-miRNA driving gliotic responses in degeneration (Cioanca, Natoli et al. 2023, J Extracell Vesicles)",
    "doi": "10.1002/jev2.12393",
    "geo": [
      "GSE153674 (Fadl 2020 reference — the study's own scRNA PRJNA990691 not deposited)"
    ],
    "score": {
      "paper_id": "jev",
      "reproducibility": 86,
      "selom_confidence": 100,
      "tier": "reproduced",
      "color": "#22c55e",
      "n_scored": 7,
      "n_in_scope": 7,
      "n_out_of_scope": 4,
      "n_form_only": 0,
      "coverage": "7 scored / 7 in-scope · 4 out-of-scope"
    },
    "n_panels": 11,
    "n_in_scope": 7,
    "findings": {
      "reproduced": 14,
      "paper_irreproducible": 0,
      "structural_limit": 0,
      "engine_delta": 0,
      "upstream_delta": 0,
      "selom_engine_bugs": 0
    },
    "provenance_divergences": [
      "4e: ST6+ Fig4e−"
    ],
    "cells": [
      {
        "panel_key": "1c",
        "reproducibility": 92,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "3",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "4c",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "4d",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "4e",
        "reproducibility": 58,
        "tier": "deposit-faithful",
        "color": "#f59e0b",
        "attribution_icon": "📄",
        "in_scope": true
      },
      {
        "panel_key": "5D",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "6a",
        "reproducibility": 92,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "8a",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "8ann",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "8d",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "8e",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      }
    ]
  },
  {
    "slug": "hani",
    "title": "Comprehensive characterization of fetal and mature retinal cell identity to assess the fidelity of retinal organoids (Kim, Gonzalez-Cordero, Yang et al. 2023, Stem Cell Reports)",
    "doi": "10.1016/j.stemcr.2022.12.002",
    "geo": [
      "GSE201356"
    ],
    "score": {
      "paper_id": "hani",
      "reproducibility": 96,
      "selom_confidence": 100,
      "tier": "verified",
      "color": "#15803d",
      "n_scored": 5,
      "n_in_scope": 5,
      "n_out_of_scope": 1,
      "n_form_only": 0,
      "coverage": "5 scored / 5 in-scope · 1 out-of-scope"
    },
    "n_panels": 6,
    "n_in_scope": 5,
    "findings": {
      "reproduced": 9,
      "paper_irreproducible": 0,
      "structural_limit": 0,
      "engine_delta": 0,
      "upstream_delta": 0,
      "selom_engine_bugs": 0
    },
    "provenance_divergences": [],
    "cells": [
      {
        "panel_key": "1D",
        "reproducibility": 92,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "2A",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "2C",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "3B",
        "reproducibility": 92,
        "tier": "reproduced",
        "color": "#22c55e",
        "attribution_icon": "✓",
        "in_scope": true
      },
      {
        "panel_key": "6D",
        "reproducibility": null,
        "tier": "out-of-scope",
        "color": "#9ca3af",
        "attribution_icon": "🗄",
        "in_scope": false
      },
      {
        "panel_key": "6E",
        "reproducibility": 100,
        "tier": "verified",
        "color": "#15803d",
        "attribution_icon": "✓",
        "in_scope": true
      }
    ]
  }
];

export const REPRO_LEDGERS: Record<string, Ledger> = {
  "rpgrip1": {
    "paper": {
      "id": "rpgrip1",
      "slug": "rpgrip1",
      "title": "RPGRIP1 retinal organoid (Loi et al. 2025, Stem Cell Reports)",
      "doi": "10.1016/j.stemcr.2025.102717",
      "geo": [
        "GSE293982",
        "GSE293984"
      ]
    },
    "panels": [
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "sig",
        "chart_form": "count",
        "scope": "transcriptomic",
        "data_source": "GSE293982 (bulk featureCounts)",
        "skill_id": "deg",
        "golden": [
          {
            "metric": "universe",
            "value": 1133,
            "unit": "",
            "source": "methods",
            "confidence": 1.0,
            "note": "RPGRIP1-associated GO union — reproduced byte-exact"
          },
          {
            "metric": "signature.count",
            "value": 78,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "figures/results say 78; methods say 181 (internal inconsistency)"
          },
          {
            "metric": "signature.down_both",
            "value": 49,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "signature genes down-regulated in BOTH LCA-1 & MS-VUS"
          }
        ],
        "weight": 2.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "A",
        "chart_form": "dotplot",
        "scope": "transcriptomic",
        "data_source": "GSE293982",
        "skill_id": "gsea",
        "golden": [],
        "weight": 1.0,
        "note": "GSEA: retinal/photoreceptor/cilium terms negatively enriched, stronger in LCA-1 (MS-VUS alone clears 0 at FDR<0.05) — form+claim, no printed value",
        "status": "pending"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "B",
        "chart_form": "pca",
        "scope": "transcriptomic",
        "data_source": "GSE293982",
        "skill_id": "pca",
        "golden": [],
        "weight": 1.0,
        "note": "PCA of the 78 signature genes: 3 clusters, MS-VUS separates — form+claim",
        "status": "pending"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "C",
        "chart_form": "heatmap",
        "scope": "transcriptomic",
        "data_source": "GSE293982",
        "skill_id": "deg",
        "golden": [
          {
            "metric": "RHO.pct_LCA1",
            "value": -71,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": ""
          },
          {
            "metric": "RHO.pct_MSVUS",
            "value": -34,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": ""
          },
          {
            "metric": "PRPH2.pct_LCA1",
            "value": -53,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": ""
          },
          {
            "metric": "PRPH2.pct_MSVUS",
            "value": -18,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": ""
          },
          {
            "metric": "RPGR.pct_MSVUS",
            "value": 59,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": ""
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "D",
        "chart_form": "ihc",
        "scope": "wet_lab",
        "data_source": "",
        "skill_id": null,
        "golden": [
          {
            "metric": "PRPH2.ihc",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "PRPH2 immunostaining"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "E",
        "chart_form": "qpcr",
        "scope": "wet_lab",
        "data_source": "",
        "skill_id": null,
        "golden": [
          {
            "metric": "rtqpcr",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "independent RT-qPCR"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "5",
        "panel": "F",
        "chart_form": "imaging",
        "scope": "wet_lab",
        "data_source": "",
        "skill_id": null,
        "golden": [
          {
            "metric": "proteostat",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "PROTEOSTAT aggresome assay"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "A",
        "chart_form": "umap",
        "scope": "transcriptomic",
        "data_source": "GSE293984 (scRNA)",
        "skill_id": "annotate",
        "golden": [
          {
            "metric": "n_cell_types",
            "value": 9,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "9 types; Selom set differs by {RGC missing, RPE appears}"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "C",
        "chart_form": "stacked_bar",
        "scope": "transcriptomic",
        "data_source": "GSE293984",
        "skill_id": "composition",
        "golden": [],
        "weight": 1.0,
        "note": "per-sample 9-type composition, rod-dominant (~64.5%); control rows limited by the 1-control deposit — form+claim",
        "status": "pending"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "D",
        "chart_form": "stacked_bar",
        "scope": "transcriptomic",
        "data_source": "GSE293984",
        "skill_id": "composition",
        "golden": [
          {
            "metric": "rod2_fold.LCA1",
            "value": 2.0,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "paper: Rod-2 >=2x in LCA-1 vs Control-1 (continuous fold)"
          },
          {
            "metric": "rod2_fold.MSVUS",
            "value": 2.0,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "paper: Rod-2 >=2x in MS-VUS vs Control-1 (continuous fold)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "E",
        "chart_form": "venn",
        "scope": "transcriptomic",
        "data_source": "GSE293984",
        "skill_id": "gsea",
        "golden": [
          {
            "metric": "rod2_enriched_terms",
            "value": 119,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "enriched GO terms for Rod-2 (engine-sensitive count, RISKS #10)"
          },
          {
            "metric": "allthree_core",
            "value": 52,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "GO terms shared by all three rod subtypes (the 52-term core)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "F",
        "chart_form": "dotplot",
        "scope": "transcriptomic",
        "data_source": "GSE293984",
        "skill_id": "gsea",
        "golden": [
          {
            "metric": "functional_groups",
            "value": 4,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "Rod-2 GO groups: stress/ROS, proteostasis, mito, lipid; Selom hits 3/4 (proteostasis absent)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "rpgrip1",
        "figure": "6",
        "panel": "G",
        "chart_form": "box",
        "scope": "transcriptomic",
        "data_source": "GSE293984",
        "skill_id": "deg",
        "golden": [
          {
            "metric": "n_down_genes",
            "value": 49,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "49-down bulk signature scaled across rods; Rod-1 highest"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      }
    ],
    "validations": [
      {
        "run_id": "captured-5sig",
        "panel_key": "5sig",
        "results": [
          {
            "metric": "universe",
            "golden": 1133,
            "computed": 1133,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "RPGRIP1-associated GO union — reproduced byte-exact"
          },
          {
            "metric": "signature.count",
            "golden": 78,
            "computed": 19,
            "oracle": null,
            "delta": -0.7564102564102564,
            "verdict": "fail",
            "blame": "paper-irreproducible",
            "note": "figures/results say 78; methods say 181 (internal inconsistency)"
          },
          {
            "metric": "signature.down_both",
            "golden": 49,
            "computed": 13,
            "oracle": null,
            "delta": -0.7346938775510204,
            "verdict": "fail",
            "blame": "paper-irreproducible",
            "note": "signature genes down-regulated in BOTH LCA-1 & MS-VUS"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "deterministic_anchor"
        ]
      },
      {
        "run_id": "captured-5C",
        "panel_key": "5C",
        "results": [
          {
            "metric": "RHO.pct_LCA1",
            "golden": -71,
            "computed": -73,
            "oracle": null,
            "delta": -0.028169014084507043,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": ""
          },
          {
            "metric": "RHO.pct_MSVUS",
            "golden": -34,
            "computed": -35,
            "oracle": null,
            "delta": -0.029411764705882353,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": ""
          },
          {
            "metric": "PRPH2.pct_LCA1",
            "golden": -53,
            "computed": -57,
            "oracle": null,
            "delta": -0.07547169811320754,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": ""
          },
          {
            "metric": "PRPH2.pct_MSVUS",
            "golden": -18,
            "computed": -20,
            "oracle": null,
            "delta": -0.1111111111111111,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": ""
          },
          {
            "metric": "RPGR.pct_MSVUS",
            "golden": 59,
            "computed": 56.5,
            "oracle": null,
            "delta": -0.0423728813559322,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": ""
          }
        ],
        "panel_verdict": "close",
        "guards_fired": []
      },
      {
        "run_id": "captured-5D",
        "panel_key": "5D",
        "results": [
          {
            "metric": "PRPH2.ihc",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "PRPH2 immunostaining"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "wet_lab_scope"
        ]
      },
      {
        "run_id": "captured-5E",
        "panel_key": "5E",
        "results": [
          {
            "metric": "rtqpcr",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "independent RT-qPCR"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "wet_lab_scope"
        ]
      },
      {
        "run_id": "captured-5F",
        "panel_key": "5F",
        "results": [
          {
            "metric": "proteostat",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "PROTEOSTAT aggresome assay"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "wet_lab_scope"
        ]
      },
      {
        "run_id": "captured-6A",
        "panel_key": "6A",
        "results": [
          {
            "metric": "n_cell_types",
            "golden": 9,
            "computed": 9,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "9 types; Selom set differs by {RGC missing, RPE appears}"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-6D",
        "panel_key": "6D",
        "results": [
          {
            "metric": "rod2_fold.LCA1",
            "golden": 2.0,
            "computed": 1.8,
            "oracle": null,
            "delta": -0.09999999999999998,
            "verdict": "close",
            "blame": "structural-limit",
            "note": "paper: Rod-2 >=2x in LCA-1 vs Control-1 (continuous fold)"
          },
          {
            "metric": "rod2_fold.MSVUS",
            "golden": 2.0,
            "computed": 1.1,
            "oracle": null,
            "delta": -0.44999999999999996,
            "verdict": "fail",
            "blame": "structural-limit",
            "note": "paper: Rod-2 >=2x in MS-VUS vs Control-1 (continuous fold)"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": []
      },
      {
        "run_id": "captured-6E",
        "panel_key": "6E",
        "results": [
          {
            "metric": "rod2_enriched_terms",
            "golden": 119,
            "computed": 36,
            "oracle": null,
            "delta": -0.6974789915966386,
            "verdict": "fail",
            "blame": "engine-delta",
            "note": "enriched GO terms for Rod-2 (engine-sensitive count, RISKS #10)"
          },
          {
            "metric": "allthree_core",
            "golden": 52,
            "computed": 0,
            "oracle": null,
            "delta": -1.0,
            "verdict": "fail",
            "blame": "upstream-delta",
            "note": "GO terms shared by all three rod subtypes (the 52-term core)"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": []
      },
      {
        "run_id": "captured-6F",
        "panel_key": "6F",
        "results": [
          {
            "metric": "functional_groups",
            "golden": 4,
            "computed": 3,
            "oracle": null,
            "delta": -0.25,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": "Rod-2 GO groups: stress/ROS, proteostasis, mito, lipid; Selom hits 3/4 (proteostasis absent)"
          }
        ],
        "panel_verdict": "close",
        "guards_fired": []
      },
      {
        "run_id": "captured-6G",
        "panel_key": "6G",
        "results": [
          {
            "metric": "n_down_genes",
            "golden": 49,
            "computed": 50,
            "oracle": null,
            "delta": 0.02040816326530612,
            "verdict": "close",
            "blame": "delta-unmeasured",
            "note": "49-down bulk signature scaled across rods; Rod-1 highest"
          }
        ],
        "panel_verdict": "close",
        "guards_fired": []
      }
    ],
    "scorecard": {
      "paper_id": "rpgrip1",
      "n_panels": 13,
      "n_in_scope": 10,
      "totals_by_verdict": {
        "exact": 2,
        "close": 8,
        "fail": 8
      },
      "totals_by_blame": {
        "paper-irreproducible": 2,
        "delta-unmeasured": 7,
        "out-of-scope": 3,
        "structural-limit": 2,
        "engine-delta": 1,
        "upstream-delta": 1
      },
      "findings": {
        "reproduced": 9,
        "paper_irreproducible": 2,
        "structural_limit": 2,
        "engine_delta": 1,
        "upstream_delta": 1,
        "selom_engine_bugs": 0
      },
      "provenance_divergences": [],
      "panel_scores": [
        {
          "panel_key": "5sig",
          "reproducibility": 40,
          "selom_confidence": 100,
          "tier": "irreproducible",
          "color": "#f97316",
          "attribution": "paper",
          "provenance": "",
          "in_scope": true,
          "weight": 2.0,
          "note": ""
        },
        {
          "panel_key": "5C",
          "reproducibility": 84,
          "selom_confidence": 90,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "5D",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (wet_lab) — excluded from the denominator"
        },
        {
          "panel_key": "5E",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (wet_lab) — excluded from the denominator"
        },
        {
          "panel_key": "5F",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (wet_lab) — excluded from the denominator"
        },
        {
          "panel_key": "6A",
          "reproducibility": 92,
          "selom_confidence": 100,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "6D",
          "reproducibility": 38,
          "selom_confidence": 100,
          "tier": "irreproducible",
          "color": "#f97316",
          "attribution": "data",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "6E",
          "reproducibility": 45,
          "selom_confidence": 70,
          "tier": "irreproducible",
          "color": "#f97316",
          "attribution": "data",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "6F",
          "reproducibility": 84,
          "selom_confidence": 90,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "6G",
          "reproducibility": 84,
          "selom_confidence": 90,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        }
      ],
      "score": {
        "paper_id": "rpgrip1",
        "reproducibility": 63,
        "selom_confidence": 92,
        "tier": "deposit-faithful",
        "color": "#f59e0b",
        "n_scored": 7,
        "n_in_scope": 10,
        "n_out_of_scope": 3,
        "n_form_only": 3,
        "coverage": "7 scored / 10 in-scope · 3 out-of-scope · 3 form-only"
      },
      "generated_at": "2026-06-17T16:21:56.167692+00:00"
    }
  },
  "jev": {
    "paper": {
      "id": "jev",
      "slug": "jev",
      "title": "Retinal EV-miRNA driving gliotic responses in degeneration (Cioanca, Natoli et al. 2023, J Extracell Vesicles)",
      "doi": "10.1002/jev2.12393",
      "geo": [
        "GSE153674 (Fadl 2020 reference — the study's own scRNA PRJNA990691 not deposited)"
      ]
    },
    "panels": [
      {
        "paper_id": "jev",
        "figure": "1",
        "panel": "c",
        "chart_form": "heatmap",
        "scope": "transcriptomic",
        "data_source": "Table S1/S2 (OpenArray miRNA)",
        "skill_id": "deg",
        "golden": [
          {
            "metric": "de_up",
            "value": 12,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "upregulated DE miRNAs in ST2 (p<0.05)"
          },
          {
            "metric": "de_down",
            "value": 22,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "downregulated in ST2 (figure says 23)"
          },
          {
            "metric": "de_total",
            "value": 34,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "total DE miRNAs in ST2 (figure says 35)"
          }
        ],
        "weight": 2.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "3",
        "panel": "",
        "chart_form": "volcano",
        "scope": "transcriptomic",
        "data_source": "Table S2",
        "skill_id": "volcano",
        "golden": [
          {
            "metric": "top_mirna",
            "value": "mmu-miR-182-5p",
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "top DE miRNA by p-value (miR-182-5p, miR-183/96/182 cluster)"
          }
        ],
        "weight": 0.5,
        "note": "ST2 differential data recast as a volcano; same data as Fig 1c (the paper shows it as a CDF + MA plot)",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "4",
        "panel": "c",
        "chart_form": "pca",
        "scope": "transcriptomic",
        "data_source": "Table S6 (EV proteome, 2180 × 10)",
        "skill_id": "pca",
        "golden": [
          {
            "metric": "pc1_var",
            "value": 39.8,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": "PC1 variance; Selom 39.7%"
          },
          {
            "metric": "pc2_var",
            "value": 18.5,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": "PC2 variance; Selom 18.5%"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "4",
        "panel": "d",
        "chart_form": "heatmap",
        "scope": "transcriptomic",
        "data_source": "Table S6",
        "skill_id": "heatmap",
        "golden": [
          {
            "metric": "n_proteins",
            "value": 50,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "top-50 DE proteins, z-scored, hierarchically clustered"
          }
        ],
        "weight": 0.5,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "4",
        "panel": "e",
        "chart_form": "volcano",
        "scope": "transcriptomic",
        "data_source": "Table S6",
        "skill_id": "deg",
        "golden": [
          {
            "metric": "de_up",
            "value": 172,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "upregulated in the deposited ST6 (p<0.05); figure shows 61"
          },
          {
            "metric": "de_down",
            "value": 275,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "downregulated in ST6 (p<0.05); figure shows 119"
          },
          {
            "metric": "de_total",
            "value": 447,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "total DE in ST6 (p<0.05); figure shows 180"
          },
          {
            "metric": "top_up_protein",
            "value": "B2M",
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "B2M — the figure's labeled top up-regulated hit (matches ST6)"
          }
        ],
        "weight": 2.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "5",
        "panel": "D",
        "chart_form": "heatmap",
        "scope": "transcriptomic",
        "data_source": "Table S5 × Table S10",
        "skill_id": "heatmap",
        "golden": [
          {
            "metric": "n_ev_proteins",
            "value": 28,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "ESCRT (PDCD6IP, CHMP2A/4B/5/6, IST1) + RNA-loading (AGO1, HNRNPA2B1) EV-biogenesis mediators"
          }
        ],
        "weight": 0.5,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "6",
        "panel": "a",
        "chart_form": "stacked_area",
        "scope": "transcriptomic",
        "data_source": "Table S8",
        "skill_id": "composition",
        "golden": [
          {
            "metric": "muller_dr_pct",
            "value": 2.61,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": "Müller glia, DR EV"
          },
          {
            "metric": "muller_pd_pct",
            "value": 22.25,
            "unit": "%",
            "source": "figure",
            "confidence": 1.0,
            "note": "Müller glia, PD EV — largest contribution increase (Fig 6b)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "8",
        "panel": "a",
        "chart_form": "umap",
        "scope": "data_not_deposited",
        "data_source": "Fadl 2020 GSE153674 (reference, not the study)",
        "skill_id": "umap_scrna",
        "golden": [
          {
            "metric": "a",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "cell-type UMAP (Fig 8a) — pipeline demo, no paper data"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "8",
        "panel": "ann",
        "chart_form": "umap",
        "scope": "data_not_deposited",
        "data_source": "Fadl 2020 GSE153674 (reference, not the study)",
        "skill_id": "annotate",
        "golden": [
          {
            "metric": "ann",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "marker-score annotation (Fig 8a) — pipeline demo, no paper data"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "8",
        "panel": "d",
        "chart_form": "dotplot",
        "scope": "data_not_deposited",
        "data_source": "Fadl 2020 GSE153674 (reference, not the study)",
        "skill_id": "markers",
        "golden": [
          {
            "metric": "d",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "marker dotplot (Fig 8d) — pipeline demo, no paper data"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "jev",
        "figure": "8",
        "panel": "e",
        "chart_form": "trajectory",
        "scope": "data_not_deposited",
        "data_source": "Fadl 2020 GSE153674 (reference, not the study)",
        "skill_id": "trajectory",
        "golden": [
          {
            "metric": "e",
            "value": 1,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "pseudotime trajectory (Fig 8e) — pipeline demo, no paper data"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      }
    ],
    "validations": [
      {
        "run_id": "captured-1c",
        "panel_key": "1c",
        "results": [
          {
            "metric": "de_up",
            "golden": 12,
            "computed": 12,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "upregulated DE miRNAs in ST2 (p<0.05)"
          },
          {
            "metric": "de_down",
            "golden": 22,
            "computed": 22,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "downregulated in ST2 (figure says 23)"
          },
          {
            "metric": "de_total",
            "golden": 34,
            "computed": 34,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "total DE miRNAs in ST2 (figure says 35)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-3",
        "panel_key": "3",
        "results": [
          {
            "metric": "top_mirna",
            "golden": "mmu-miR-182-5p",
            "computed": "mmu-miR-182-5p",
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "top DE miRNA by p-value (miR-182-5p, miR-183/96/182 cluster)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-4c",
        "panel_key": "4c",
        "results": [
          {
            "metric": "pc1_var",
            "golden": 39.8,
            "computed": 39.7,
            "oracle": null,
            "delta": -0.002512562814070209,
            "verdict": "exact",
            "blame": null,
            "note": "PC1 variance; Selom 39.7%"
          },
          {
            "metric": "pc2_var",
            "golden": 18.5,
            "computed": 18.5,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "PC2 variance; Selom 18.5%"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-4d",
        "panel_key": "4d",
        "results": [
          {
            "metric": "n_proteins",
            "golden": 50,
            "computed": 50,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "top-50 DE proteins, z-scored, hierarchically clustered"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-4e",
        "panel_key": "4e",
        "results": [
          {
            "metric": "de_up",
            "golden": 172,
            "computed": 172,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "upregulated in the deposited ST6 (p<0.05); figure shows 61"
          },
          {
            "metric": "de_down",
            "golden": 275,
            "computed": 275,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "downregulated in ST6 (p<0.05); figure shows 119"
          },
          {
            "metric": "de_total",
            "golden": 447,
            "computed": 447,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "total DE in ST6 (p<0.05); figure shows 180"
          },
          {
            "metric": "top_up_protein",
            "golden": "B2M",
            "computed": "B2M",
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "B2M — the figure's labeled top up-regulated hit (matches ST6)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-5D",
        "panel_key": "5D",
        "results": [
          {
            "metric": "n_ev_proteins",
            "golden": 28,
            "computed": 28,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "ESCRT (PDCD6IP, CHMP2A/4B/5/6, IST1) + RNA-loading (AGO1, HNRNPA2B1) EV-biogenesis mediators"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-6a",
        "panel_key": "6a",
        "results": [
          {
            "metric": "muller_dr_pct",
            "golden": 2.61,
            "computed": 2.61,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "Müller glia, DR EV"
          },
          {
            "metric": "muller_pd_pct",
            "golden": 22.25,
            "computed": 22.25,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "Müller glia, PD EV — largest contribution increase (Fig 6b)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-8a",
        "panel_key": "8a",
        "results": [
          {
            "metric": "a",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "cell-type UMAP (Fig 8a) — pipeline demo, no paper data"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "data_not_deposited"
        ]
      },
      {
        "run_id": "captured-8ann",
        "panel_key": "8ann",
        "results": [
          {
            "metric": "ann",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "marker-score annotation (Fig 8a) — pipeline demo, no paper data"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "data_not_deposited"
        ]
      },
      {
        "run_id": "captured-8d",
        "panel_key": "8d",
        "results": [
          {
            "metric": "d",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "marker dotplot (Fig 8d) — pipeline demo, no paper data"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "data_not_deposited"
        ]
      },
      {
        "run_id": "captured-8e",
        "panel_key": "8e",
        "results": [
          {
            "metric": "e",
            "golden": 1,
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "pseudotime trajectory (Fig 8e) — pipeline demo, no paper data"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "data_not_deposited"
        ]
      }
    ],
    "scorecard": {
      "paper_id": "jev",
      "n_panels": 11,
      "n_in_scope": 7,
      "totals_by_verdict": {
        "exact": 14,
        "close": 0,
        "fail": 4
      },
      "totals_by_blame": {
        "out-of-scope": 4
      },
      "findings": {
        "reproduced": 14,
        "paper_irreproducible": 0,
        "structural_limit": 0,
        "engine_delta": 0,
        "upstream_delta": 0,
        "selom_engine_bugs": 0
      },
      "provenance_divergences": [
        "4e: ST6+ Fig4e−"
      ],
      "panel_scores": [
        {
          "panel_key": "1c",
          "reproducibility": 92,
          "selom_confidence": 100,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "ST2+ Fig1c+",
          "in_scope": true,
          "weight": 2.0,
          "note": ""
        },
        {
          "panel_key": "3",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "ST2+ Fig3+",
          "in_scope": true,
          "weight": 0.5,
          "note": ""
        },
        {
          "panel_key": "4c",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "ST6+ Fig4c+",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "4d",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "ST6+ Fig4d+",
          "in_scope": true,
          "weight": 0.5,
          "note": ""
        },
        {
          "panel_key": "4e",
          "reproducibility": 58,
          "selom_confidence": 100,
          "tier": "deposit-faithful",
          "color": "#f59e0b",
          "attribution": "paper",
          "provenance": "ST6+ Fig4e−",
          "in_scope": true,
          "weight": 2.0,
          "note": ""
        },
        {
          "panel_key": "5D",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "ST5+ ST10+ Fig5D+",
          "in_scope": true,
          "weight": 0.5,
          "note": ""
        },
        {
          "panel_key": "6a",
          "reproducibility": 92,
          "selom_confidence": 100,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "ST8+ Fig6+",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "8a",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "GSE153674+ Fig8−",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (data_not_deposited) — excluded from the denominator"
        },
        {
          "panel_key": "8ann",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "GSE153674+ Fig8−",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (data_not_deposited) — excluded from the denominator"
        },
        {
          "panel_key": "8d",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "GSE153674+ Fig8−",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (data_not_deposited) — excluded from the denominator"
        },
        {
          "panel_key": "8e",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "GSE153674+ Fig8−",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (data_not_deposited) — excluded from the denominator"
        }
      ],
      "score": {
        "paper_id": "jev",
        "reproducibility": 86,
        "selom_confidence": 100,
        "tier": "reproduced",
        "color": "#22c55e",
        "n_scored": 7,
        "n_in_scope": 7,
        "n_out_of_scope": 4,
        "n_form_only": 0,
        "coverage": "7 scored / 7 in-scope · 4 out-of-scope"
      },
      "generated_at": "2026-06-17T16:21:56.169713+00:00"
    }
  },
  "hani": {
    "paper": {
      "id": "hani",
      "slug": "hani",
      "title": "Comprehensive characterization of fetal and mature retinal cell identity to assess the fidelity of retinal organoids (Kim, Gonzalez-Cordero, Yang et al. 2023, Stem Cell Reports)",
      "doi": "10.1016/j.stemcr.2022.12.002",
      "geo": [
        "GSE201356"
      ]
    },
    "panels": [
      {
        "paper_id": "hani",
        "figure": "1",
        "panel": "D",
        "chart_form": "stacked_bar",
        "scope": "transcriptomic",
        "data_source": "GSE201356 + curated public retinal scRNA-seq",
        "skill_id": "composition",
        "golden": [
          {
            "metric": "n_cell_types",
            "value": 9,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "major retinal cell types in the reference atlas (mmc2 columns)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "hani",
        "figure": "2",
        "panel": "A",
        "chart_form": "corr_heatmap",
        "scope": "transcriptomic",
        "data_source": "Cepo gene statistics per cell type x dataset/batch",
        "skill_id": "corr_heatmap",
        "golden": [
          {
            "metric": "n_cell_type_groups",
            "value": 9,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "correlation blocks group by cell type (vision-read structure)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "hani",
        "figure": "2",
        "panel": "C",
        "chart_form": "box",
        "scope": "transcriptomic",
        "data_source": "mean correlation of cell-identity statistics per dataset pair",
        "skill_id": "box",
        "golden": [
          {
            "metric": "top_method",
            "value": "Cepo",
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "most concordant cell-identity method (directional)"
          }
        ],
        "weight": 0.5,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "hani",
        "figure": "3",
        "panel": "B",
        "chart_form": "upset",
        "scope": "transcriptomic",
        "data_source": "mmc2.csv (Cepo marker matrix, 405 genes x 9 cell types)",
        "skill_id": "upset",
        "golden": [
          {
            "metric": "markers_per_type",
            "value": 50,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "top-50 Cepo cell-identity genes per type"
          },
          {
            "metric": "n_marker_genes",
            "value": 405,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "unique cell-identity genes in mmc2"
          },
          {
            "metric": "n_type_specific",
            "value": 360,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "genes marking exactly 1 cell type (UpSet)"
          },
          {
            "metric": "n_shared",
            "value": 45,
            "unit": "",
            "source": "extracted",
            "confidence": 1.0,
            "note": "genes marking exactly 2 cell types (UpSet)"
          }
        ],
        "weight": 2.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "hani",
        "figure": "6",
        "panel": "D",
        "chart_form": "micrograph",
        "scope": "wet_lab",
        "data_source": "immunohistochemistry (mmc3 antibodies)",
        "skill_id": "",
        "golden": [
          {
            "metric": "ihc",
            "value": "confirmed",
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "protein-level marker validation — out of scope (guard 7)"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      },
      {
        "paper_id": "hani",
        "figure": "6",
        "panel": "E",
        "chart_form": "umap",
        "scope": "transcriptomic",
        "data_source": "GSE201356 organoid scRNA-seq (West et al. 2022 protocol)",
        "skill_id": "umap_scrna",
        "golden": [
          {
            "metric": "n_organoids",
            "value": 15,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "n = 15 organoids"
          },
          {
            "metric": "n_batches",
            "value": 3,
            "unit": "",
            "source": "figure",
            "confidence": 1.0,
            "note": "N = 3 differentiation batches"
          }
        ],
        "weight": 1.0,
        "note": "",
        "status": "validated"
      }
    ],
    "validations": [
      {
        "run_id": "captured-1D",
        "panel_key": "1D",
        "results": [
          {
            "metric": "n_cell_types",
            "golden": 9,
            "computed": 9,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "major retinal cell types in the reference atlas (mmc2 columns)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-2A",
        "panel_key": "2A",
        "results": [
          {
            "metric": "n_cell_type_groups",
            "golden": 9,
            "computed": 9,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "correlation blocks group by cell type (vision-read structure)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-2C",
        "panel_key": "2C",
        "results": [
          {
            "metric": "top_method",
            "golden": "Cepo",
            "computed": "Cepo",
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "most concordant cell-identity method (directional)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-3B",
        "panel_key": "3B",
        "results": [
          {
            "metric": "markers_per_type",
            "golden": 50,
            "computed": 50,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "top-50 Cepo cell-identity genes per type"
          },
          {
            "metric": "n_marker_genes",
            "golden": 405,
            "computed": 405,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "unique cell-identity genes in mmc2"
          },
          {
            "metric": "n_type_specific",
            "golden": 360,
            "computed": 360,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "genes marking exactly 1 cell type (UpSet)"
          },
          {
            "metric": "n_shared",
            "golden": 45,
            "computed": 45,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "genes marking exactly 2 cell types (UpSet)"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      },
      {
        "run_id": "captured-6D",
        "panel_key": "6D",
        "results": [
          {
            "metric": "ihc",
            "golden": "confirmed",
            "computed": null,
            "oracle": null,
            "delta": null,
            "verdict": "fail",
            "blame": "out-of-scope",
            "note": "protein-level marker validation — out of scope (guard 7)"
          }
        ],
        "panel_verdict": "fail",
        "guards_fired": [
          "wet_lab_out_of_scope"
        ]
      },
      {
        "run_id": "captured-6E",
        "panel_key": "6E",
        "results": [
          {
            "metric": "n_organoids",
            "golden": 15,
            "computed": 15,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "n = 15 organoids"
          },
          {
            "metric": "n_batches",
            "golden": 3,
            "computed": 3,
            "oracle": null,
            "delta": 0.0,
            "verdict": "exact",
            "blame": null,
            "note": "N = 3 differentiation batches"
          }
        ],
        "panel_verdict": "exact",
        "guards_fired": []
      }
    ],
    "scorecard": {
      "paper_id": "hani",
      "n_panels": 6,
      "n_in_scope": 5,
      "totals_by_verdict": {
        "exact": 9,
        "close": 0,
        "fail": 1
      },
      "totals_by_blame": {
        "out-of-scope": 1
      },
      "findings": {
        "reproduced": 9,
        "paper_irreproducible": 0,
        "structural_limit": 0,
        "engine_delta": 0,
        "upstream_delta": 0,
        "selom_engine_bugs": 0
      },
      "provenance_divergences": [],
      "panel_scores": [
        {
          "panel_key": "1D",
          "reproducibility": 92,
          "selom_confidence": 100,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "GSE201356+ Fig1D+",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "2A",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "Fig2A+",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        },
        {
          "panel_key": "2C",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "Fig2C+",
          "in_scope": true,
          "weight": 0.5,
          "note": ""
        },
        {
          "panel_key": "3B",
          "reproducibility": 92,
          "selom_confidence": 100,
          "tier": "reproduced",
          "color": "#22c55e",
          "attribution": "selom",
          "provenance": "mmc2+ Fig3+",
          "in_scope": true,
          "weight": 2.0,
          "note": ""
        },
        {
          "panel_key": "6D",
          "reproducibility": null,
          "selom_confidence": null,
          "tier": "out-of-scope",
          "color": "#9ca3af",
          "attribution": "data",
          "provenance": "Fig6D+",
          "in_scope": false,
          "weight": 1.0,
          "note": "out of scope (wet_lab) — excluded from the denominator"
        },
        {
          "panel_key": "6E",
          "reproducibility": 100,
          "selom_confidence": 100,
          "tier": "verified",
          "color": "#15803d",
          "attribution": "selom",
          "provenance": "GSE201356+ Fig6E+",
          "in_scope": true,
          "weight": 1.0,
          "note": ""
        }
      ],
      "score": {
        "paper_id": "hani",
        "reproducibility": 96,
        "selom_confidence": 100,
        "tier": "verified",
        "color": "#15803d",
        "n_scored": 5,
        "n_in_scope": 5,
        "n_out_of_scope": 1,
        "n_form_only": 0,
        "coverage": "5 scored / 5 in-scope · 1 out-of-scope"
      },
      "generated_at": "2026-06-17T16:21:56.170717+00:00"
    }
  }
};
