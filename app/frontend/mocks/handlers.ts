import { http, HttpResponse } from "msw";
import { CATALOG } from "@/lib/catalog/seed";
import { stubUmapFigure } from "./stub-figure";

// Mirrors the live contract from app/backend/main.py:
//   GET  /skills                 -> SkillCatalogEntry[]  (live registry, B3)
//   POST /skills/{skill_id}/run  (multipart field "matrix") -> { "figure": { data, layout } }
// The frontend calls these through the /api/* proxy, so we intercept the proxied paths.
export const handlers = [
  // Live registry: the Selom-native Verified slice, mirroring the 7 skills the backend
  // actually serves (proteomics_volcano has no runner yet, so it's not Verified).
  http.get("/api/skills", () =>
    HttpResponse.json(
      CATALOG.filter((s) => s.source === "selom" && s.id !== "selom.proteomics_volcano"),
    ),
  ),
  http.post("/api/skills/:skillId/run", async () => {
    // A real upload would parse `matrix`; the stub is input-independent by design,
    // so we just return the canned figure (same as the backend stub run.py).
    return HttpResponse.json({ figure: stubUmapFigure() });
  }),
];
