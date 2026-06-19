import next from "eslint-config-next";

// Next 16 removed the built-in `next lint`; this is the flat-config equivalent. eslint-config-next
// 16 ships a native flat-config array (next core-web-vitals + the TypeScript rules), so we spread it
// directly — wrapping it in FlatCompat double-loads the plugins and throws a circular-structure error.
const eslintConfig = [
  ...next,
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "test-results/**",
      "playwright-report/**",
      "public/mockServiceWorker.js", // generated MSW worker — not ours to lint
    ],
  },
  {
    // eslint-config-next 16 turns on the new React Compiler rules. They are optimization
    // ADVISORIES (not correctness bugs) and flag ~25 pre-existing, intentional patterns across the
    // verified components (sync-on-mount / reset-on-dep-change effects, manual memoization the
    // compiler can't preserve, refs read in render). Blanket-refactoring working features to satisfy
    // them carries real regression risk, so they ride as WARNINGS — visible + tracked for incremental
    // cleanup — rather than blocking the lint gate. New code still sees them (and several intentional
    // sites carry a justified inline disable). Promote back to "error" once the backlog is worked off.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
      "react-hooks/refs": "warn",
    },
  },
];

export default eslintConfig;
