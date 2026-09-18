import { readFileSync } from "node:fs";
const input = JSON.parse(readFileSync(0, "utf8"));
globalThis.document = {
  getElementById: (id) =>
    id === "react-shell-data"
      ? { textContent: JSON.stringify(input.shell) }
      : null,
};
const { render } = await import("./.test-render/render-test.js");
process.stdout.write(render(input));
