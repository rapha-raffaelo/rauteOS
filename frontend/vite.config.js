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
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.js"] },
});
