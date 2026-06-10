import { http, HttpResponse } from "msw";
import { stubUmapFigure } from "./stub-figure";

// Mirrors the live contract from app/backend/main.py:
//   POST /skills/{skill_id}/run  (multipart field "matrix")
//   -> { "figure": { data, layout } }
// The frontend calls it through the /api/* proxy, so we intercept the proxied path.
export const handlers = [
  http.post("/api/skills/:skillId/run", async () => {
    // A real upload would parse `matrix`; the stub is input-independent by design,
    // so we just return the canned figure (same as the backend stub run.py).
    return HttpResponse.json({ figure: stubUmapFigure() });
  }),
];
