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
import { projectStore } from "./store";

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
