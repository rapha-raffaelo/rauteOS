import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  base: "/static/react/",
  build: {
    outDir: "../newspulse/src/newspulse/web/static/react",
    emptyOutDir: true,
    manifest: true,
    rolldownOptions: {
      input: {
        composer: fileURLToPath(new URL("./src/composer.jsx", import.meta.url)),
        shell: fileURLToPath(new URL("./src/shell.jsx", import.meta.url)),
        platform: fileURLToPath(new URL("./src/platform.jsx", import.meta.url)),
        workbench: fileURLToPath(
          new URL("./src/workbench.jsx", import.meta.url),
        ),
        opportunities: fileURLToPath(
          new URL("./src/opportunities.jsx", import.meta.url),
        ),
        journalists: fileURLToPath(
          new URL("./src/journalists.jsx", import.meta.url),
        ),
        desk: fileURLToPath(new URL("./src/desk.jsx", import.meta.url)),
        twin: fileURLToPath(new URL("./src/twin.jsx", import.meta.url)),
      },
      output: {
        // Framer bekommt einen eigenen, geteilten Chunk.
        //
        // Gemessen beim Einbau: die Bewegungsbibliothek wiegt rund 80 kB. Ohne
        // diese Zeile landet sie in *jedem* Seiten-Bundle, das sie benutzt —
        // bei acht Einstiegspunkten also achtmal, und der Browser lädt sie bei
        // jedem Seitenwechsel erneut. So liegt sie einmal da, trägt einen
        // Inhalts-Hash im Namen und wird deshalb ein Jahr lang unverändert aus
        // dem Cache bedient (siehe _CachedStatic in web/app.py).
        manualChunks(id) {
          if (id.includes("node_modules/framer-motion") || id.includes("node_modules/motion")) {
            return "motion";
          }
          return undefined;
        },
      },
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.js"] },
});
