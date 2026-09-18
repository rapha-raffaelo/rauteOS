import React from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import { Field, Notice, Panel, t } from "./shared.jsx";
export function NewClientPage({ data: d }) {
  return (
    <div className="platform-page">
      <PageHeading eyebrow="Clients" title={t("Neuer Mandant")} />
      <Notice>{d.error}</Notice>
      <div className="platform-columns">
        <Panel title="Unternehmensangaben">
          <form method="post" action="/mandant/neu">
            <Field
              name="name"
              label="Name des Unternehmens"
              value={d.prefill_name}
              required
              autoFocus
              autoComplete="off"
              placeholder={t("Wie die Presse es nennt")}
            >
              <small>
                {t(
                  "So, wie er in einer Schlagzeile stünde. Danach wird gesucht.",
                )}
              </small>
            </Field>
            <Field
              name="website"
              label="Website"
              value={d.prefill_website}
              autoComplete="off"
              placeholder="beispiel.de"
            >
              <small>
                {t(
                  "Woraus das Profil gelesen wird: Geschäftsfeld, Führung, Zahlen. Ohne sie bleibt das Profil leer, bis jemand es tippt.",
                )}
              </small>
            </Field>
            <Field
              name="country"
              label="Land"
              value={d.prefill_country}
              maxLength={2}
              autoComplete="off"
              placeholder="DE"
            >
              <small>{t("Entscheidet, welche Presse durchsucht wird.")}</small>
            </Field>
            <div className="platform-actions">
              <button type="submit">{t("Anlegen und einrichten")}</button>
              <a href="/">{t("Abbrechen")}</a>
            </div>
          </form>
        </Panel>
        <Panel title="Was danach von selbst passiert">
          <ol>
            {[
              "Die Branche wird bestimmt und an der echten Suche geprüft.",
              "Themen für den Radar werden vorgeschlagen und gemessen.",
              "Die Berichterstattung der letzten Wochen wird geholt und analysiert.",
              "Das Profil wird von der Website gelesen und eingetragen.",
              "Ein erster Impuls und ein Anschreiben dazu entstehen.",
            ].map((text) => (
              <li key={text}>{t(text)}</li>
            ))}
          </ol>
          <p>
            {t(
              "Das dauert ein paar Minuten. Alles davon lässt sich danach von Hand ändern, und was Sie ändern, fasst die Recherche nie wieder an.",
            )}
          </p>
        </Panel>
      </div>
    </div>
  );
}
