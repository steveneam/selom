"use client";

import { api } from "@/lib/api/client";

/**
 * One-time localStorage → Postgres import (sub-spec §4). On first authenticated load, POST the two
 * localStorage blobs to the idempotent `/import/local-state` so a dogfood user's existing work isn't
 * stranded. Gated by a local marker (`selom.import.v1`) so it runs once; the backend also stamps
 * `users.local_import_at`. The blobs are read, never deleted (non-destructive). Idempotent + fail-soft:
 * a network failure leaves the marker UNSET so the next load retries.
 */

const MARKER = "selom.import.v1";
const PROJECTS_KEY = "selom.projects.v1";
const WORKSPACE_KEY = "selom.workspace.v1";

function safeParse(raw: string | null): unknown | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function importLocalStateOnce(): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    if (localStorage.getItem(MARKER)) return; // already imported on this client
  } catch {
    return; // storage unavailable — nothing to import
  }
  const projects = safeParse(localStorage.getItem(PROJECTS_KEY));
  const workspace = safeParse(localStorage.getItem(WORKSPACE_KEY));
  if (!projects && !workspace) {
    try {
      localStorage.setItem(MARKER, JSON.stringify({ at: Date.now(), empty: true }));
    } catch {
      /* ignore */
    }
    return; // nothing local to migrate
  }
  try {
    await api.post("/import/local-state", { projects, workspace });
    localStorage.setItem(MARKER, JSON.stringify({ at: Date.now() }));
  } catch {
    /* backend down / offline — leave the marker unset; the next load retries (import is idempotent) */
  }
}
