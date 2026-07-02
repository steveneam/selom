import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the HTTP client so the optimistic writes resolve without a backend.
vi.mock("@/lib/api/client", () => {
  const api = {
    get: vi.fn().mockResolvedValue({}),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    del: vi.fn().mockResolvedValue({}),
  };
  return { api, setAuthHeader: vi.fn(), ApiError: class extends Error {} };
});

import { api } from "@/lib/api/client";
import { mergeDatasets, mergeFigures, projectStore } from "./store";
import { fromApiDataset } from "./sync";
import type { Dataset, Figure } from "./types";

const flush = () => new Promise<void>((r) => setTimeout(r, 0));

describe("projectStore — sync read / async write (sub-spec §2.2)", () => {
  beforeEach(() => {
    (api.post as ReturnType<typeof vi.fn>).mockClear();
    (api.patch as ReturnType<typeof vi.fn>).mockClear();
    (api.del as ReturnType<typeof vi.fn>).mockClear();
  });

  it("createProject returns synchronously with a client id + optimistic row, then POSTs", async () => {
    const p = projectStore.createProject("My project");
    expect(p.id).toMatch(/^p_/); // sync return, client-authoritative id
    expect(p.name).toBe("My project");
    // visible in the snapshot immediately (optimistic — no await)
    expect(projectStore.getSnapshot().projects.some((x) => x.id === p.id)).toBe(true);
    await flush();
    expect(api.post).toHaveBeenCalledWith(
      "/projects",
      { id: p.id, name: "My project", color: expect.any(String) },
    );
  });

  it("addFigure returns the figure synchronously and POSTs the full snake_case body", async () => {
    const pj = projectStore.createProject("P");
    const f = projectStore.addFigure(pj.id, { title: "Volcano", skillId: "selom.volcano" });
    expect(f.id).toMatch(/^f_/);
    await flush();
    const figPost = (api.post as ReturnType<typeof vi.fn>).mock.calls.find((c) => c[0] === "/figures");
    expect(figPost).toBeTruthy();
    expect(figPost![1]).toMatchObject({ id: f.id, project_id: pj.id, title: "Volcano", skill_id: "selom.volcano" });
  });

  it("updateFigureSpec coalesces rapid edits into ONE PATCH carrying the latest spec", async () => {
    const pj = projectStore.createProject("P");
    const f = projectStore.addFigure(pj.id, { title: "F" });
    (api.patch as ReturnType<typeof vi.fn>).mockClear();
    projectStore.updateFigureSpec(f.id, { data: [1], layout: {} } as never);
    projectStore.updateFigureSpec(f.id, { data: [2], layout: {} } as never);
    projectStore.updateFigureSpec(f.id, { data: [3], layout: {} } as never);
    await flush();
    const specCalls = (api.patch as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c) => c[0] === `/figures/${f.id}`,
    );
    expect(specCalls.length).toBe(1);
    expect(specCalls[0][1]).toEqual({ spec: { data: [3], layout: {} } });
  });

  it("installSkill is idempotent locally and de-duplicated (no double POST)", async () => {
    const pj = projectStore.createProject("P");
    (api.post as ReturnType<typeof vi.fn>).mockClear();
    projectStore.installSkill(pj.id, "selom.deg");
    projectStore.installSkill(pj.id, "selom.deg"); // already installed — no-op
    await flush();
    const installPosts = (api.post as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c) => c[0] === "/skill-installs",
    );
    expect(installPosts.length).toBe(1);
  });

  it("deleteProject + immediate restore (Undo) cancels the queued DELETE — no API call", async () => {
    const pj = projectStore.createProject("To delete");
    await flush();
    (api.del as ReturnType<typeof vi.fn>).mockClear();
    const snap = projectStore.deleteProject(pj.id);
    projectStore.restoreProject(snap); // Undo within the grace window
    await flush();
    expect(api.del).not.toHaveBeenCalled(); // the delete was cancelled before firing
    expect(projectStore.getSnapshot().projects.some((x) => x.id === pj.id)).toBe(true);
  });
});

describe("addDataset — the real path never fabricates qc (A2 ratchet: the pbmc3k mock-QC honesty bug)", () => {
  it("a freshly added REAL dataset starts with qc === undefined, never a fabricated stand-in", () => {
    const pj = projectStore.createProject("Real project");
    const d = projectStore.addDataset(pj.id, "sample.h5ad", "scRNA-seq");
    expect(d.qc).toBeUndefined();
    // The snapshot agrees — no fabricated dims persisted to the store/mirror either.
    expect(projectStore.getSnapshot().datasets.find((x) => x.id === d.id)?.qc).toBeUndefined();
  });
});

describe("addUploadedDataset + fromApiDataset.uploaded — the WS2.1 upload→run→save loop", () => {
  it("addUploadedDataset inserts the server-authoritative row WITHOUT a POST (intake already persisted it)", async () => {
    (api.post as ReturnType<typeof vi.fn>).mockClear();
    const d: Dataset = {
      id: "srv_up_ds", projectId: "demo-pbmc", filename: "counts.csv",
      modality: "bulk RNA-seq", uploaded: true, currentSha256: "abc", createdAt: 1,
    };
    const ret = projectStore.addUploadedDataset(d);
    expect(ret).toBe(d);
    expect(projectStore.getSnapshot().datasets.some((x) => x.id === "srv_up_ds")).toBe(true);
    await flush();
    // The metadata-only twin (addDataset) POSTs /datasets; the upload flow must NOT — the row exists.
    expect(api.post).not.toHaveBeenCalledWith("/datasets", expect.objectContaining({ id: "srv_up_ds" }));
  });

  it("flags a ready row WITH stored bytes as uploaded; a metadata-only / pending row is not", () => {
    const map = (r: Record<string, unknown>) => fromApiDataset({ id: "x", project_id: "p", filename: "f", ...r });
    expect(map({ status: "ready", upload_s3_key: "uploads/x" }).uploaded).toBe(true);
    expect(map({ status: "ready", parquet_s3_key: "data/x.csv" }).uploaded).toBe(true);
    expect(map({ status: "ready" }).uploaded).toBe(false); // metadata-only (addDataset) → multipart
    expect(map({ status: "pending_upload", upload_s3_key: "uploads/x" }).uploaded).toBe(false); // not confirmed
  });
});

describe("mergeFigures — the local-only aiProposals survives a server-wins reconcile (S5)", () => {
  const fig = (over: Partial<Figure>): Figure =>
    ({ id: "f1", projectId: "p", title: "F", createdAt: 1, ...over }) as Figure;

  it("re-attaches aiProposals when the server row (which lacks them) replaces the local figure", () => {
    const local = [
      fig({
        aiProposals: [
          { id: "a1", type: "set_param", tier: "recompute", status: "accepted", paramKey: "n_neighbors", value: 30, actor: "ai" },
        ],
      }),
    ];
    const server = [fig({ title: "F (from server)" })]; // same id, NO aiProposals key
    const merged = mergeFigures(local, server);
    const f1 = merged.find((f) => f.id === "f1")!;
    expect(f1.title).toBe("F (from server)"); // server wins on synced fields
    expect(f1.aiProposals).toHaveLength(1); // ...but the pre-commit AI queue is preserved
    expect(f1.aiProposals![0].id).toBe("a1");
  });

  it("leaves a server figure with no local counterpart untouched (no phantom proposals)", () => {
    const merged = mergeFigures([], [fig({ id: "f2" })]);
    expect(merged.find((f) => f.id === "f2")!.aiProposals).toBeUndefined();
  });
});

describe("mergeDatasets — the local-only routing/dataFit survives a server-wins reconcile (Slice 2)", () => {
  const dset = (over: Partial<Dataset>): Dataset =>
    ({ id: "d1", projectId: "p", filename: "de.csv", modality: "bulk RNA-seq", createdAt: 1, ...over }) as Dataset;

  it("re-attaches routing + dataFit when the server row (which lacks them) replaces the local dataset", () => {
    const local = [
      dset({
        routing: { kind: "de_results", steps: [{ skill_id: "volcano", role: "analyze", reason: "" }], confident: true, note: "" },
        dataFit: { quality: 100, confidence: "confident", columns: ["gene", "logFC", "padj"], n_numeric_cols: 2, fits: [] },
      }),
    ];
    const server = [dset({ filename: "de.csv (from server)" })]; // same id, NO routing/dataFit keys
    const merged = mergeDatasets(local, server);
    const d1 = merged.find((d) => d.id === "d1")!;
    expect(d1.filename).toBe("de.csv (from server)"); // server wins on synced fields
    expect(d1.routing?.steps[0].skill_id).toBe("volcano"); // ...but the data-aware route is preserved
    expect(d1.dataFit?.columns).toEqual(["gene", "logFC", "padj"]);
  });

  it("leaves a server dataset with no local counterpart untouched (no phantom route)", () => {
    const merged = mergeDatasets([], [dset({ id: "d2" })]);
    expect(merged.find((d) => d.id === "d2")!.routing).toBeUndefined();
  });
});
