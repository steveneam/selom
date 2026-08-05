import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Unit tests for pure FE logic (lib/**) — the Pillar-1 staleness/diff engines, etc. — plus
 * component-level PREDICATES (components/**), e.g. whether a badge renders at all for a given
 * value. A React component is a function and `null` is a real return value, so a "does this appear"
 * rule is testable without a DOM; anything needing actual rendering belongs in browser-verify.
 *
 * Still scoped by SUFFIX so it never picks up the Playwright e2e specs (`e2e/*.spec.ts`), which use
 * a different `test`/`expect` — that exclusion is by `.test.ts` vs `.spec.ts`, not by directory.
 * The `@` alias mirrors tsconfig `paths` for any value imports under test.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "components/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
});
