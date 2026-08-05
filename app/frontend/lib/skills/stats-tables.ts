import type { StatsTable } from "@/lib/skills/api";

/**
 * Narrow the `StatsTable | StatsTable[] | null | undefined` wire union to a plain array.
 *
 * `null`/`undefined` → `[]`, one table → `[table]`, a list → itself. **This is the only place
 * that union is narrowed on the frontend** (docs/stats-tables/spec.md D1, guarded by
 * `lib/structure.guard.test.ts`): a union invites `Array.isArray(...)` to sprout at every call
 * site, and the answer is one normalizer rather than a convention. Every consumer calls this and
 * then handles an array.
 *
 * The backend twin is `skills/_table.py` `as_tables`.
 */
export function asTables(value: StatsTable | StatsTable[] | null | undefined): StatsTable[] {
  if (value == null) return [];
  return Array.isArray(value) ? value : [value];
}
