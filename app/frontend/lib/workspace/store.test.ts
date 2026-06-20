import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the Workspace-Library store (the localStorage mock + the project→workspace
 * migration). The vitest env is "node", so we stub a minimal in-memory `localStorage` + a
 * `window` (the store guards hydration on `typeof window`). Each test imports a FRESH module
 * instance (`vi.resetModules()`) so the module-scoped `state`/`hydrated` start clean.
 */

class MemStorage {
  private m = new Map<string, string>();
  getItem(k: string) {
    return this.m.has(k) ? (this.m.get(k) as string) : null;
  }
  setItem(k: string, v: string) {
    this.m.set(k, v);
  }
  removeItem(k: string) {
    this.m.delete(k);
  }
  clear() {
    this.m.clear();
  }
}

let ls: MemStorage;

beforeEach(() => {
  ls = new MemStorage();
  vi.stubGlobal("localStorage", ls);
  vi.stubGlobal("window", { localStorage: ls });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function freshStore() {
  vi.resetModules();
  return await import("./store");
}

/** A persisted ProjectState shape with the two migratable collections. */
function seedProjects(geneSets: unknown[], installs: unknown[]) {
  ls.setItem(
    "selom.projects.v1",
    JSON.stringify({ projects: [], datasets: [], figures: [], installs, geneSets }),
  );
}

describe("workspaceStore — seed", () => {
  it("starts empty and SSR-stable (server snapshot === first client snapshot)", async () => {
    const { workspaceStore } = await freshStore();
    const snap = workspaceStore.getSnapshot();
    expect(snap).toEqual({ papers: [], geneSets: [], skills: [] });
    expect(workspaceStore.getServerSnapshot()).toBe(snap);
  });
});

describe("workspaceStore — hydrate + migration", () => {
  it("migrates project gene sets (deduped on createdFrom) and installs (union) on first run", async () => {
    seedProjects(
      [
        { id: "a", projectId: "p1", name: "Cilium", genes: ["A"], source: "go", sourceLabel: "GO", license: "CC", createdFrom: "go:1", createdAt: 1 },
        { id: "b", projectId: "p2", name: "Cilium", genes: ["A"], source: "go", sourceLabel: "GO", license: "CC", createdFrom: "go:1", createdAt: 2 }, // dup createdFrom
        { id: "c", projectId: "p2", name: "Photo", genes: ["B"], source: "wiki", sourceLabel: "Wiki", license: "CC", createdFrom: "wiki:9", createdAt: 3 },
      ],
      [
        { id: "i1", projectId: "p1", skillId: "selom.deg", installedAt: 10 },
        { id: "i2", projectId: "p2", skillId: "selom.deg", installedAt: 11 }, // dup skillId
        { id: "i3", projectId: "p2", skillId: "selom.volcano", installedAt: 12 },
      ],
    );
    const { workspaceStore } = await freshStore();
    workspaceStore.hydrate();
    const s = workspaceStore.getSnapshot();
    expect(s.geneSets.map((g) => g.createdFrom)).toEqual(["go:1", "wiki:9"]);
    expect(s.skills.map((x) => x.skillId).sort()).toEqual(["selom.deg", "selom.volcano"]);
    // Persisted the workspace key so the next hydrate loads, not re-migrates.
    expect(ls.getItem("selom.workspace.v1")).toBeTruthy();
  });

  it("does NOT re-migrate when a workspace snapshot already exists", async () => {
    seedProjects([], [{ id: "i1", projectId: "p1", skillId: "selom.deg", installedAt: 10 }]);
    ls.setItem("selom.workspace.v1", JSON.stringify({ papers: [], geneSets: [], skills: [] }));
    const { workspaceStore } = await freshStore();
    workspaceStore.hydrate();
    expect(workspaceStore.getSnapshot().skills).toEqual([]); // loaded the empty workspace, ignored projects
  });

  it("tolerates a missing / corrupt projects snapshot (migrates nothing)", async () => {
    ls.setItem("selom.projects.v1", "{not json");
    const { workspaceStore } = await freshStore();
    workspaceStore.hydrate();
    expect(workspaceStore.getSnapshot()).toEqual({ papers: [], geneSets: [], skills: [] });
  });

  it("hydrate is a no-op the second time (the hydrated flag holds)", async () => {
    const { workspaceStore } = await freshStore();
    workspaceStore.hydrate();
    workspaceStore.installSkill("selom.deg");
    // A second hydrate must not clobber live state with a re-read.
    workspaceStore.hydrate();
    expect(workspaceStore.getSnapshot().skills.map((s) => s.skillId)).toEqual(["selom.deg"]);
  });
});

describe("workspaceStore — savePaper (idempotent)", () => {
  const base = {
    filename: "JEV.pdf",
    title: "EV paper",
    skills: ["deg", "volcano"],
    outOfScope: ["wet_lab"],
    figureCount: 8,
    tierSummary: { structured: 6, recovered: 2 },
  };

  it("saves a new paper", async () => {
    const { workspaceStore } = await freshStore();
    const p = workspaceStore.savePaper(base);
    expect(p.id).toMatch(/^paper_/);
    expect(workspaceStore.getSnapshot().papers).toHaveLength(1);
  });

  it("re-saving the same filename updates in place (no duplicate, same id)", async () => {
    const { workspaceStore } = await freshStore();
    const a = workspaceStore.savePaper(base);
    const b = workspaceStore.savePaper({ ...base, title: "EV paper (v2)" });
    expect(workspaceStore.getSnapshot().papers).toHaveLength(1);
    expect(b.id).toBe(a.id);
    expect(workspaceStore.getSnapshot().papers[0].title).toBe("EV paper (v2)");
  });

  it("dedups on doi when present (different filename, same doi → one row)", async () => {
    const { workspaceStore } = await freshStore();
    workspaceStore.savePaper({ ...base, filename: "x.pdf", doi: "10.1/abc" });
    workspaceStore.savePaper({ ...base, filename: "y.pdf", doi: "10.1/abc" });
    expect(workspaceStore.getSnapshot().papers).toHaveLength(1);
  });

  it("removePaper returns the row and restorePaper re-inserts it (Undo)", async () => {
    const { workspaceStore } = await freshStore();
    const p = workspaceStore.savePaper(base);
    const removed = workspaceStore.removePaper(p.id);
    expect(removed?.id).toBe(p.id);
    expect(workspaceStore.getSnapshot().papers).toHaveLength(0);
    workspaceStore.restorePaper(removed!);
    expect(workspaceStore.getSnapshot().papers).toHaveLength(1);
  });
});

describe("workspaceStore — paper supplements (Reproduction stage 2)", () => {
  const base = {
    filename: "JEV.pdf",
    title: "EV paper",
    skills: ["deg", "volcano"],
    outOfScope: ["wet_lab"],
    figureCount: 8,
    tierSummary: { structured: 6, recovered: 2 },
  };

  it("adds supplements to a paper, deduped on filename (case-insensitive)", async () => {
    const { workspaceStore, wselect } = await freshStore();
    const p = workspaceStore.savePaper(base);
    workspaceStore.addPaperSupplements(p.id, [
      { filename: "mmc2.xlsx", kind: "xlsx", size: 1000 },
      { filename: "methods.pdf", kind: "pdf" },
    ]);
    workspaceStore.addPaperSupplements(p.id, [{ filename: "MMC2.XLSX", kind: "xlsx" }]); // dup
    const supp = wselect.paper(workspaceStore.getSnapshot(), p.id)?.supplements ?? [];
    expect(supp.map((s) => s.filename)).toEqual(["mmc2.xlsx", "methods.pdf"]);
    expect(supp[0].id).toMatch(/^supp_/);
  });

  it("returns undefined when the paper isn't in the Library", async () => {
    const { workspaceStore } = await freshStore();
    expect(workspaceStore.addPaperSupplements("nope", [{ filename: "x.csv", kind: "csv" }])).toBeUndefined();
  });

  it("removePaperSupplement detaches one file by id", async () => {
    const { workspaceStore, wselect } = await freshStore();
    const p = workspaceStore.savePaper(base);
    workspaceStore.addPaperSupplements(p.id, [
      { filename: "a.csv", kind: "csv" },
      { filename: "b.xlsx", kind: "xlsx" },
    ]);
    const first = wselect.paper(workspaceStore.getSnapshot(), p.id)!.supplements![0];
    workspaceStore.removePaperSupplement(p.id, first.id);
    const left = wselect.paper(workspaceStore.getSnapshot(), p.id)?.supplements ?? [];
    expect(left.map((s) => s.filename)).toEqual(["b.xlsx"]);
  });

  it("wselect.paper finds a saved paper by id", async () => {
    const { workspaceStore, wselect } = await freshStore();
    const p = workspaceStore.savePaper(base);
    expect(wselect.paper(workspaceStore.getSnapshot(), p.id)?.id).toBe(p.id);
    expect(wselect.paper(workspaceStore.getSnapshot(), "missing")).toBeUndefined();
  });

  it("setPaperReproductionRun stamps the run id (and is a no-op for an unknown paper)", async () => {
    const { workspaceStore, wselect } = await freshStore();
    const p = workspaceStore.savePaper(base);
    workspaceStore.setPaperReproductionRun(p.id, "run_abc");
    expect(wselect.paper(workspaceStore.getSnapshot(), p.id)?.reproductionRunId).toBe("run_abc");
    expect(() => workspaceStore.setPaperReproductionRun("nope", "run_x")).not.toThrow();
  });
});

describe("workspaceStore — gene sets + skills", () => {
  it("saveGeneSet is idempotent on createdFrom", async () => {
    const { workspaceStore } = await freshStore();
    const set = { name: "Cilium", genes: ["A"], source: "go", sourceLabel: "GO", license: "CC", createdFrom: "go:1" };
    const a = workspaceStore.saveGeneSet(set);
    const b = workspaceStore.saveGeneSet(set);
    expect(b.id).toBe(a.id);
    expect(workspaceStore.getSnapshot().geneSets).toHaveLength(1);
  });

  it("install/uninstall skill dedups by skillId", async () => {
    const { workspaceStore, wselect } = await freshStore();
    workspaceStore.installSkill("selom.deg");
    workspaceStore.installSkill("selom.deg"); // dup
    workspaceStore.installSkill("selom.umap_scrna");
    expect(wselect.installedSkillIds(workspaceStore.getSnapshot())).toEqual(new Set(["selom.deg", "selom.umap_scrna"]));
    workspaceStore.uninstallSkill("selom.deg");
    expect(wselect.hasSkill(workspaceStore.getSnapshot(), "selom.deg")).toBe(false);
  });
});
