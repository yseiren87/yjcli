import { existsSync } from "node:fs";
import { basename, resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Env values (yj-arch-core): this app keeps only .env.examples; values live in
// tools/secrets/frontend/<app>/.env.<mode> (e.g. vite --mode local-dev).
// Loaded via Vite --mode (no plain .env).
const secretsDir = resolve(__dirname, "../../tools/secrets/frontend", basename(__dirname));
const envDir = existsSync(secretsDir) ? secretsDir : __dirname;

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, "");
  const host = env.HOST || "127.0.0.1";
  const port = Number(env.PORT || "5173");

  return {
    envDir,
    plugins: [react()],
    define: {
      __APP_NAME__: JSON.stringify(env.NAME ?? ""),
      __APP_VERSION__: JSON.stringify(env.VERSION ?? ""),
    },
    server: {
      host,
      port,
      strictPort: true,
    },
    preview: {
      host,
      port,
      strictPort: true,
    },
  };
});
