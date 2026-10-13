import React from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import { Field, Notice, Panel, t } from "./shared.jsx";
export function NewClientPage({ data: d }) {
  return (
    <div className="platform-page new-client-page">
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
            <Field name="contact_name" label="Ansprechpartner" value={d.contact?.contact_name || ""} maxLength={255} autoComplete="name" />
            <Field name="contact_role" label="Funktion" value={d.contact?.contact_role || ""} maxLength={255} placeholder="z. B. Geschäftsführung" />
            <Field name="contact_email" label="E-Mail des Ansprechpartners" type="email" value={d.contact?.contact_email || ""} maxLength={320} autoComplete="email" />
            <Field name="contact_phone" label="Telefon (optional)" type="tel" value={d.contact?.contact_phone || ""} maxLength={80} autoComplete="tel" />
            <div className="platform-actions">
              <button type="submit">{t("Kunden anlegen & Recherche starten")}</button>
              <a href="/">{t("Abbrechen")}</a>
            </div>
          </form>
        </Panel>
        <Panel title="Was danach von selbst passiert">
          <p><a href="/onboarding/demo" target="_blank" rel="noopener noreferrer">Onboarding mit Beispieldaten testen ↗</a></p>
          <ol>
            {[
              "Das Profil wird von der Website gelesen und durch öffentliche Quellen ergänzt.",
              "Belegte Informationen werden mit Quelle im Kundenprofil gespeichert.",
              "Ein persönlicher Onboarding-Link wird automatisch vorbereitet.",
              "Der CEO prüft die Angaben und beantwortet fünf kurze Fragen.",
              "Antworten und Korrekturen fließen direkt in die Kundendatenbank.",
            ].map((text) => (
              <li key={text}>{t(text)}</li>
            ))}
          </ol>
          <p>
            {t(
              "Die Recherche läuft im Hintergrund. Den Fortschritt und den Kundenlink finden Sie im Profil. Unbekannte Angaben bleiben offen; vorhandene Kundenangaben werden nicht überschrieben.",
            )}
          </p>
        </Panel>
      </div>
    </div>
  );
}
