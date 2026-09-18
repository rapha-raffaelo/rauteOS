import React from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import { Action, Field, Panel, Source, date, dateTime, t } from "./shared.jsx";
export function ArchivePage({ data: d }) {
  const client = d.client,
    base = client ? `/client/${client.id}` : "/archive",
    f = d.filters;
  return (
    <div className="platform-page">
      <PageHeading
        eyebrow={client?.name || "Recherche"}
        title={t("Archiv")}
        description={`${d.pagination.total_count} ${t("Artikel")}`}
      >
        {client && !client.is_competitor && (
          <a className="btn btn--ghost" href={`${base}/export.xlsx`} download>
            ↓ Excel
          </a>
        )}
      </PageHeading>
      <form className="archive-filters" method="get" action={base}>
        {client ? (
          <>
            <Field
              name="date_from"
              label="Von"
              type="date"
              value={f.date_from}
            />
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
                ...d.clients.map((c) => [
                  c.id,
                  c.name + (c.active ? "" : " (inaktiv)"),
                ]),
              ]}
            />
            <Field
              name="month"
              label="Monat"
              value={f.month}
              options={[
                ["", "Alle Monate"],
                ...d.months.map((m) => [m.value, m.label]),
              ]}
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
        <Field
          name="q"
          label="Suche"
          type="search"
          value={f.search}
          placeholder={t("Schlagzeile oder Zusammenfassung")}
        />
        <button type="submit">{t("Filtern")}</button>
        <a href={base}>{t("Zurücksetzen")}</a>
      </form>
      {d.radar_count > 0 && (
        <p className="archive-radar">
          {d.radar_count} Beiträge aus dem Themen-Radar der letzten{" "}
          {d.radar_days} Tage — Marktmaterial, das den Mandanten nicht nennt und
          deshalb keine Berichterstattung ist.{" "}
          <a href={`${base}/twin#marktumfeld`}>
            {t("Im Marktumfeld ansehen")} →
          </a>
        </p>
      )}
      <section id="archive-list" aria-label={t("Artikel")}>
        <div className="archive-rows">
          {d.rows.map((row, i) => (
            <article
              key={row.analysis_id || `${row.client_id}-${i}`}
              className={`feed-item${row.is_alert ? " feed-item--alert" : ""}`}
            >
              <div className="feed-item__head">
                <h2 className="feed-item__headline">
                  <Source url={row.url}>{row.headline}</Source>
                </h2>
                {row.is_alert && <span className="tag tag--alert">Alert</span>}
              </div>
              <div className="feed-item__meta">
                {row.client_id && (
                  <a className="clichip" href={`/client/${row.client_id}`}>
                    {row.client_name}
                  </a>
                )}
                <span>{row.source}</span>
                <time dateTime={row.published_at}>
                  {dateTime(row.published_at)}
                </time>
                <span className="tag">{t(row.category)}</span>
                <span
                  title={t(
                    "Wichtigkeit für diesen Mandanten, 0–10 — vom Analysemodell vergeben",
                  )}
                >
                  {row.importance}/10
                </span>
              </div>
              {row.summary && (
                <p className="feed-item__summary">{row.summary}</p>
              )}
              {row.analysis_id && (
                <Action
                  action={`/coverage/${row.analysis_id}/dismiss`}
                  label="nicht relevant"
                  values={{ redirect_to: base }}
                />
              )}
            </article>
          ))}
        </div>
        {!d.rows.length && (
          <p className="empty-state">
            {t("Keine Artikel für die gewählten Filter.")}
          </p>
        )}
        <nav className="pagination" aria-label="Archivseiten">
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
                <a href={`${base}/twin#wettbewerb`}>{t("Vergleichsgruppe")}</a>
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
                <a href={`${base}/gelegenheit/${o.id}`}>{o.headline}</a>
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
                    href={`${base}/advice?eintrag=anlass-${o.angle_id}#impulse-${o.angle_id}`}
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
