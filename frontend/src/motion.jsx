/**
 * Die Bewegung von RauteOS, an einer Stelle.
 *
 * Ein System und keine verstreuten Effekte: erfindet jede Seite ihre eigene
 * Dauer und Kurve, fühlt sich das Werkzeug unruhig an statt lebendig.
 *
 * Der Grundsatz: Bewegung erklärt, woher etwas kommt — sie ist kein Schmuck.
 * Alles bleibt unter einer Fünftelsekunde, nichts verzögert einen Klick, und
 * nichts bewegt sich, worauf jemand gerade zielt.
 *
 * **Warum `m` und `LazyMotion` und nicht `motion`.** Gemessen beim Einbau: der
 * volle Import macht aus 8 kB Schale 139 kB — 131 kB mehr auf *jeder* Seite,
 * bei einer Anwendung, deren Beschwerde die Latenz ist. `LazyMotion` mit
 * `domAnimation` lädt nur, was Transparenz und Verschiebung brauchen. Was
 * damit nicht geht, sind Layout-Animationen; die brauchen wir auch nicht (siehe
 * unten).
 *
 * **Warum keine Seitenübergänge.** Jeder Klick in RauteOS ist heute ein voller
 * Seitenwechsel: das Dokument wird verworfen, React startet neu. Zwischen zwei
 * Seiten lässt sich nichts animieren, was es beim Start der zweiten nicht mehr
 * gibt — `layoutId` und `AnimatePresence` über Seitengrenzen wären Code, der
 * nie läuft. Animiert wird deshalb, was *innerhalb* einer Seite entsteht.
 *
 * Wer im System "Bewegung reduzieren" gesetzt hat, bekommt keine. Das ist eine
 * Barrierefreiheitseinstellung, keine Höflichkeit — Bewegung löst bei manchen
 * Menschen Übelkeit aus.
 */
import { LazyMotion, MotionConfig, domAnimation, m } from "framer-motion";

/** Kurz genug, dass niemand darauf wartet. */
export const FAST = 0.16;
export const NORMAL = 0.22;

/**
 * Schnell los, weich aus. Eine Bewegung, die langsam anfängt, liest sich als
 * Verzögerung — und Verzögerung ist das, was hier gerade verschwinden soll.
 */
export const EASE = [0.22, 0.61, 0.36, 1];

/** Etwas erscheint. Leicht von unten, damit es "dazugekommen" aussieht. */
export const appear = {
  hidden: { opacity: 0, y: 6 },
  shown: { opacity: 1, y: 0, transition: { duration: NORMAL, ease: EASE } },
};

/**
 * Eine Liste erscheint der Reihe nach. Sehr kurz gestaffelt: bei dreissig
 * Karten darf die letzte nicht erst nach einer Sekunde dastehen.
 */
export const list = {
  hidden: {},
  shown: { transition: { staggerChildren: 0.025, delayChildren: 0.02 } },
};

/** Rückmeldung auf Zeigen und Drücken. Klein — es ist ein Arbeitswerkzeug. */
export const press = { whileHover: { y: -1 }, whileTap: { scale: 0.985 } };

/**
 * Die Schale. Umschliesst eine Seite einmal, lädt die Bewegungsfunktionen
 * nach und schaltet alles ab, wenn das System danach fragt — an einer Stelle
 * statt in jeder Komponente.
 */
export function Motion({ children }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user" transition={{ duration: NORMAL, ease: EASE }}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}

export { m };
