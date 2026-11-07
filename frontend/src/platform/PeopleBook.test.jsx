import React from "react";
import { expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PeopleBook } from "./PeopleBook.jsx";

const anna = { id: 3, name: "Anna Berg", position: "CFO", phone: "+49 30 1234", email: "anna@qonto.example",
  linkedin_url: "https://www.linkedin.com/in/anna-berg", topics: "Finanzierung, Kredite", media_contact: true };

it("shows a person as a card: neutral head, LinkedIn, reachable, media switch", () => {
  const { container } = render(<PeopleBook people={[anna, { ...anna, id: 4, name: "Ben", media_contact: false, linkedin_url: "" }]} base="/client/1" />);
  expect(container.querySelector("#kontakt-3 .pb-photo--none")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Anna Berg auf LinkedIn" }).getAttribute("href")).toBe(anna.linkedin_url);
  expect(screen.getAllByRole("link", { name: "+49 30 1234" })[0].getAttribute("href")).toBe("tel:+49301234");
  expect(container.querySelector('#kontakt-3 form[action="/client/1/kontakte/3/medien"] button').textContent).toBe("Medien ✓");
  expect(container.querySelector('#kontakt-4 form[action="/client/1/kontakte/4/medien"] input[name="media_contact"]').value).toBe("1");
  expect(screen.getByText("2 Kontakte · 1 Medienansprechpartner")).toBeTruthy();
});

it("opens an empty form to add a contact", () => {
  const { container } = render(<PeopleBook people={[]} base="/client/1" />);
  fireEvent.click(screen.getByRole("button", { name: "+ Kontakt anlegen" }));
  const form = container.querySelector('form[action="/client/1/kontakte"]');
  expect(form.querySelector('input[type="file"]')).toBeNull();
  expect(document.activeElement).toBe(form.querySelector('input[name="name"]'));
});
