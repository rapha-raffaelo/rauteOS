/**
 * Klicks ohne Neuladen — für die Seiten, die ihre Daten ohnehin über die API holen.
 *
 * Bisher war jeder Klick ein voller Seitenwechsel: das Dokument wurde
 * verworfen, React neu gestartet, die Seitenleiste neu gebaut, und dazwischen
 * blitzte es weiss. Gemessen am Server lag das nicht — desk.build antwortet in
 * 38 ms. Es lag am Weg dorthin.
 *
 * **Warum das hier klein sein darf.** `WorkbenchPage` nimmt `page` und
 * `clientId` schon als Eigenschaften entgegen und lädt alles Weitere über
 * `/api/v1/workbench/...`. Die Seiten sind also bereits datengetrieben; es
 * fehlte nur, dass jemand die Adresse ändert, ohne das Dokument wegzuwerfen.
 *
 * **Was absichtlich *nicht* abgefangen wird.** Alles, was keine
 * Workbench-Adresse ist, bleibt ein gewöhnlicher Link und lädt die Seite neu —
 * diese Seiten rendert der Server, und ein Router, der so tut, als könnte er
 * sie auch, würde auf halbem Weg stehenbleiben. Ebenso unangetastet bleiben
 * Mittelklick, Strg/Cmd-Klick, Umschalt-Klick, `target`, `download` und fremde
 * Hosts: wer einen Link in einem neuen Tab öffnen will, meint das auch.
 */
import { useEffect, useState } from "react";

/** Das Ereignis, mit dem sich die Seitenleiste über einen Wechsel erfährt. */
export const NAVIGATED = "rauteos:navigated";

/**
 * Die Adresse als Ansicht, oder ``null`` wenn sie keine Workbench-Adresse ist.
 *
 * Die Liste ist bewusst erschöpfend statt gemustert: ein Router, der rät,
 * welche Adresse er bedienen kann, verschluckt irgendwann eine Seite, die er
 * nicht rendern kann, und zeigt dann nichts.
 */
export function route(pathname) {
  if (pathname === "/clients") return { page: "clients", clientId: null };
  if (pathname === "/assets") return { page: "assets", clientId: null };
  if (pathname === "/ask") return { page: "ask", clientId: null };
  const client = pathname.match(/^\/client\/(\d+)\/(overview|actions)$/);
  if (client) return { page: client[2], clientId: Number(client[1]) };
  return null;
}

/** Ob dieser Klick eine Navigation im Dokument sein darf. */
function handled(event, link) {
  if (event.defaultPrevented || event.button !== 0) return false;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (!link || link.target || link.hasAttribute("download")) return false;
  if (link.origin !== window.location.origin) return false;
  // Ein Sprungziel auf derselben Seite ist keine Navigation.
  if (link.pathname === window.location.pathname && link.hash) return false;
  return Boolean(route(link.pathname));
}

/**
 * Die aktuelle Ansicht, und der Umschalter dazu.
 *
 * ``initial`` ist, was der Server in das Mount-Element geschrieben hat. Es
 * zählt nur beim ersten Aufbau: danach ist die Adresse die Wahrheit, und zwar
 * auch nach Zurück und Vorwärts — ohne den ``popstate``-Hörer bliebe der
 * Zurück-Knopf wirkungslos, was schlimmer ist als gar kein Router.
 */
export function useRoute(initial) {
  const [view, setView] = useState(() => route(window.location.pathname) || initial);

  useEffect(() => {
    function go(pathname) {
      const next = route(pathname);
      if (!next) {
        window.location.assign(pathname);
        return;
      }
      setView(next);
      window.dispatchEvent(new CustomEvent(NAVIGATED, { detail: { pathname } }));
    }

    function onClick(event) {
      const link = event.target.closest?.("a[href]");
      if (!handled(event, link)) return;
      event.preventDefault();
      if (link.pathname === window.location.pathname && !link.search) return;
      window.history.pushState({}, "", link.pathname + link.search);
      // Nach oben, wie bei einem echten Seitenwechsel: sonst landet man auf
      // der neuen Seite an der Scrollposition der alten.
      window.scrollTo({ top: 0 });
      go(link.pathname);
    }

    function onPop() {
      go(window.location.pathname);
    }

    document.addEventListener("click", onClick);
    window.addEventListener("popstate", onPop);
    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener("popstate", onPop);
    };
  }, []);

  return view;
}
