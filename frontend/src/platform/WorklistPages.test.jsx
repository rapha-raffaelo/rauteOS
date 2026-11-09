import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { LinkedInPage } from "./WorklistPages.jsx";

afterEach(() => vi.unstubAllGlobals());

const data = {
  posts: [{ id: 5, title: "Kreditkosten", body: "Kredite werden teurer. #Mittelstand", status: "freigabe",
    client: { id: 1, name: "Qonto" }, published_url: "", on_linkedin: false, post_at: null }],
  clients: [{ id: 1, name: "Qonto" }],
  states: [["idee", "Idee"], ["freigabe", "Freigabe"], ["veroeffentlicht", "Veröffentlicht"]],
  suggestions: { texts: [], chances: [] },
  account: { configured: false, connected: false },
  draft: {},
};

it("opens LinkedIn with the text, copies it, and then asks for the link", () => {
  const open = vi.fn();
  const writeText = vi.fn().mockResolvedValue();
  vi.stubGlobal("open", open);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  const { container } = render(<LinkedInPage data={data} />);
  fireEvent.click(screen.getByRole("button", { name: "In LinkedIn öffnen" }));
  expect(open.mock.calls[0][0]).toBe(
    "https://www.linkedin.com/feed/?shareActive=true&text=" + encodeURIComponent("Kredite werden teurer. #Mittelstand"));
  expect(writeText).toHaveBeenCalledWith("Kredite werden teurer. #Mittelstand");
  expect(container.querySelector('form[action="/linkedin/5/published"] input[name="published_url"]')).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Mit LinkedIn verbinden" })).toBeNull();
});

it("an idea without text asks for the text, not for a link, and says where its arrow goes", () => {
  const idea = { ...data.posts[0], id: 6, body: "", status: "idee", title: "Neue Wettbewerber" };
  const { container } = render(<LinkedInPage data={{ ...data, posts: [idea] }} />);
  expect(screen.queryByRole("button", { name: "Schon gepostet? Link eintragen" })).toBeNull();
  expect(screen.queryByRole("button", { name: "In LinkedIn öffnen" })).toBeNull();
  expect(screen.getByRole("button", { name: "Freigabe →" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Text schreiben" }));
  const body = container.querySelector('form[action="/linkedin/6"] textarea[name="body"]');
  expect(document.activeElement).toBe(body);
});
