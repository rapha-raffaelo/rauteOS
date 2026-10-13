/**
 * Der Router, und vor allem das, was er *nicht* abfangen darf.
 *
 * Ein Router, der zu viel abfängt, ist schlimmer als keiner: er verschluckt
 * Mittelklicks, "in neuem Tab öffnen" und Adressen, die er gar nicht rendern
 * kann — und zeigt dann eine leere Seite statt einer geladenen.
 */
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { route, useRoute, NAVIGATED } from "./router.jsx";

describe("route", () => {
  it("erkennt die Workbench-Adressen", () => {
    expect(route("/clients")).toEqual({ page: "clients", clientId: null });
    expect(route("/assets")).toEqual({ page: "assets", clientId: null });
    expect(route("/ask")).toEqual({ page: "ask", clientId: null });
    expect(route("/client/8/overview")).toEqual({ page: "overview", clientId: 8 });
    expect(route("/client/8/actions")).toEqual({ page: "actions", clientId: 8 });
  });

  it("lässt alles andere dem Server", () => {
    // Diese Seiten rendert Jinja. Ein Router, der so tut, als könnte er sie
    // auch, bleibt auf halbem Weg stehen und zeigt nichts.
    for (const path of ["/", "/today", "/archive", "/contacts", "/settings",
                        "/client/8/twin", "/client/8/opportunities", "/desk"]) {
      expect(route(path), path).toBeNull();
    }
  });

  it("verwechselt keine fremde Zahl mit einer Mandanten-Id", () => {
    expect(route("/client/acht/overview")).toBeNull();
    expect(route("/client/8/overview/extra")).toBeNull();
  });
});

function Probe() {
  const view = useRoute({ page: "clients", clientId: null });
  return <div>
    <span data-testid="view">{view.page}:{String(view.clientId)}</span>
    <a href="/assets">Assets</a>
    <a href="/client/8/overview">Mandant</a>
    <a href="/today">Heute</a>
    <a href="/assets" target="_blank">Neuer Tab</a>
  </div>;
}

describe("useRoute", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/clients");
  });

  it("wechselt die Ansicht ohne Neuladen", () => {
    render(<Probe/>);

    fireEvent.click(screen.getByText("Assets"));

    expect(screen.getByTestId("view").textContent).toBe("assets:null");
    expect(window.location.pathname).toBe("/assets");
  });

  it("trägt die Mandanten-Id mit", () => {
    render(<Probe/>);

    fireEvent.click(screen.getByText("Mandant"));

    expect(screen.getByTestId("view").textContent).toBe("overview:8");
  });

  it("sagt der Seitenleiste Bescheid", () => {
    // Die Seitenleiste ist ein eigener React-Baum und bekäme den Wechsel sonst
    // nie mit — ihre Markierung bliebe auf der verlassenen Seite stehen.
    render(<Probe/>);
    let heard = null;
    window.addEventListener(NAVIGATED, (e) => { heard = e.detail.pathname; });

    fireEvent.click(screen.getByText("Assets"));

    expect(heard).toBe("/assets");
  });

  it("lässt einen Link auf eine Server-Seite in Ruhe", () => {
    render(<Probe/>);
    const link = screen.getByText("Heute");

    const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(screen.getByTestId("view").textContent).toBe("clients:null");
  });

  it("lässt einen Link mit target in Ruhe", () => {
    render(<Probe/>);
    const link = screen.getByText("Neuer Tab");

    const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
  });

  it("lässt Strg-Klick und Mittelklick in Ruhe", () => {
    // Wer einen Link in einem neuen Tab öffnen will, meint das auch.
    render(<Probe/>);
    const link = screen.getByText("Assets");

    for (const init of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
      const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0, ...init });
      link.dispatchEvent(event);
      expect(event.defaultPrevented, JSON.stringify(init)).toBe(false);
    }
  });

  it("folgt dem Zurück-Knopf", () => {
    // Ohne das wäre der Zurück-Knopf wirkungslos — schlimmer als gar kein Router.
    render(<Probe/>);
    fireEvent.click(screen.getByText("Assets"));

    window.history.replaceState({}, "", "/clients");
    fireEvent.popState(window);

    expect(screen.getByTestId("view").textContent).toBe("clients:null");
  });
});
