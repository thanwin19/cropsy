// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// The Cropsy backend (FastAPI, backend/) serves the API, the reference photos and the satellite layer PNGs.
// In development the browser talks to this dev server, which forwards those paths to it.
const API_TARGET = process.env.CROPSY_API_PROXY || "http://127.0.0.1:8000";
const proxy = Object.fromEntries(["/api", "/health", "/images", "/field_images", "/layers"].map((p) => [p, { target: API_TARGET, ws: p === "/api" }]));   // ws: the voice question streams over a WebSocket under /api

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    server: { port: Number(process.env.PORT) || 5173, host: "0.0.0.0", proxy },
    preview: { port: Number(process.env.PORT) || 5173, host: "0.0.0.0" },
  },
});
