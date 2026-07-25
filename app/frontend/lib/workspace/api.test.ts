import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";
import { fetchWorkspaceAccount } from "./api";

// Spy on the REAL transport module rather than vi.mock-ing it: the module identity stays the one
// `./api` imported, so there is no hoisting/instance mismatch to reason about.
afterEach(() => vi.restoreAllMocks());

describe("fetchWorkspaceAccount (R-07)", () => {
  it("calls GET /workspace and maps snake_case to the FE shape", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({
      id: "ws_1", name: "My workspace", created_at: "2026-01-01T00:00:00",
    } as never);
    const w = await fetchWorkspaceAccount();
    expect(get).toHaveBeenCalledWith("/workspace");
    expect(w).toEqual({ id: "ws_1", name: "My workspace", createdAt: "2026-01-01T00:00:00" });
  });

  it("FAILS SOFT to null when the backend is unreachable", async () => {
    // The sidebar is chrome on every page: a dead backend must degrade the label, never blank the shell.
    vi.spyOn(api, "get").mockImplementation(() => Promise.reject(new Error("network error")));
    await expect(fetchWorkspaceAccount()).resolves.toBeNull();
  });

  it("returns null on a malformed record rather than inventing a name", async () => {
    // A fallback may degrade structure; it may never fabricate the answer.
    vi.spyOn(api, "get").mockResolvedValue({ name: "ghost" } as never);
    await expect(fetchWorkspaceAccount()).resolves.toBeNull();
  });

  it("does not invent a name when the server sends an empty one", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ id: "ws_1", name: "" } as never);
    const w = await fetchWorkspaceAccount();
    expect(w?.name).toBe(""); // the caller renders a neutral label; api.ts never guesses
  });
});
