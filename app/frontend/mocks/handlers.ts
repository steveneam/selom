import { http, HttpResponse } from "msw";
import { CATALOG } from "@/lib/catalog/seed";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { stubUmapFigure } from "./stub-figure";
import { mockBundle, mockDataCheck, mockDataFit, mockLegend, mockTable } from "./stub-bundle";
import { compileFixture, getFixtureSet, searchFixture } from "./gene-sets-fixture";
import { EXPORT_PRESETS, mockExportFile } from "./export-fixture";
import { FIGURE_STYLES, mockApplyStyle } from "./styles-fixture";
import { mockExtractChart } from "./extract-fixture";
import { mockInspect } from "./data-inspect-fixture";
import { SKILL_PARAM_SPECS } from "./skill-spec-fixture";
import { persistenceHandlers } from "./persistence-handlers";
import { mockExplain, mockGaps, mockHelperTurn, mockSweepSuggestions } from "./ai-fixture";
import type { AiAction, AiActionDelta } from "@/lib/ai/types";
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
  // Per-skill describe (P2.5c): the backend serves the full SkillSpec here, but the FE
  // only reads `param_spec` to build the spec-driven param controls. Mirror that with the
  // offline param-spec fixture; an unknown skill yields an empty spec (no controls).
  http.get("/api/skills/:skillId", ({ params }) => {
    const id = String(params.skillId);
    return HttpResponse.json({ id, param_spec: SKILL_PARAM_SPECS[id] ?? {} });
  }),
  // Auto-tune (Layer A, docs/auto-tune/spec.md): the DETERMINISTIC best-practice params for a skill.
  // Mirrors the backend WIRE (engine/recommend.py) — baseline = the param-spec defaults + the one
  // curated rule (umap_scrna/cluster n_hvg → ~2000). Content is verified on the real backend, not here
  // ([[selom-mock-is-wire-only-verify-real]]); this proves the shape for dev:mock + vitest.
  http.post("/api/skills/:skillId/recommend-params", ({ params }) => {
    const id = String(params.skillId);
    const spec = SKILL_PARAM_SPECS[id];
    if (!spec) return new HttpResponse(null, { status: 404 });
    const recs = Object.entries(spec).map(([key, entry]) => {
      const def = (entry as { default: string | number | boolean }).default;
      if ((id === "umap_scrna" || id === "cluster") && key === "n_hvg") {
        return { key, value: 2000, default: def, scaled: true,
          why: "select the top ~2000 highly-variable genes before PCA (standard scRNA practice)" };
      }
      return { key, value: def, default: def, why: "skill default", scaled: false };
    });
    const n = recs.filter((r) => r.scaled).length;
    return HttpResponse.json({
      skill_id: id,
      recs,
      note: n
        ? `Set ${n} best-practice input${n === 1 ? "" : "s"} for your data — review below, then re-run.`
        : "These are the best-practice defaults for this skill.",
    });
  }),
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
  // Chart extractor (X4 calibration picker): recover a panel's series from an image +
  // axis calibration. The live backend reads the actual image; the mock returns a
  // representative recovered series so the picker's full flow renders offline. 400 when
  // the calibration is missing, mirroring extract/chart_intake.calibration_from_params.
  http.post("/api/extract/chart", ({ request }) => {
    const url = new URL(request.url);
    if (!url.searchParams.get("x_px0")) {
      return HttpResponse.json({ detail: "missing calibration param 'x_px0'" }, { status: 400 });
    }
    return HttpResponse.json(mockExtractChart(url.searchParams.get("form") ?? "bar", url.searchParams));
  }),
  // Engine front door (P1): the layered data-type profile + dynamic cleaning plan. The mock reads
  // only the CSV header, so it matches the live engine's CLASSIFICATION (esp. ERG → no gene
  // cleaning) offline; matrix deltas are omitted (verify real content against the live backend).
  http.post("/api/data/inspect", async ({ request }) => {
    const url = new URL(request.url);
    const override = url.searchParams.get("profile") || url.searchParams.get("hint") || undefined;
    let filename = "data.csv";
    let header = "";
    try {
      const fd = await request.formData();
      const f = fd.get("matrix");
      if (f instanceof File) {
        filename = f.name;
        header = (await f.text()).split(/\r?\n/)[0] ?? "";
      }
    } catch {
      /* no body / unreadable — fall through to the generic-table default */
    }
    return HttpResponse.json(mockInspect(filename, header, override));
  }),
  // C6 multi-file combine: merge several single-condition ERG files into one canonical table. The
  // mock concatenates the uploaded files' rows (header from the first) + returns the X-Combine-
  // Summary header the FE reads; real content is verified against the live backend, not here.
  http.post("/api/data/combine", async ({ request }) => {
    let names: string[] = [];
    let header = "sample_id,condition,intensity_group,time_ms,voltage_uv,role,condition_order";
    const bodies: string[] = [];
    try {
      const fd = await request.formData();
      const files = fd.getAll("files").filter((f): f is File => f instanceof File);
      names = files.map((f) => f.name);
      for (let i = 0; i < files.length; i++) {
        const lines = (await files[i].text()).split(/\r?\n/).filter(Boolean);
        if (i === 0 && lines[0]) header = lines[0];
        bodies.push(...lines.slice(1));
      }
    } catch {
      /* no body — return a minimal stub */
    }
    const conditions = Array.from(new Set(names.map((n) => n.replace(/\.[^.]+$/, "")))).slice(0, 8);
    const summary = {
      filename: `combined_${names.length}_files.csv`,
      n_files: names.length,
      conditions,
      rows: bodies.length,
      columns: header.split(","),
      per_condition_n: Object.fromEntries(conditions.map((c) => [c, 1])),
    };
    return new HttpResponse([header, ...bodies].join("\n"), {
      headers: { "Content-Type": "text/csv", "X-Combine-Summary": JSON.stringify(summary) },
    });
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
      figure_legend: mockLegend(skillId),
      data_check: mockDataCheck(query),
      data_fit: mockDataFit(skillId),
    });
  }),
  // AI Action Gateway (S5) — mirrors app/backend/routers/ai.py. The stubs return a representative
  // non-empty HelperTurn so the dev:mock UI loop is demonstrable; the real gateway is OFF by default.
  http.post("/api/ai/propose", async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as {
      skill_id?: string | null;
      goal?: string;
      params?: Record<string, unknown>;
    };
    return HttpResponse.json(mockHelperTurn(body.skill_id ?? null, body.goal ?? "", body.params ?? {}));
  }),
  http.post("/api/ai/apply", async ({ request }) => {
    const fd = await request.formData();
    const skillId = String(fd.get("skill_id") ?? "umap_scrna");
    // /ai/apply sends `params` as a JSON object (the FINAL approved params), NOT a query string —
    // parse it as JSON so provenance.params reflects the applied values (e.g. n_neighbors → 30).
    let params: Record<string, string> = {};
    try {
      params = JSON.parse(String(fd.get("params") ?? "{}"));
    } catch {
      /* malformed → empty */
    }
    let delta: AiActionDelta[] = [];
    try {
      delta = JSON.parse(String(fd.get("ai_actions") ?? "[]")) as AiActionDelta[];
    } catch {
      /* malformed → empty */
    }
    // Mirror the 400 the backend raises on an empty/missing ai_actions delta.
    if (!Array.isArray(delta) || delta.length === 0) {
      return HttpResponse.json(
        { detail: "/ai/apply requires a non-empty ai_actions log (the approved action delta)" },
        { status: 400 },
      );
    }
    const bundle = mockBundle(skillId, params as Record<string, string>);
    // Mirror the NEXT#1 chokepoint: the SERVER stamps the trusted attribution — the posted delta carries
    // only {action_id, type, target, prompt}; actor/model/approved_by/approved_at are derived here, never
    // echoed from the client (a client cannot forge a provenance tag). See docs/provenance-chokepoint/spec.md.
    const actions: AiAction[] = delta.map((d) => ({
      action_id: String(d.action_id ?? ""),
      actor: "ai",
      type: String(d.type ?? ""),
      target: String(d.target ?? ""),
      prompt: String(d.prompt ?? ""),
      model: "mock-gateway",
      approved_by: "dev-user",
      approved_at: "2026-06-30T00:00:00+00:00",
    }));
    bundle.provenance = { ...bundle.provenance, actions };
    return HttpResponse.json({
      figure: stubUmapFigure(),
      ...bundle,
      table: mockTable(skillId, params as Record<string, string>),
      figure_legend: mockLegend(skillId),
      data_check: mockDataCheck(params as Record<string, string>),
      data_fit: mockDataFit(skillId),
    });
  }),
  http.get("/api/ai/gaps", () => HttpResponse.json(mockGaps())),
  http.post("/api/ai/explain", async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as {
      request?: string;
      scorecard?: Record<string, unknown>;
      sweep_space?: Record<string, unknown>;
    };
    const req = body.request ?? "explain_score";
    return HttpResponse.json({
      request: req,
      text: mockExplain(req, body),
      source: "deterministic",
      suggestions: req === "propose_sweep" ? mockSweepSuggestions(body.sweep_space) : [],
    });
  }),
  // 7c FE-state persistence (projectStore/workspaceStore optimistic writes + reconcile GETs).
  // Spread last: the specific /api/figures/* and /api/gene-sets routes above win on overlap.
  ...persistenceHandlers,
];
