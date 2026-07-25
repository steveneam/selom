"use client";

/**
 * Workspace ACCOUNT endpoint (`GET /workspace`) — the account's own record, distinct from its child
 * collections (`/workspace/papers`, `/workspace/gene-sets`) which `./sync.ts` already pulls.
 *
 * **Why this exists (reachability finding `R-07`).** The route shipped for exactly one purpose — its
 * own docstring says a GET "gives the store a single place to provision + **a name to show**" — and
 * nothing ever called it, while the sidebar rendered a hardcoded `"Steven"` / `"Workspace"`. So the
 * account name was both unreachable *and* wrong for anyone who is not the author: a single-tenant
 * assumption baked into a shared component. The reachability ratchet
 * (`app/backend/tests/test_reachability_guard.py`) is what surfaced it.
 *
 * Reading it also **provisions** the workspace server-side — `get_workspace` auto-creates on first
 * read — so this is the honest bootstrap call, not merely a label lookup.
 *
 * Kept separate from `reconcileFetchWorkspace` on purpose: that function returns `WorkspaceState`
 * (papers · geneSets · skills) which the store merges, and the account record is not part of that
 * state. Folding it in would ripple the store's shape for a display string.
 */

import { api } from "@/lib/api/client";

/** The account workspace as it arrives on the wire. */
interface WorkspaceWire {
  id: string;
  name: string;
  created_at?: string | null;
}

export interface WorkspaceAccount {
  id: string;
  /** Display name — the server's, never a client guess. Backend default is "My workspace". */
  name: string;
  createdAt?: string;
}

/**
 * Fetch the account workspace. **Fails SOFT to `null`** rather than throwing: the sidebar is chrome on
 * every page, so a dead backend must not blank the shell. The caller renders a neutral fallback and
 * never a fabricated name — a fallback may degrade structure, it may not invent the answer
 * ([[mock-fallback-never-fabricates-data]]).
 */
export async function fetchWorkspaceAccount(): Promise<WorkspaceAccount | null> {
  try {
    const w = await api.get<WorkspaceWire>("/workspace");
    if (!w?.id) return null;
    return { id: w.id, name: w.name, createdAt: w.created_at ?? undefined };
  } catch {
    return null;
  }
}
