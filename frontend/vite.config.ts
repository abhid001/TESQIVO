/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Open-core: the Enterprise image builds with TESQIVO_EDITION=enterprise, which points
// `@edition` at the proprietary src/ee/ tree. Everyone else gets the empty stub.
const enterprise = process.env.TESQIVO_EDITION === "enterprise";
const editionEntry = enterprise ? "./src/ee/index.tsx" : "./src/edition/community.tsx";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@edition": fileURLToPath(new URL(editionEntry, import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
