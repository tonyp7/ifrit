import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
// vitest/config's defineConfig is a drop-in for vite's own (adds the `test` field's
// types on top) — needed to type-check the `test` block below without a separate
// vitest.config.ts.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    // Vite warns about any chunk over 500 kB, and the limit is global. Two chunks are that
    // large on purpose: the English word lists of the password-strength library (1,200 kB and
    // 428 kB), which only the New/Edit User form loads, lazily, and which are data that cannot
    // shrink. 1250 sits just above the larger one. The cost is that the main chunk is no
    // longer flagged at 500 kB, so when adding a library check how big `index-*.js` has grown.
    chunkSizeWarningLimit: 1250,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    // vitest 5 exits 1 on zero matched test files (a change from earlier versions,
    // meant to catch a broken test glob/config silently "passing") — this repo
    // genuinely has no test files yet, so that's not a failure to report as one.
    passWithNoTests: true,
    // Initializes a global i18next instance (real English JSON) so components that call
    // useTranslation() can be rendered without a provider.
    setupFiles: ["src/test/setup.ts"],
  },
});
