import React from "react";
import { expect, it } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ProfilePage } from "./ProfilePage.jsx";

const data = {
  view: "guide",
  client: { id: 1, name: "Tetravia" },
  company: { guide_text: "", max_chars: 2000, max_mb: 10, sources: [{ id: 2, filename: "Briefing.pdf", characters: 25631, uploaded_at: "2026-11-06T10:00:00Z" }],
    coach_days: 30, findings: null, coverage: [] },
};

it("an upload says it is loading until the page comes back, and the coach is gone", () => {
  const { container } = render(<ProfilePage data={data} />);
  expect(screen.queryByText("Strategie-Coach")).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull();
  const upload = container.querySelector('form[action="/client/1/guide/upload"]');
  upload.addEventListener("submit", (e) => e.preventDefault());
  fireEvent.submit(upload);
  expect(screen.getByRole("dialog").textContent).toContain("Dokument wird hochgeladen und gelesen");
  act(() => { window.dispatchEvent(new Event("pageshow")); });
  expect(screen.queryByRole("dialog")).toBeNull();
});
