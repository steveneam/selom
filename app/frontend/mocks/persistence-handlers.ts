import { http, HttpResponse } from "msw";

/**
 * MSW handlers for the 7c FE-state persistence layer (projectStore + workspaceStore + the
 * one-time local-state import).
 *
 * The 7c migration made the stores API-backed: a mutator applies to the in-memory cache
 * synchronously, then a background write queue (`lib/api/write-queue.ts`) drives the durable
 * write — and ROLLS BACK the optimistic row on a *permanent* failure (a 4xx the user can't fix;
 * see `ApiError.permanent` + `addFigure`'s `onPermanentFail`). Before this module, dev:mock /
 * e2e had no handlers for these endpoints, so every optimistic create got an unhandled-route 4xx
 * → permanent-fail → the just-created figure was deleted, orphaning `activeFigureId`. A
 * demo-deep-link run then rendered a figure whose `activeFigure` never resolved, so the
 * Figure-data stage, VersionBar, and staleness (all keyed off it) were unreachable — and the
 * gesture tests only passed by racing the rollback. [[verify-on-real-data-not-mock]]
 *
 * The real backend honours **client-authoritative ids** (the FE mints the uuid; the backend
 * stores it verbatim — sub-spec §7c, no temp-id remap), so the faithful mock simply ACKS every
 * write and returns EMPTY reconcile collections — the store's `mergeById` keeps its optimistic +
 * seed rows. Mock mode is then behaviourally identical to the deployed API for the
 * create → persist → reconcile loop, so a created figure stays addressable.
 */

const ok = () => HttpResponse.json({ ok: true });

export const persistenceHandlers = [
  // ── reconcile GETs (the server "authority" view) — empty so the store keeps its optimistic
  //    in-flight rows + the local seed (union merge, server-wins-by-id only on a collision).
  http.get("/api/projects", () => HttpResponse.json({ projects: [] })),
  http.get("/api/datasets", () => HttpResponse.json({ datasets: [] })),
  http.get("/api/figures", () => HttpResponse.json({ figures: [] })),
  http.get("/api/skill-installs", () => HttpResponse.json({ installs: [] })),
  http.get("/api/workspace/papers", () => HttpResponse.json({ papers: [] })),
  http.get("/api/workspace/gene-sets", () => HttpResponse.json({ gene_sets: [] })),

  // ── projectStore writes — ack (client-authoritative ids, no remap → no rollback).
  http.post("/api/projects", ok),
  http.patch("/api/projects/:id", ok),
  http.delete("/api/projects/:id", ok),
  http.post("/api/datasets", ok),
  http.patch("/api/datasets/:id", ok),
  http.delete("/api/datasets/:id", ok),
  http.post("/api/figures", ok),
  http.patch("/api/figures/:id", ok),
  http.delete("/api/figures/:id", ok),
  http.post("/api/import/local-state", ok),

  // ── workspaceStore writes (account-wide installs / papers / gene sets).
  http.post("/api/skill-installs", ok),
  http.delete("/api/skill-installs", ok), // query-param form: ?skill_id=&project_id=
  http.post("/api/workspace/papers", ok),
  http.delete("/api/workspace/papers/:id", ok),
  http.post("/api/workspace/gene-sets", ok),
  http.delete("/api/workspace/gene-sets/:id", ok),
];
