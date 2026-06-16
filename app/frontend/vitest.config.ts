import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Unit tests for pure FE logic (lib/**) — the Pillar-1 staleness/diff engines, etc.
 * Scoped to `lib/**​/*.test.ts` so it never picks up the Playwright e2e specs
 * (e2e/*.spec.ts), which use a different `test`/`expect`. The `@` alias mirrors
 * tsconfig `paths` for any value imports under test.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
});
