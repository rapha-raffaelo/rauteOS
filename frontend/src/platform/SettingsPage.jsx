import React, { useState, useEffect, useRef } from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import {
  Action,
  Field,
  Hidden,
  Notice,
  Panel,
  Source,
  date,
  dateTime,
  t,
} from "./shared.jsx";
const clientFields = [
  ["name", "Marke"],
  ["legal_name", "Unternehmen dahinter (optional)"],
  ["industry", "Branche"],
  ["country", "Land"],
  ["aliases", "Aliasse"],
  ["keywords", "Suchbegriffe"],
  ["excluded_terms", "Ausschlussbegriffe"],
  ["required_terms", "Pflicht-Begleitwörter"],
  ["actions_per_quarter", "Actions pro Quartal"],
  ["alert_topics", "Alarm-Themen"],
];
function ClientFields({ client = {}, create = false }) {
  return (
    <div className="platform-fields">
      {[...clientFields, ...(create ? [["website", "Website"]] : [])].map(
        ([key, label]) => (
          <Field
            key={key}
            name={key}
            label={label}
            value={
              Array.isArray(client[key])
                ? client[key].join(", ")
                : (client[key] ?? (key === "country" ? "DE" : ""))
            }
            required={key === "name"}
            type={key === "actions_per_quarter" ? "number" : "text"}
            min={key === "actions_per_quarter" ? 0 : undefined}
          />
        ),
      )}
    </div>
  );
}
function Job({
  job,
  children,
  label = "Vorschläge werden recherchiert…",
  errorLabel = "Vorschlag fehlgeschlagen",
}) {
  return !job ? null : job.state === "läuft" ? (
    <Notice>{label}</Notice>
  ) : job.state === "fehler" ? (
    <Notice>{`${errorLabel}: ${job.error || ""}`}</Notice>
  ) : (
    children
  );
}
// Live mandates, then the archive: a deactivated mandate is on its way out
// and should not sit between the ones Lucas works on. Competitors are not kept
// here; each mandate manages its own under Strategie › Wettbewerb & Markt.
const clientGroups = [
  ["Mandanten gesamt", (c) => !c.is_competitor && c.active],
  ["im Archiv", (c) => !c.is_competitor && !c.active],
];
const PENCIL = "M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4";
const CLOSE = "M6 6l12 12M18 6 6 18";
const POWER = "M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0";
const Glyph = ({ d }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);
// KI-Modelle: connect each provider, then give each role its order. The first
// connected provider of a role answers; the next steps in when it is spent.
function AiModels({ data: ai }) {
  if (!ai) return null;
  const labels = Object.fromEntries(ai.providers.map((p) => [p.key, p.label]));
  return (
    <Panel title="KI-Modelle" id="ki-modelle">
      <p>
        {t("Erst die Anbieter verbinden, dann je Rolle festlegen, welches Modell zuerst antwortet. Fällt eines aus oder ist sein Kontingent erschöpft, springt das nächste ein.")}
      </p>
      <Notice>{ai.error}</Notice>
      {ai.notice && <p className="ai-notice" role="status">{ai.notice}</p>}
      {!ai.secret_ready && (
        <Notice>{t("Auf dem Server fehlt NEWSPULSE_SESSION_SECRET. Ohne ihn werden keine Schlüssel gespeichert.")}</Notice>
      )}
      <div className="ai-providers">
        {ai.providers.map((p) => (
          <section className={`ai-provider${p.connected ? " ai-provider--on" : ""}`} key={p.key} aria-label={p.label}>
            <header>
              <h3>{p.label} <small>{p.vendor}</small></h3>
              <span className="ai-state">{p.connected ? `${t("Verbunden")} · ${t(p.how)}${p.hint ? ` · …${p.hint}` : ""}` : t("Nicht verbunden")}</span>
            </header>
            {p.subscription_only ? (
              <div className="ai-login">
                <p>
                  {t(p.connected
                    ? "Läuft über das ChatGPT-Abo, ohne API-Schlüssel. Der Verbrauch zählt gegen die Kontingente des angemeldeten Kontos."
                    : "Läuft über das ChatGPT-Abo, ohne API-Schlüssel. Einmal auf dem Server anmelden (im Ordner /srv/rauteos/repo/deploy), dann den angezeigten Link und Code im Browser bestätigen:")}
                </p>
                {!p.connected && <code className="ai-login__cmd">{p.login_command}</code>}
                <form method="post" action="/settings/ai/key" className="ai-key">
                  <input type="hidden" name="provider" value={p.key} />
                  <label className="platform-field"><span>{t("Modell")}</span>
                    <input type="text" name="model" defaultValue={p.model} placeholder={t("Standard des Abos")} maxLength={100} />
                  </label>
                  <button type="submit" className="btn btn--go">{t("Speichern")}</button>
                </form>
              </div>
            ) : (
              <form method="post" action="/settings/ai/key" className="ai-key">
                <input type="hidden" name="provider" value={p.key} />
                <label className="platform-field"><span>{t("API-Schlüssel")}</span>
                  <input type="password" name="api_key" autoComplete="off" placeholder={p.hint ? `…${p.hint}` : ""} maxLength={500} />
                </label>
                <label className="platform-field"><span>{t("Modell")}</span>
                  <input type="text" name="model" defaultValue={p.model} placeholder={p.default_model} maxLength={100} />
                </label>
                <button type="submit" className="btn btn--go">{t(p.connected ? "Speichern" : "Verbinden")}</button>
              </form>
            )}
            <div className="ai-provider__acts">
              <form method="post" action="/settings/ai/test">
                <input type="hidden" name="provider" value={p.key} />
                <button type="submit" className="btn btn--quiet" disabled={!p.connected}>{t("Verbindung testen")}</button>
              </form>
              {p.hint && (
                <form method="post" action="/settings/ai/forget">
                  <input type="hidden" name="provider" value={p.key} />
                  <button type="submit" className="btn btn--quiet">{t("Schlüssel entfernen")}</button>
                </form>
              )}
            </div>
          </section>
        ))}
      </div>
      <form method="post" action="/settings/ai/order" className="ai-roles">
        <h3>{t("Rollen und Reihenfolge")}</h3>
        {ai.roles.map((r) => (
          <fieldset key={r.key} className="ai-role">
            <legend>{t(r.label)}</legend>
            <p>{t(r.description)}</p>
            <div className="ai-role__order">
              {[0, 1, 2].map((i) => (
                <label key={i} className="platform-field"><span>{i + 1}.</span>
                  <select name={`${r.key}_${i + 1}`} defaultValue={r.order[i] || ""} aria-label={`${t(r.label)} ${i + 1}.`}>
                    <option value="">—</option>
                    {ai.providers.map((p) => (
                      <option key={p.key} value={p.key}>{labels[p.key]}{p.connected ? "" : ` (${t("nicht verbunden")})`}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <button type="submit" className="btn btn--go">{t("Reihenfolge speichern")}</button>
      </form>
    </Panel>
  );
}
function ClientSettings({ client: c, data: d }) {
  const base = `/settings/clients/${c.id}`,
    edit = Number(d.edit_id) === c.id;
  const label = t(edit ? "Schließen" : "Bearbeiten");
  return (
    <article className="platform-client platform-client--row" id={`client-${c.id}`}>
      <header>
        <div className="platform-client__who">
          <h3>
            <a href={`/client/${c.id}/overview`}>{c.name}</a>
          </h3>
          <p title={c.industry || ""}>
            {c.industry || "—"} · {c.country} ·{" "}
            {t(c.active ? "aktiv" : "inaktiv")}
            {c.purge_on &&
              ` · ${t("Löschung am")} ${date(c.purge_on)}`}
          </p>
        </div>
        <a className="platform-icon" aria-label={`${label}: ${c.name}`} title={label}
          href={edit ? "/settings" : `/settings?edit=${c.id}#client-${c.id}`}>
          <Glyph d={edit ? CLOSE : PENCIL} />
        </a>
      </header>
      {d.onboarding[c.id] && <p className="platform-client__status" role="status">{d.onboarding[c.id]}</p>}
      {edit && (
        <div className="platform-edit">
          <div className="platform-edit__bar">
            <a href={`/client/${c.id}/wettbewerb`}>{t("Wettbewerber verwalten")} →</a>
            <form method="post" action={base + (c.active ? "/deactivate" : "/reactivate")}>
              <button type="submit" className={`platform-icon${c.active ? " platform-icon--danger" : ""}`}
                aria-label={`${t(c.active ? "Deaktivieren" : "Reaktivieren")}: ${c.name}`}
                title={t(c.active ? "Deaktivieren" : "Reaktivieren")}>
                <Glyph d={POWER} /><span>{t(c.active ? "Deaktivieren" : "Reaktivieren")}</span>
              </button>
            </form>
          </div>
          <form method="post" action={base}>
            <ClientFields client={c} />
            <fieldset>
              <legend>{t("Im Tagesfeed ausblenden")}</legend>
              {d.categories.map((category) => (
                <label key={category} className="platform-check">
                  <input
                    type="checkbox"
                    name="muted_categories"
                    value={category}
                    defaultChecked={c.muted_categories.includes(category)}
                  />
                  {t(category)}
                </label>
              ))}
              <p>
                {t(
                  "Nur die Ansicht: die Artikel bleiben im Archiv, in den Zahlen und im Export.",
                )}
              </p>
            </fieldset>
            <button type="submit" className="btn btn--go">{t("Speichern")}</button>
          </form>
          <h4>{t("Branche als Suchfilter")}</h4>
          <Job job={d.industry_work[c.id]}>
            {d.industry_work[c.id]?.candidates?.map((p) => (
              <Action
                key={p.term}
                action={base + "/industry/accept"}
                label={"Übernehmen: " + p.term}
                values={{ term: p.term }}
              >
                <p>
                  {p.usable
                    ? `${p.hits} Meldungen in 90 Tagen`
                    : "kaum Presse — als Filter unbrauchbar"}
                </p>
              </Action>
            ))}
          </Job>
          <Action
            action={base + "/industry"}
            disabled={d.industry_work[c.id]?.state === "läuft"}
            label="Branche vorschlagen"
          />
          <Action
            action={base + "/themes"}
            disabled={d.themes[c.id]?.state === "läuft"}
            label="Passende Themen vorschlagen"
          />
        </div>
      )}
    </article>
  );
}
function Feeds({ data: d }) {
  const [selected, setSelected] = useState(
    () => new Set(d.feeds.filter((f) => f.active).map((f) => f.name)),
  );
  return (
    <Panel title={`Feeds (${selected.size}/${d.feeds.length} ${t("aktiv")})`}>
      <form method="post" action="/settings/feeds">
        {d.feed_tiers.map(([label, feeds]) => (
          <fieldset key={label}>
            <legend>{t(label)}</legend>
            <button
              type="button"
              onClick={() =>
                setSelected((prev) => {
                  const next = new Set(prev);
                  const enable = feeds.some((f) => !prev.has(f.name));
                  feeds.forEach((f) =>
                    enable ? next.add(f.name) : next.delete(f.name),
                  );
                  return next;
                })
              }
            >
              {t("alle")}
            </button>
            <div className="platform-fields">
              {feeds.map((f) => (
                <label key={f.name} className="platform-check" title={f.url}>
                  <input
                    type="checkbox"
                    name="feed"
                    value={f.name}
                    checked={selected.has(f.name)}
                    onChange={(e) =>
                      setSelected((prev) => {
                        const next = new Set(prev);
                        e.target.checked
                          ? next.add(f.name)
                          : next.delete(f.name);
                        return next;
                      })
                    }
                  />
                  {f.name}
                  {f.industry && ` · ${f.industry}`}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <button type="submit" className="btn btn--go">{t("Feeds speichern")}</button>
      </form>
    </Panel>
  );
}
const gmailNotices = {
  verbunden: "Postfach verbunden.",
  getrennt: "Postfach getrennt und der Zugriff bei Google widerrufen.",
  "widerruf-offen":
    "Der Zugang wurde hier gelöscht, der Widerruf bei Google ließ sich aber nicht bestätigen. Bitte im Google-Konto unter „Drittanbieter-Apps“ nachsehen.",
  "nichts-verbunden": "Es war kein Postfach verbunden.",
  abgelehnt:
    "Die Freigabe wurde bei Google abgebrochen. Es wurde nichts gespeichert.",
  state:
    "Die Rückmeldung von Google gehörte nicht zu dieser Anfrage. Es wurde nichts verbunden.",
  fehler:
    "Die Verbindung mit Google ist fehlgeschlagen. Es wurde nichts gespeichert.",
};
export function SettingsPage({ data: d, onData }) {
  const submitting = useRef(false);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit(event) {
    const form = event.target;
    if (form.tagName !== "FORM" || form.method.toLowerCase() !== "post") return;
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setSaving(true);
    setSaveError("");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: new FormData(form),
      });
      if (!response.ok)
        throw new Error(
          "Die Änderung konnte nicht gespeichert werden. Bitte Eingaben prüfen und erneut versuchen.",
        );
      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }
      onData(await response.json());
    } catch (error) {
      setSaveError(error.message);
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }
  // Poll only job data. Stable React form instances retain unsaved input and files.
  const running =
    d.run_active ||
    [
      ...Object.values(d.themes),
      ...Object.values(d.rival_work),
      ...Object.values(d.industry_work),
    ].some((j) => j.state === "läuft") ||
    Object.values(d.onboarding).some((s) =>
      ["wartet", "läuft", "entwürfe"].includes(s),
    );
  useEffect(() => {
    if (!running) return;
    const controller = new AbortController();
    const timer = setInterval(async () => {
      try {
        const res = await fetch(window.location.href, {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        if (res.ok) {
          const next = await res.json();
          onData((prev) => ({
            ...prev,
            themes: next.themes,
            rival_work: next.rival_work,
            industry_work: next.industry_work,
            onboarding: next.onboarding,
            runs: next.runs,
            run_active: next.run_active,
          }));
        }
      } catch {}
    }, 4000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [running, onData]);
  return (
    <div className="platform-page" onSubmit={submit} aria-busy={saving}>
      <Notice>{saveError}</Notice>
      {saving && <Notice>Änderung wird gespeichert…</Notice>}
      <PageHeading
        eyebrow="Workspace"
        title={t("Einstellungen")}
        description="Mandanten, Datenquellen und gemeinsame Arbeitsgrundlagen."
      />
      {Object.entries(d.themes).map(([id, job]) => (
        <Job key={id} job={job} errorLabel="Themenvorschlag fehlgeschlagen">
          <Panel title={`Themen für ${job.client}`}>
            <p>
              Vorschläge — noch nichts übernommen. Treffer aus der Radar-Abfrage
              der letzten 90 Tage.
            </p>
            {job.probes?.map((p) => (
              <Action
                key={p.term}
                action={`/settings/clients/${id}/themes/accept`}
                label={"+ " + p.term}
                values={{ term: p.term }}
              >
                <p>
                  {p.usable
                    ? `${p.external} Marktmeldung(en) · ${p.own || 0} über den Mandanten selbst${p.widened ? " · ohne Branchenfilter" : ""}`
                    : "Keine Treffer — die Presse schreibt diesen Begriff nicht"}
                </p>
                {p.reason && <p>{p.reason}</p>}
                {p.samples?.[0] && <p>{p.samples[0]}</p>}
              </Action>
            ))}
          </Panel>
        </Job>
      ))}
      <Panel title="Lauf starten">
        <Notice>{d.run_error}</Notice>
        <Notice>
          {d.run_started != null
            ? "Lauf gestartet — läuft im Hintergrund."
            : ""}
        </Notice>
        <Action
          action="/settings/run"
          label={d.run_active ? "Läuft…" : "Jetzt aktualisieren"}
          disabled={d.run_active}
        >
          <Field
            name="since_days"
            label="Zeitraum"
            options={[
              ["", "Seit letztem Lauf (Standard)"],
              ...d.backfill_days.map((n) => [n, `Letzte ${n} Tage nachladen`]),
            ]}
          />
        </Action>
        <p>
          Ein Nachlauf erweitert das akzeptierte Zeitfenster. Feeds liefern nur
          ihre verfügbaren Einträge; gespeicherte Artikel werden dedupliziert.
        </p>
      </Panel>
      <Panel title="Mandanten">
        <Notice>{d.client_error}</Notice>
        <details
          id="neuer-mandant"
          open={(!!d.client_error && !d.edit_id) || undefined}
        >
          <summary>{t("+ Mandant hinzufügen")}</summary>
          <form method="post" action="/settings/clients">
            <ClientFields create />
            <p>
              Suchbegriffe entscheiden, was gefunden wird. Alarm-Themen stufen
              hoch, was schon gefunden wurde. Listen mit Komma oder Semikolon
              trennen. Keine eigene Presseschau: Alarm-Themen wirken nur auf
              bereits zugeordnete Meldungen.
            </p>
            <button type="submit" className="btn btn--go">{t("+ Mandant hinzufügen")}</button>
          </form>
        </details>
        {clientGroups
          .map(([label, belongs]) => [label, d.clients.filter(belongs)])
          .filter(([, members]) => members.length)
          .map(([label, members]) => (
            <section className="platform-client-group" key={label}>
              <h3>
                {members.length} {t(label)}
              </h3>
              {label === "im Archiv" && (
                <div className="platform-archive-head">
                  <p>
                    {t(
                      "Deaktivierte Mandanten bleiben 90 Tage im Archiv und werden danach mit allen Daten gelöscht.",
                    )}
                  </p>
                  <form method="post" action="/settings/archive/purge"
                    onSubmit={(e) => { if (!window.confirm(t("Alle Mandanten im Archiv jetzt mit allen Daten löschen? Das lässt sich nicht rückgängig machen."))) e.preventDefault(); }}>
                    <button type="submit" className="platform-icon platform-icon--danger">{t("Alle löschen")}</button>
                  </form>
                </div>
              )}
              {members.map((c) => (
                <ClientSettings key={c.id} client={c} data={d} />
              ))}
            </section>
          ))}
      </Panel>
      <Panel title={`Maßstäbe · Fassung ${d.brain_version}`} id="brain">
        <p>
          Die gemeinsamen Regeln für erzeugte Texte. Änderungen gelten für alle
          Prompts, die den jeweiligen Block verwenden.
        </p>
        <Notice>{d.brain_error}</Notice>
        {d.brain_blocks.map((b) => (
          <article
            key={b.key}
            id={`brain-${b.key}`}
            className="platform-client"
          >
            <header>
              <h3>{b.key}</h3>
              <span>
                {t(
                  b.is_orphan
                    ? "Verwaist"
                    : b.is_override
                      ? "Überschrieben"
                      : "Vorgabe",
                )}
              </span>
              <a
                href={
                  d.brain_open === b.key
                    ? `/settings#brain-${b.key}`
                    : `/settings/brain/${b.key}#brain-${b.key}`
                }
              >
                {t(d.brain_open === b.key ? "Schließen" : "Bearbeiten")}
              </a>
            </header>
            <p>
              {b.changed_at
                ? `${date(b.changed_at)} · ${b.changed_by_is_sentinel ? t(b.changed_by) : b.changed_by} · Fassung ${b.version}`
                : t("Noch nie geändert")}
            </p>
            {b.is_orphan && (
              <Notice>
                Der Block wird nicht mehr ausgeliefert. Die Überschreibung gilt
                weiter, wo ein Prompt sie verwendet.
              </Notice>
            )}
            {d.brain_open === b.key ? (
              <>
                <Action action={`/settings/brain/${b.key}`} label="Speichern">
                  <Field
                    name="text"
                    label="Wortlaut"
                    type="textarea"
                    value={b.text}
                    rows={14}
                  />
                </Action>
                {b.is_override && (
                  <Action
                    action={`/settings/brain/${b.key}/revert`}
                    label="Auf Vorgabe zurücksetzen"
                  />
                )}
                {d.brain_from_change && (
                  <Notice>{`Von einem Text hierher gekommen: Fassung ${d.brain_from_change.version}. Die übrigen Blöcke stehen in ihrem heutigen Wortlaut, nicht in dem von damals.`}</Notice>
                )}
                <h4>{t("Verlauf")}</h4>
                {d.brain_history.length ? (
                  d.brain_history.map((change) => (
                    <article
                      key={change.version}
                      id={`brain-v${change.version}`}
                    >
                      <p>
                        Fassung {change.version} · {date(change.changed_at)} ·{" "}
                        {change.changed_by_is_sentinel
                          ? t(change.changed_by)
                          : change.changed_by}
                        {change.is_revert
                          ? " · Auf die Vorgabe zurückgesetzt"
                          : ""}
                      </p>
                      <pre className="platform-pre">
                        {change.text ||
                          t(
                            "Auf die Vorgabe zurückgesetzt — der ausgelieferte Wortlaut existiert nicht mehr.",
                          )}
                      </pre>
                    </article>
                  ))
                ) : (
                  <p>
                    {t(
                      "Noch keine Änderung aufgezeichnet. Der Block ist der ausgelieferte Wortlaut.",
                    )}
                  </p>
                )}
              </>
            ) : (
              <pre className="platform-pre">{b.text}</pre>
            )}
          </article>
        ))}
      </Panel>
      <AiModels data={d.ai} />
      <div className="platform-columns">
        <Panel title="Postfach" id="gmail">
          <Notice>{gmailNotices[d.gmail_notice]}</Notice>
          {d.gmail?.is_connected ? (
            <>
              <p>
                {t("Verbunden als")} {d.gmail.email} ·{" "}
                {date(d.gmail.connected_at)}
              </p>
              <ul>
                {d.gmail.scope_words.map((w) => (
                  <li key={w}>{t(w)}</li>
                ))}
              </ul>
              {!d.gmail.may_send && (
                <Notice>
                  Nur zum Lesen verbunden. Für das Senden einmal trennen und mit
                  den erforderlichen Rechten erneut verbinden.
                </Notice>
              )}
              <Action
                action="/settings/gmail/disconnect"
                label="Postfach trennen"
              />
            </>
          ) : (
            <>
              <p>{t("Kein Postfach verbunden.")}</p>
              <Notice>
                {d.gmail?.lost
                  ? "Der Zugriff wurde bei Google entzogen, die Verbindung wurde deshalb beendet. " +
                    d.gmail.lost
                  : null}
              </Notice>
              <ul>
                {d.gmail_scopes.map((w) => (
                  <li key={w}>{t(w)}</li>
                ))}
              </ul>
              {d.gmail_configured && (
                <a className="btn" href="/settings/gmail/start">
                  {t("Postfach verbinden")}
                </a>
              )}
            </>
          )}
          {!d.gmail_configured && (
            <p>
              OAuth-Client nicht eingerichtet.{" "}
              <Source url={d.gmail_doc_url}>
                {t("Einrichtung in der Deployment-Notiz")}
              </Source>
            </p>
          )}
        </Panel>
      </div>
      <Feeds data={d} />
      <Panel title="Letzte Läufe">
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                {["Start", "Status", "Artikel", "Fehler"].map((x) => (
                  <th key={x}>{t(x)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.runs.map((run, i) => (
                <tr key={i}>
                  <td>
                    {dateTime(run.started_at)}
                    {run.is_running ? " (läuft…)" : ""}
                  </td>
                  <td>{run.status}</td>
                  <td>{run.articles_found}</td>
                  <td>
                    {run.errors?.length ? (
                      <ul>
                        {run.errors.map((e, n) => (
                          <li key={n}>{e}</li>
                        ))}
                      </ul>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!d.runs.length && <p>{t("Noch kein Lauf.")}</p>}
      </Panel>
    </div>
  );
}
