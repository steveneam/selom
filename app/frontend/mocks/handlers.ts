import { http, HttpResponse } from "msw";
import { CATALOG } from "@/lib/catalog/seed";
import { stubUmapFigure } from "./stub-figure";
import { mockBundle } from "./stub-bundle";
import { compileFixture, getFixtureSet, searchFixture } from "./gene-sets-fixture";

// Mirrors the live contract from app/backend/main.py:
//   GET  /skills                 -> SkillCatalogEntry[]  (live registry, B3)
//   POST /skills/{skill_id}/run  (multipart field "matrix")
//       -> { figure, provenance, methods }   (publish-confidence bundle, B4)
// The frontend calls these through the /api/* proxy, so we intercept the proxied paths.
export const handlers = [
  // Live registry: the Selom-native Verified slice, mirroring the 7 skills the backend
  // actually serves (proteomics_volcano has no runner yet, so it's not Verified).
  http.get("/api/skills", () =>
    HttpResponse.json(
      CATALOG.filter((s) => s.source === "selom" && s.id !== "selom.proteomics_volcano"),
    ),
  ),
  // Gene-set catalog (gene-set builder Phase A): search + members from the offline fixture.
  http.get("/api/gene-sets", ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const source = url.searchParams.get("source");
    const limit = Number(url.searchParams.get("limit") ?? 60);
    return HttpResponse.json(searchFixture(q, source, limit));
  }),
  http.post("/api/gene-sets/compile", async ({ request }) => {
    const body = (await request.json()) as { set_ids?: string[]; op?: string; name?: string };
    if (!body.set_ids?.length) return new HttpResponse(null, { status: 400 });
    return HttpResponse.json(compileFixture(body.set_ids, body.op ?? "union", body.name));
  }),
  http.get("/api/gene-sets/:id", ({ params }) => {
    const set = getFixtureSet(String(params.id));
    return set ? HttpResponse.json(set) : new HttpResponse(null, { status: 404 });
  }),
  http.post("/api/skills/:skillId/run", async ({ params, request }) => {
    // A real upload would parse `matrix`; the stub is input-independent by design,
    // so we return the canned figure (same as the backend stub run.py) plus a
    // representative B4 bundle so the publish-confidence panel renders offline too.
    const skillId = String(params.skillId);
    const query = Object.fromEntries(new URL(request.url).searchParams.entries());
    return HttpResponse.json({ figure: stubUmapFigure(), ...mockBundle(skillId, query) });
  }),
];
