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
  ["name", "Name"],
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
function ClientSettings({ client: c, data: d }) {
  const base = `/settings/clients/${c.id}`,
    edit = Number(d.edit_id) === c.id;
  return (
    <article className="platform-client" id={`client-${c.id}`}>
      <header>
        <div>
          <h3>
            <a href={`/client/${c.id}/overview`}>{c.name}</a>
          </h3>
          <p>
            {c.industry || "—"} · {c.country} ·{" "}
            {t(c.active ? "aktiv" : "inaktiv")}
          </p>
          {d.onboarding[c.id] && <p role="status">{d.onboarding[c.id]}</p>}
          <p>
            {c.is_competitor ? "Maßstab für" : "Wettbewerber"}:{" "}
            {c.is_competitor && !c.benchmark_for.length && (
              <span>keinem Mandanten</span>
            )}
            {(c.is_competitor ? c.benchmark_for : c.competitors).map((x) => (
              <span className="tag tag--rival" key={x.id}>
                {x.name}
              </span>
            ))}
          </p>
        </div>
        <div className="platform-actions">
          <a
            href={edit ? "/settings" : `/settings?edit=${c.id}#client-${c.id}`}
          >
            {t(edit ? "Schließen" : "Bearbeiten")}
          </a>
          <Action
            action={base + "/competitor"}
            label={c.is_competitor ? "Wettbewerb" : "Mandant"}
          />
          <Action
            action={base + (c.active ? "/deactivate" : "/reactivate")}
            label={c.active ? "Deaktivieren" : "Reaktivieren"}
          />
        </div>
      </header>
      {edit && (
        <div className="platform-edit">
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
            <button type="submit">{t("Speichern")}</button>
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
          <h4>{t("Wettbewerber")}</h4>
          {c.competitors.map((r) => (
            <Action
              key={r.id}
              action={`/client/${c.id}/competitors/${r.id}/remove`}
              label="Verknüpfung lösen"
              values={{ redirect_to: `/settings?edit=${c.id}` }}
            >
              <span>{r.name}</span>
            </Action>
          ))}
          <Job
            label="Wettbewerber werden vorgeschlagen — das dauert einen Moment."
            job={d.rival_work[c.id]}
          >
            {d.rival_work[c.id]?.state === "fertig" &&
              !d.rival_work[c.id]?.rivals?.length && (
                <p>
                  Keine Wettbewerber vorgeschlagen — das Modell kennt dieses
                  Unternehmen nicht sicher genug.
                </p>
              )}
            {d.rival_work[c.id]?.rivals?.map((r) => (
              <Action
                key={r.name}
                action={`/client/${c.id}/competitors/accept`}
                label={"Hinzufügen: " + r.name}
                values={{
                  name: r.name,
                  website: r.website,
                  industry: r.industry,
                  aliases: (r.aliases || []).join("\n"),
                  redirect_to: `/settings?edit=${c.id}`,
                }}
              >
                <p>{r.reason}</p>
              </Action>
            ))}
          </Job>
          <Action
            action={base + "/rivals"}
            disabled={d.rival_work[c.id]?.state === "läuft"}
            label="Wettbewerber vorschlagen"
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
function ImportClients({ data: d, onData }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function preview(event) {
    const form = event.currentTarget.form;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/settings/import/preview", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: new FormData(form),
      });
      if (!res.ok)
        throw Error(
          "Die Vorschau konnte nicht geladen werden. Bitte Datei und Zuordnung prüfen.",
        );
      onData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Import (Excel / CSV)">
      <Notice>
        {d.import_success != null
          ? `${d.import_success} Client(s) importiert.`
          : ""}
      </Notice>
      <form
        method="post"
        action="/settings/import/commit"
        encType="multipart/form-data"
      >
        <Field
          name="file"
          label="Datei (.xlsx / .csv)"
          type="file"
          accept=".csv,.xlsx"
        />
        <p>
          Spaltenzuordnung — Spaltenüberschrift je Feld eintragen (Name ist
          Pflicht).
        </p>
        <div className="platform-fields">
          {d.map_fields.map((key) => (
            <Field
              key={key}
              name={"map_" + key}
              label={key}
              value={d.map_values[key]}
            />
          ))}
        </div>
        <div className="platform-actions">
          <button type="button" onClick={preview} disabled={busy}>
            {busy ? "Vorschau wird geladen…" : t("Vorschau")}
          </button>
          <button type="submit" disabled={busy}>
            {t("Importieren")}
          </button>
        </div>
      </form>
      <Notice>{error || d.import_error}</Notice>
      {d.import_rows && (
        <>
          <p>
            {d.import_row_total} Zeile(n) — noch nicht importiert. Vorschau:{" "}
            {d.import_rows.length} Zeilen.
          </p>
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  {d.map_fields.map((f) => (
                    <th key={f}>{f}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.import_rows.map((row, i) => (
                  <tr key={i}>
                    {d.map_fields.map((f) => (
                      <td key={f}>
                        {Array.isArray(row[f]) ? row[f].join(", ") : row[f]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
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
        <button type="submit">{t("Feeds speichern")}</button>
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
            <button type="submit">{t("+ Mandant hinzufügen")}</button>
          </form>
        </details>
        {[false, true]
          .filter((flag) => d.clients.some((c) => c.is_competitor === flag))
          .map((isCompetitor) => (
            <section
              className="platform-client-group"
              key={String(isCompetitor)}
            >
              <h3>
                {
                  d.clients.filter((c) => c.is_competitor === isCompetitor)
                    .length
                }{" "}
                {t(isCompetitor ? "Wettbewerber" : "Mandanten gesamt")}
              </h3>
              {d.clients
                .filter((c) => c.is_competitor === isCompetitor)
                .map((c) => (
                  <ClientSettings key={c.id} client={c} data={d} />
                ))}
            </section>
          ))}
      </Panel>
      <ImportClients data={d} onData={onData} />
      <Panel title="Alarm-Schwellenwert">
        <p>
          Wirkt auf künftige Läufe. Alarm-Themen lösen unabhängig vom
          Schwellenwert eine Warnung aus.
        </p>
        <Notice>{d.threshold_error}</Notice>
        <Action action="/settings/threshold" label="Speichern">
          <Field
            name="alert_threshold"
            label="Schwellenwert"
            value={d.alert_threshold}
            options={d.score_range}
          />
        </Action>
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
      <div className="platform-columns">
        <Panel title="KI-Ausweichmodell">
          <p>
            {d.fallback_ready
              ? `${t("Aktiv")} — ${d.fallback_model}`
              : t("Nicht eingerichtet")}
          </p>
          <p>
            Wird verwendet, wenn das primäre Modell sein Nutzungslimit erreicht.
            Der Schlüssel wird über die Server-Konfiguration gesetzt.
          </p>
        </Panel>
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
      <Panel title="Themen-Radar">
        {d.radar_stale == null ? (
          <>
            <p>
              Prüft gespeicherte Zuordnungen zum Themenfeld, ohne sie zu ändern.
            </p>
            <a className="btn" href="/settings?radar=1">
              {t("Radar-Treffer prüfen")}
            </a>
          </>
        ) : d.radar_stale.length ? (
          <form method="post" action="/settings/radar/cleanup">
            <p>
              {d.radar_stale.length} Treffer ohne passendes Thema. Die Artikel
              bleiben im Archiv; nur diese Zuordnungen werden gelöst.
            </p>
            {d.radar_stale.map((row) => (
              <p key={`${row.client_id}:${row.article_id}`}>
                <Hidden
                  values={{ hit: `${row.client_id}:${row.article_id}` }}
                />
                {row.client} · {row.outlet} · {dateTime(row.published_at)} ·{" "}
                <Source url={row.url}>{row.headline}</Source>
              </p>
            ))}
            <button type="submit">
              Diese {d.radar_stale.length} Zuordnungen entfernen
            </button>
          </form>
        ) : (
          <p>
            {t(
              "Alle gespeicherten Radar-Treffer tragen ein Thema ihres Mandanten.",
            )}
          </p>
        )}
      </Panel>
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
