import { defineConfig } from "vite";

// Builds mermaid-check/ into one Node script next to the app (spec §8), so the
// wheel ships it. `npm run build` runs this after the app build, which empties
// the folder.
export default defineConfig({
  resolve: { alias: { dompurify: "/mermaid-check/dompurify-stub.ts" } },
  build: {
    outDir: "../src/synapto/web",
    emptyOutDir: false,
    copyPublicDir: false,
    lib: { entry: "mermaid-check/main.ts", formats: ["es"], fileName: () => "mermaid-check.mjs" },
    rolldownOptions: { output: { codeSplitting: false, minify: true } },
  },
});
