import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { ClientTabs, Shell } from "../shell.jsx";
import { Kickoff } from "./ProfilePage.jsx";
import { safeUrl } from "./shared.jsx";
const response = (body) => ({ ok: true, json: async () => body });
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
afterEach(() => vi.unstubAllGlobals());
it("keeps the five workspace tabs with no Today option or profile submenu", () => {
  const data = {
    client: { id: 1, name: "Alpha" },
    active: "opportunities",
    crisis: { has_history: false },
  };
  const { rerender } = render(
    <ClientTabs data={data} path="/client/1/opportunities" />,
  );
  expect(within(screen.getByRole("navigation", {name:"Mandant"})).getAllByRole("link").map((l) => l.textContent)).toEqual([
    "Overview",
    "Opportunities",
    "Profil",
    "Archiv",
    "KI-Sichtbarkeit",
  ]);
  expect(within(screen.getByRole("navigation", {name:"Ansicht in Opportunities"})).getAllByRole("link").map((o) => o.textContent)).toEqual([
    "Chancen",
    "Impulse",
    "Issues",
    "Plan",
  ]);
  rerender(
    <ClientTabs data={{ ...data, active: "twin" }} path="/client/1/twin" />,
  );
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(
    screen.getByRole("link", { name: "Profil" }).getAttribute("aria-current"),
  ).toBe("page");
});
it("uses client path boundaries and exposes exactly one assistant and Contacts link", () => {
  const data = {
    clients: [
      { id: 1, name: "One" },
      { id: 10, name: "Ten" },
    ],
    path: "/client/10/twin",
    query: "",
    crumbs: { area: "Portfolio" },
    language: "de",
    assistant: { client_id: "10" },
  };
  render(<Shell data={data} portals={false} />);
  expect(
    screen.getByRole("link", { name: "One" }).getAttribute("aria-current"),
  ).toBeNull();
  expect(
    screen.getByRole("link", { name: "Ten" }).getAttribute("aria-current"),
  ).toBe("page");
  expect(screen.getAllByRole("link", { name: "Ask RAUTE" })).toHaveLength(1);
  expect(screen.getAllByRole("link", { name: "Kontakte" })).toHaveLength(1);
  expect(screen.queryByRole("link", { name: "Journalisten" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Menü öffnen" }));
  expect(
    screen
      .getByRole("button", { name: "Menü schließen" })
      .getAttribute("aria-expanded"),
  ).toBe("true");
  fireEvent.keyDown(screen.getByRole("button", { name: "Menü schließen" }), {
    key: "Escape",
  });
  expect(
    screen
      .getByRole("button", { name: "Menü öffnen" })
      .getAttribute("aria-expanded"),
  ).toBe("false");
});
const kickoff = {
  answers: {},
  progress: { settled: 0, total: 2, remaining: 2 },
  groups: [
    [
      { key: "company", title: "Company", intro: "" },
      ["first", "second"].map((key) => ({
        key,
        text: key,
        help: "",
        is_list: false,
        is_prose: true,
        feeds: [],
        verb: "",
        note: "",
      })),
    ],
  ],
};
it("saves one kickoff answer without losing another unsaved answer", async () => {
  const fetch = vi.fn().mockResolvedValue(
    response({
      answer: { value: "Saved", answered_at: "2026-09-18" },
      progress: { settled: 1, total: 2, remaining: 1 },
    }),
  );
  vi.stubGlobal("fetch", fetch);
  render(<Kickoff clientId={1} data={kickoff} />);
  const first = document.getElementById("q-first"),
    second = document.getElementById("q-second");
  fireEvent.change(within(first).getByLabelText("Antwort"), {
    target: { value: "Saved" },
  });
  fireEvent.change(within(second).getByLabelText("Antwort"), {
    target: { value: "Unsaved notes" },
  });
  fireEvent.submit(
    within(first).getByRole("button", { name: "Speichern" }).form,
  );
  await vi.waitFor(() =>
    expect(screen.getByText(/1\/2 beantwortet/)).toBeTruthy(),
  );
  expect(within(second).getByLabelText("Antwort").value).toBe("Unsaved notes");
  expect(fetch.mock.calls[0][0]).toMatch(/\/client\/1\/kickoff\/first$/);
  expect(fetch.mock.calls[0][1].body.get("value")).toBe("Saved");
});
it("retains a kickoff draft and reports a failed save", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  render(<Kickoff clientId={1} data={kickoff} />);
  const first = document.getElementById("q-first");
  fireEvent.change(within(first).getByLabelText("Antwort"), {
    target: { value: "Keep this" },
  });
  fireEvent.submit(
    within(first).getByRole("button", { name: "Speichern" }).form,
  );
  await screen.findByText(/Die Antwort konnte nicht gespeichert werden/);
  expect(within(first).getByLabelText("Antwort").value).toBe("Keep this");
});
it("blocks executable source URLs including embedded controls", () => {
  expect(safeUrl("java\tscript:alert(1)")).toBe("");
  expect(safeUrl("data:text/html,x")).toBe("");
  expect(safeUrl("https://example.org")).toBe("https://example.org");
});

const settingsData = {
  clients: [
    {
      id: 1,
      name: "Alpha",
      active: true,
      is_competitor: false,
      industry: "Tech",
      country: "DE",
      aliases: [],
      keywords: [],
      alert_topics: [],
      excluded_terms: [],
      required_terms: [],
      muted_categories: [],
      competitors: [],
      benchmark_for: [],
    },
  ],
  edit_id: 1,
  onboarding: {},
  themes: {},
  rival_work: {},
  industry_work: {},
  categories: [],
  run_active: false,
  backfill_days: [7],
  run_started: null,
  runs: [],
  map_fields: ["name"],
  map_values: {},
  import_success: null,
  import_rows: null,
  score_range: [0, 1, 2],
  alert_threshold: 2,
  brain_blocks: [],
  brain_version: 0,
  brain_history: [],
  gmail: null,
  gmail_scopes: [],
  gmail_configured: false,
  feeds: [],
  feed_tiers: [],
  radar_stale: null,
};
it("retains settings input after server validation rejects an edit", async () => {
  const { SettingsPage } = await import("./SettingsPage.jsx");
  const fetch = vi
    .fn()
    .mockResolvedValue(
      response({ ...settingsData, client_error: "Land unbekannt." }),
    );
  vi.stubGlobal("fetch", fetch);
  function Harness() {
    const [data, setData] = React.useState(settingsData);
    return <SettingsPage data={data} onData={setData} />;
  }
  render(<Harness />);
  const editor = document.querySelector(".platform-edit");
  fireEvent.change(within(editor).getByLabelText("Name"), {
    target: { value: "Unsaved name" },
  });
  fireEvent.change(within(editor).getByLabelText("Land"), {
    target: { value: "invalid" },
  });
  fireEvent.submit(
    within(editor).getByRole("button", { name: "Speichern", exact: true }).form,
  );
  await screen.findByText("Land unbekannt.");
  expect(within(editor).getByLabelText("Name").value).toBe("Unsaved name");
  expect(within(editor).getByLabelText("Land").value).toBe("invalid");
  expect(fetch.mock.calls[0][1].body.get("name")).toBe("Unsaved name");
});
it("reports a settings network error without resetting the form", async () => {
  const { SettingsPage } = await import("./SettingsPage.jsx");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("Verbindung unterbrochen")),
  );
  render(<SettingsPage data={settingsData} onData={vi.fn()} />);
  const editor = document.querySelector(".platform-edit");
  fireEvent.change(within(editor).getByLabelText("Name"), {
    target: { value: "Keep this client name" },
  });
  fireEvent.submit(
    within(editor).getByRole("button", { name: "Speichern", exact: true }).form,
  );
  await screen.findByText("Verbindung unterbrochen");
  expect(within(editor).getByLabelText("Name").value).toBe(
    "Keep this client name",
  );
});
