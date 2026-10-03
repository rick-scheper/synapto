import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run build` writes the app into the Python package, which FastAPI serves
// and the wheel ships (ADR-0005). `npm run dev` proxies the API to `debrief serve`.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/debrief/web", emptyOutDir: true },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8765", ws: true } } },
});
