import { readFileSync } from "node:fs";
const input = JSON.parse(readFileSync(0, "utf8"));
globalThis.document = {
  getElementById: (id) =>
    id === "react-shell-data"
      ? { textContent: JSON.stringify(input.shell) }
      : null,
};
// Each pytest process builds into its own folder (RENDER_TEST_BUNDLE), so two
// test runs at once never read each other's half-written bundle.
const bundle = process.env.RENDER_TEST_BUNDLE || "./.test-render/render-test.js";
const { render } = await import(new URL(bundle, import.meta.url).href);
process.stdout.write(render(input));
