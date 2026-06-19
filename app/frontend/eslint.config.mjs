import next from "eslint-config-next";

// Next 16 removed the built-in `next lint`; this is the flat-config equivalent. eslint-config-next
// 16 ships a native flat-config array (next core-web-vitals + the TypeScript rules), so we spread it
// directly — wrapping it in FlatCompat double-loads the plugins and throws a circular-structure error.
const eslintConfig = [
  ...next,
  {
    ignores: [".next/**", "node_modules/**", "test-results/**", "playwright-report/**"],
  },
];

export default eslintConfig;
