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
  },
});
