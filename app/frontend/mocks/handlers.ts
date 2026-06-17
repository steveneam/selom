import { http, HttpResponse } from "msw";
import { CATALOG } from "@/lib/catalog/seed";
import type { FigureSpec } from "@/lib/figure-spec";
import { stubUmapFigure } from "./stub-figure";
import { mockBundle, mockTable } from "./stub-bundle";
import { compileFixture, getFixtureSet, searchFixture } from "./gene-sets-fixture";
import { EXPORT_PRESETS, mockExportFile } from "./export-fixture";
import { FIGURE_STYLES, mockApplyStyle } from "./styles-fixture";
import { REPRO_LEDGERS, REPRO_PAPERS } from "@/lib/reproduction/fixture";

// Mirrors the live contract from app/backend/main.py:
//   GET  /skills                 -> SkillCatalogEntry[]  (live registry, B3)
//   POST /skills/{skill_id}/run  (multipart field "matrix")
//       -> { figure, provenance, methods }   (publish-confidence bundle, B4)
// The frontend calls these through the /api/* proxy, so we intercept the proxied paths.
export const handlers = [
  // Live registry: the Selom-native Verified slice, mirroring the skills the backend
  // actually serves (every Selom-native entry now has a runner).
  http.get("/api/skills", () =>
    HttpResponse.json(CATALOG.filter((s) => s.source === "selom")),
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
  // Journal figure export (B4): presets catalog + a per-format file download. The
  // mock returns a placeholder file (no Chrome in dev:mock) so the menu's download
  // flow is verifiable offline; the real backend renders the figure via Kaleido.
  http.get("/api/figures/export/presets", () => HttpResponse.json({ presets: EXPORT_PRESETS })),
  http.post("/api/figures/export", async ({ request }) => {
    const body = (await request.json()) as { format?: string; filename?: string };
    const format = body.format ?? "png";
    const { body: file, type } = mockExportFile(format);
    return new HttpResponse(file, {
      headers: {
        "Content-Type": type,
        "Content-Disposition": `attachment; filename="${body.filename ?? "selom-figure"}.${format}"`,
      },
    });
  }),
  // Journal styles (journal-styles v1): the style catalog + a live restyle. The mock
  // remaps palette/font/bg so the editor preview visibly changes offline; the real
  // backend runs the full theme transform.
  http.get("/api/figures/styles", () => HttpResponse.json({ styles: FIGURE_STYLES })),
  http.post("/api/figures/style/apply", async ({ request }) => {
    const body = (await request.json()) as { figure?: FigureSpec; style?: string };
    if (!body.figure?.data) return new HttpResponse(null, { status: 400 });
    return HttpResponse.json({ figure: mockApplyStyle(body.figure, body.style ?? "selom") });
  }),
  // Reproduction view (read-only, R5): the 3-paper reproducibility spectrum + each
  // paper's full driven ledger. The fixture is the real engine output, so dev:mock and
  // the live backend render identically.
  http.get("/api/papers", () => HttpResponse.json({ papers: REPRO_PAPERS })),
  http.get("/api/papers/:slug", ({ params }) => {
    const led = REPRO_LEDGERS[String(params.slug)];
    return led ? HttpResponse.json(led) : new HttpResponse(null, { status: 404 });
  }),
  http.get("/api/papers/:slug/scorecard", ({ params }) => {
    const led = REPRO_LEDGERS[String(params.slug)];
    return led?.scorecard
      ? HttpResponse.json(led.scorecard)
      : new HttpResponse(null, { status: 404 });
  }),
  http.post("/api/skills/:skillId/run", async ({ params, request }) => {
    // A real upload would parse `matrix`; the stub is input-independent by design,
    // so we return the canned figure (same as the backend stub run.py) plus a
    // representative B4 bundle so the publish-confidence panel renders offline too.
    const skillId = String(params.skillId);
    const query = Object.fromEntries(new URL(request.url).searchParams.entries());
    return HttpResponse.json({
      figure: stubUmapFigure(),
      ...mockBundle(skillId, query),
      table: mockTable(skillId, query),
    });
  }),
];
