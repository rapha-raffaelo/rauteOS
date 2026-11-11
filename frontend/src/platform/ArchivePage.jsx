import React from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import { Action, Field, Panel, Source, date, dateTime, t } from "./shared.jsx";
export function ArchivePage({ data: d }) {
  const client = d.client,
    clientBase = client ? `/client/${client.id}` : "",
    base = client ? `${clientBase}/medien` : "/medien",
    f = d.filters,
    active = Boolean(
      f.search || f.client || f.month || f.tier || f.source || f.category || f.date_from || f.date_to,
    );
  return (
    <div className="platform-page">
      <PageHeading
        eyebrow={client?.name || "Recherche"}
        title={t("Medien")}
        description={`${d.pagination.total_count} ${t("Artikel")}`}
      >
        {client && !client.is_competitor && (
          <a className="btn btn--ghost" href={`${clientBase}/export.xlsx`} download>
            ↓ Excel
          </a>
        )}
      </PageHeading>
      <form
        className="archive-filters archive-bar"
        method="get"
        action={base}
        onChange={(e) =>
          e.target.tagName === "SELECT" || e.target.type === "date"
            ? e.currentTarget.requestSubmit()
            : null
        }
      >
        <label className="archive-search">
          <span className="sr-only">{t("Suche")}</span>
          <input
            name="q"
            type="search"
            defaultValue={f.search}
            placeholder={t("Schlagzeile oder Zusammenfassung durchsuchen …")}
          />
          <button type="submit" className="btn btn--go">
            {t("Suchen")}
          </button>
        </label>
        <div className="archive-selects">
          {client ? (
            <>
              <Field name="date_from" label="Von" type="date" value={f.date_from} />
              <Field name="date_to" label="Bis" type="date" value={f.date_to} />
            </>
          ) : (
            <>
              <Field
                name="client"
                label="Mandant"
                value={f.client}
                options={[
                  ["", "Alle Mandanten"],
                  ...d.clients.map((c) => [c.id, c.name + (c.active ? "" : " (inaktiv)")]),
                ]}
              />
              <Field
                name="month"
                label="Monat"
                value={f.month}
                options={[["", "Alle Monate"], ...d.months.map((m) => [m.value, m.label])]}
              />
              <Field
                name="tier"
                label="Medien-Tier"
                value={f.tier}
                options={[["", "Alle Tiers"], ...d.tiers]}
              />
              {f.with_competitors && (
                <input type="hidden" name="with_competitors" value="1" />
              )}
            </>
          )}
          <Field
            name="source"
            label="Publisher"
            value={f.source}
            options={[["", "Alle Publisher"], ...d.sources]}
          />
          <Field
            name="category"
            label="Kategorie"
            value={f.category}
            options={[["", "Alle Kategorien"], ...d.categories]}
          />
          {active && (
            <a className="archive-reset" href={base}>
              {t("Filter zurücksetzen")}
            </a>
          )}
        </div>
      </form>
      {d.radar_count > 0 && (
        <p className="archive-radar">
          {d.radar_count} Beiträge aus dem Themen-Radar der letzten{" "}
          {d.radar_days} Tage: Marktmaterial, das den Mandanten nicht nennt und
          deshalb keine Berichterstattung ist.{" "}
          <a href={`${clientBase}/wettbewerb#marktumfeld`}>{t("Im Marktumfeld ansehen")}</a>
        </p>
      )}
      <section id="archive-list" aria-label={t("Artikel")}>
        <div className="archive-rows">
          {byDay(d.rows).map(([day, rows]) => (
            <div className="archive-day" key={day}>
              <h2 className="archive-day__title">{dayLabel(rows[0].published_at)}</h2>
              {rows.map((row, i) => (
                <article
                  key={row.analysis_id || `${row.client_id}-${i}`}
                  className={`feed-item archive-item${row.is_alert ? " feed-item--alert" : ""}`}
                >
                  <time className="archive-item__time" dateTime={row.published_at} title={dateTime(row.published_at)}>
                    {clock(row.published_at)}
                  </time>
                  <div className="archive-item__body">
                    <div className="feed-item__meta">
                      {row.client_id && (
                        <a className="clichip" href={`/client/${row.client_id}/medien`}>
                          {row.client_name}
                        </a>
                      )}
                      <span className="archive-item__source">{row.source}</span>
                      {row.category && (
                        <span className="tag" data-category={row.category}>{label(t(row.category))}</span>
                      )}
                      {row.is_alert && <span className="tag tag--alert">Alert</span>}
                    </div>
                    <h3 className="feed-item__headline">
                      <Source url={row.url}>{headline(row)}</Source>
                    </h3>
                    {row.summary && <p className="feed-item__summary">{row.summary}</p>}
                  </div>
                  <div className="archive-item__side">
                    <span
                      className={`archive-score archive-score--${weight(row.importance)}`}
                      title={t("Wichtigkeit für diesen Mandanten, 0–10 — vom Analysemodell vergeben")}
                    >
                      {row.importance}/10
                    </span>
                    {row.analysis_id && (
                      <Action
                        action={`/coverage/${row.analysis_id}/dismiss`}
                        label="nicht relevant"
                        values={{ redirect_to: base }}
                      />
                    )}
                  </div>
                </article>
              ))}
            </div>
          ))}
        </div>
        {!d.rows.length && (
          <p className="empty-state">{t("Keine Artikel für die gewählten Filter.")}</p>
        )}
        <nav className="pagination" aria-label="Medienseiten">
          {d.pagination.prev_url && (
            <a rel="prev" href={d.pagination.prev_url}>
              {t("← Neuer")}
            </a>
          )}
          <span>
            {t("Seite")} {d.pagination.page} / {d.pagination.total_pages}
          </span>
          {d.pagination.next_url && (
            <a rel="next" href={d.pagination.next_url}>
              {t("Älter →")}
            </a>
          )}
        </nav>
      </section>
      {client && (
        <Panel title="Share of Voice">
          <p>
            {t("letzte 30 Tage")}
            {!client.is_competitor && (
              <>
                {" "}
                ·{" "}
                <a href={`${clientBase}/wettbewerb`}>{t("Vergleichsgruppe")}</a>
              </>
            )}
          </p>
          {d.voice.length > 1 ? (
            <table className="data">
              <thead>
                <tr>
                  <th>{t("Unternehmen")}</th>
                  <th>{t("Meldungen")}</th>
                  <th>Alerts</th>
                  <th>{t("Anteil")}</th>
                </tr>
              </thead>
              <tbody>
                {d.voice.map((v) => (
                  <tr key={v.client_id}>
                    <td>
                      <a href={`/client/${v.client_id}`}>{v.name}</a>
                    </td>
                    <td>{v.mentions}</td>
                    <td>{v.alerts}</td>
                    <td>{(v.share * 100).toFixed(1)} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>{t("Noch keine Vergleichsgruppe.")}</p>
          )}
        </Panel>
      )}
      {!!d.opportunities?.length && (
        <Panel title="Gelegenheiten aus der schnellen Spur">
          {d.opportunities.map((o) => (
            <article className="feed-item" key={o.id}>
              <h3>
                <a href={`${clientBase}/gelegenheit/${o.id}`}>{o.headline}</a>
              </h3>
              <p>
                <Source url={o.url}>{t("Ursprungsbeitrag")}</Source> ·{" "}
                {o.source} · {date(o.published_at)} · {o.pickup_count}×
                aufgegriffen
              </p>
              <p>{o.reason}</p>
              <p>
                {t(o.dismissed_at ? "Verworfen am" : "Abgelaufen am")}{" "}
                {date(o.dismissed_at || o.window_ends_at)} ·{" "}
                {o.angle_id && o.texts ? (
                  <a
                    href={`${clientBase}/advice?eintrag=anlass-${o.angle_id}#impulse-${o.angle_id}`}
                  >
                    {o.texts} Text(e) ansehen →
                  </a>
                ) : (
                  t("Kein Text entstanden.")
                )}
              </p>
            </article>
          ))}
        </Panel>
      )}
    </div>
  );
}

const zone = () => {
  try {
    return JSON.parse(document.getElementById("react-shell-data")?.textContent || "{}").timezone || "Europe/Berlin";
  } catch {
    return "Europe/Berlin";
  }
};
const dayKey = (iso) =>
  iso ? new Intl.DateTimeFormat("en-CA", { timeZone: zone() }).format(new Date(iso)) : "";
const clock = (iso) =>
  iso ? new Intl.DateTimeFormat("de-DE", { timeZone: zone(), hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "";
function dayLabel(iso) {
  if (!iso) return t("Ohne Datum");
  const key = dayKey(iso), today = dayKey(new Date().toISOString());
  const yesterday = dayKey(new Date(Date.now() - 864e5).toISOString());
  if (key === today) return t("Heute");
  if (key === yesterday) return t("Gestern");
  return new Intl.DateTimeFormat("de-DE", { timeZone: zone(), weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
}
// Rows arrive newest first; consecutive rows of one day form a group.
function byDay(rows) {
  const out = [];
  for (const row of rows) {
    const key = dayKey(row.published_at);
    if (out.length && out[out.length - 1][0] === key) out[out.length - 1][1].push(row);
    else out.push([key, [row]]);
  }
  return out;
}
// Google News appends " - Publisher" to every headline; the publisher is
// already in the line above it.
function headline(row) {
  const suffix = ` - ${row.source}`;
  return row.source && row.headline?.endsWith(suffix) ? row.headline.slice(0, -suffix.length) : row.headline;
}
const label = (text) => (text ? text[0].toUpperCase() + text.slice(1) : text);
const weight = (score) => (score >= 7 ? "high" : score >= 4 ? "mid" : "low");
