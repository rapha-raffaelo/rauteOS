import React from "react";
import { expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeSwitch } from "./shell.jsx";

it("switches between Hell and Dunkel and remembers it", () => {
  document.documentElement.setAttribute("data-theme", "light");
  localStorage.removeItem("raute-theme");
  render(<ThemeSwitch />);
  const button = screen.getByRole("button", { name: "Dunkler Modus" });
  expect(button.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(button);
  expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  expect(localStorage.getItem("raute-theme")).toBe("dark");
  expect(button.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(button);
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  expect(localStorage.getItem("raute-theme")).toBe("light");
});
