import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // User content is plain text only (AGENTS.md): never render raw HTML.
    rules: { "react/no-danger": "error" },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // OpenNext / wrangler output and Playwright reports (generated):
    ".open-next/**",
    ".wrangler/**",
    "playwright-report/**",
    "test-results/**",
  ]),
]);

export default eslintConfig;
