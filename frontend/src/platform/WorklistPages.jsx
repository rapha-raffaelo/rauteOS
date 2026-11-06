import React, { useState } from "react";
import { PageHeading } from "../components/PageHeading.jsx";
import { Action, Field, Notice, t } from "./shared.jsx";

// Spec 10: Aufgaben, LinkedIn and Sales CRM. Plain forms that post and come
// back; the server checks every value (newspulse.worklists).

const day = (value) =>
  value ? new Date(value + (value.length === 10 ? "T12:00:00" : "")).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "";
const today = () => new Date().toISOString().slice(0, 10);
const euro = (n) => `${(n || 0).toLocaleString("de-DE")} €`;

function Toggle({ open, onClick, children }) {
  return (
    <button type="button" className="btn btn--ghost" aria-expanded={open} onClick={onClick}>
      {t(children)}
    </button>
  );
}

function Form({ action, fields, submit, onCancel }) {
  return (
    <form method="post" action={action} className="wl-form">
      <div className="wl-form__grid">{fields}</div>
      <div className="wl-form__acts">
        <button type="submit" className="btn btn--go">{t(submit)}</button>
        {onCancel && <button type="button" className="btn btn--quiet" onClick={onCancel}>{t("Abbrechen")}</button>}
      </div>
    </form>
  );
}

const clientOptions = (clients, empty) => [["", t(empty)], ...clients.map((c) => [String(c.id), c.name])];

// --- Aufgaben ----------------------------------------------------------------------

function taskFields(d, v = {}) {
  return (
    <>
      <Field name="title" label="Aufgabe" value={v.title} required maxLength={200} />
      <Field name="client_id" label="Mandant" value={v.client?.id ?? v.client_id ?? ""} options={clientOptions(d.clients, "Agentur (kein Mandant)")} />
      <Field name="priority" label="Priorität" value={v.priority || "mittel"} options={d.priorities} />
      <Field name="status" label="Status" value={v.status || "offen"} options={d.states} />
      <Field name="due_on" label="Fällig am" type="date" value={v.due_on || ""} />
      <Field name="owner" label="Zuständig" value={v.owner} maxLength={120} />
      <Field name="context_href" label="Link zum Vorgang (optional)" value={v.context_href} maxLength={300} placeholder="/client/1/opportunities?…" />
      <Field name="note" label="Notiz" type="textarea" value={v.note} rows={3} />
    </>
  );
}

const NEXT = { offen: ["in_arbeit", "Beginnen"], in_arbeit: ["erledigt", "Erledigt"], erledigt: ["offen", "Wieder öffnen"] };

export function TasksPage({ data: d }) {
  const [adding, setAdding] = useState(!!d.error && !!Object.keys(d.draft || {}).length);
  const [editing, setEditing] = useState(null);
  const label = Object.fromEntries(d.states);
  const prio = Object.fromEntries(d.priorities);
  const now = today();
  const open = d.tasks.filter((x) => x.status !== "erledigt");
  // The heading counts every open task, not the filtered view.
  const total = d.open_total ?? open.length;
  const dueCount = (d.due_on ?? open.map((x) => x.due_on).filter(Boolean)).filter((x) => x <= now).length;
  const filterHref = (status) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (d.filter.client) q.set("client", d.filter.client);
    return "/aufgaben" + (q.toString() ? "?" + q : "");
  };
  return (
    <section className="worklist">
      <PageHeading eyebrow="ARBEITSPLATZ" title="Aufgaben"
        description={`${total} ${t("offen")} · ${dueCount} ${t("heute fällig oder überfällig")}`} />
      <Notice>{d.error}</Notice>
      <div className="wl-bar">
        <nav className="workspace-links" aria-label={t("Status")}>
          {[["", "Alle"], ...d.states].map(([key, text]) => (
            <a key={key} href={filterHref(key)} aria-current={(d.filter.status || "") === key ? "page" : undefined}>{t(text)}</a>
          ))}
        </nav>
        <form method="get" action="/aufgaben" className="wl-filter">
          {d.filter.status && <input type="hidden" name="status" value={d.filter.status} />}
          <select name="client" defaultValue={d.filter.client || ""} aria-label={t("Mandant")} onChange={(e) => e.target.form.submit()}>
            {clientOptions(d.clients, "Alle Mandanten").map(([v, text]) => <option key={v} value={v}>{text}</option>)}
          </select>
        </form>
        <Toggle open={adding} onClick={() => setAdding(!adding)}>+ Neue Aufgabe</Toggle>
      </div>
      {adding && <div className="wl-card"><Form action="/aufgaben" fields={taskFields(d, d.draft)} submit="Aufgabe anlegen" onCancel={() => setAdding(false)} /></div>}
      <div className="wl-card">
        {d.tasks.map((x) => {
          const late = x.status !== "erledigt" && x.due_on && x.due_on < now;
          const [next, nextLabel] = NEXT[x.status];
          return (
            <article key={x.id} id={`task-${x.id}`} className={`wl-row${x.status === "erledigt" ? " wl-row--done" : ""}`}>
              <Action action={`/aufgaben/${x.id}`} label={x.status === "erledigt" ? "↺" : "✓"} values={{ status: x.status === "erledigt" ? "offen" : "erledigt" }} className="wl-check" />
              <div className="wl-row__b">
                <h2>{x.context_href ? <a href={x.context_href}>{x.title}</a> : x.title}</h2>
                <p>{[x.client?.name || t("Agentur"), x.due_on && `${t("fällig")} ${day(x.due_on)}`, x.owner, label[x.status]].filter(Boolean).join(" · ")}</p>
                {x.note && <p className="wl-note">{x.note}</p>}
                {editing === x.id && <Form action={`/aufgaben/${x.id}`} fields={taskFields(d, x)} submit="Speichern" onCancel={() => setEditing(null)} />}
              </div>
              <span className={`wl-badge wl-badge--${late ? "late" : x.priority}`}>{late ? t("Überfällig") : prio[x.priority]}</span>
              <div className="wl-acts">
                {x.status !== "erledigt" && <Action action={`/aufgaben/${x.id}`} label={nextLabel} values={{ status: next }} />}
                <button type="button" className="btn btn--quiet" onClick={() => setEditing(editing === x.id ? null : x.id)}>{t("Bearbeiten")}</button>
                <Action action={`/aufgaben/${x.id}/delete`} label="Löschen" className="wl-del" />
              </div>
            </article>
          );
        })}
        {!d.tasks.length && <p className="wl-empty">{t("Keine Aufgaben in dieser Ansicht.")}</p>}
      </div>
    </section>
  );
}

// --- LinkedIn ----------------------------------------------------------------------

function postFields(d, v = {}) {
  return (
    <>
      <Field name="title" label="Arbeitstitel" value={v.title} required maxLength={200} />
      <Field name="client_id" label="Mandant" value={v.client?.id ?? v.client_id ?? ""} options={clientOptions(d.clients, "Mandant wählen")} required />
      <Field name="author" label="Autor / Sprecher" value={v.author} maxLength={120} />
      <Field name="status" label="Status" value={v.status || "idee"} options={d.states} />
      <Field name="planned_on" label="Geplant für" type="date" value={v.planned_on || ""} />
      <Field name="published_url" label="Link nach Veröffentlichung" value={v.published_url} maxLength={500} placeholder="https://www.linkedin.com/…" />
      <Field name="body" label="Text" type="textarea" value={v.body} rows={6} maxLength={3000} />
    </>
  );
}

function Board({ columns, render }) {
  return <div className="wl-board">{columns.map((c) => (
    <section key={c.key} className="wl-col" aria-label={c.label}>
      <header><h2>{c.label}</h2><span>{c.note}</span></header>
      {c.items.map(render)}
      {!c.items.length && <p className="wl-empty">{t("Leer")}</p>}
    </section>
  ))}</div>;
}

function Move({ action, field, keys, current }) {
  const i = keys.indexOf(current);
  return (
    <div className="wl-move">
      {i > 0 && <Action action={action} label="←" values={{ [field]: keys[i - 1] }} />}
      {i < keys.length - 1 && <Action action={action} label="→" values={{ [field]: keys[i + 1] }} />}
    </div>
  );
}

// What RauteOS already has for LinkedIn: the posts written in a chance, and the
// open chances themselves. Taking one over puts it on the board; nothing moves
// there by itself.
function Suggestions({ texts = [], chances = [] }) {
  if (!texts.length && !chances.length) {
    return <p className="wl-hint">{t("Noch keine Vorschläge. Einen LinkedIn-Post schreibt RauteOS in einer Chance unter Umsetzung; offene Chancen erscheinen hier als Ideen.")}</p>;
  }
  return (
    <div className="wl-suggest">
      {[["Von RauteOS geschrieben", texts], ["Ideen aus offenen Chancen", chances]].map(([title, items]) => (
        <section key={title} className="wl-card" aria-label={t(title)}>
          <h2 className="wl-card__h">{t(title)}</h2>
          {items.map((x) => (
            <article key={x.id ?? x.href} className="wl-row">
              <div className="wl-row__b">
                <h2><a href={x.href}>{x.title}</a></h2>
                <p>{[x.client.name, x.speaker, x.written_at && day(x.written_at.slice(0, 10)), x.id && t(x.released ? "freigegeben" : "Entwurf")].filter(Boolean).join(" · ")}</p>
                {x.excerpt && <p className="wl-note">{x.excerpt}</p>}
              </div>
              <div className="wl-acts">
                {x.id
                  ? <Action action={`/linkedin/from-text/${x.id}`} label="Übernehmen" />
                  : <Action action="/linkedin/from-chance" label="Als Idee übernehmen" values={{ client_id: x.client.id, title: x.title.slice(0, 200), context_href: x.href }} />}
              </div>
            </article>
          ))}
          {!items.length && <p className="wl-empty">{t("Nichts Neues.")}</p>}
        </section>
      ))}
    </div>
  );
}

const moment = (iso) =>
  iso ? new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";

// The signed-in person's own LinkedIn profile: RauteOS posts through it.
function Account({ a = {} }) {
  if (!a.configured) return <p className="wl-hint">{t("Die LinkedIn-Anbindung ist auf dem Server noch nicht eingerichtet. Bis dahin hier planen und auf LinkedIn selbst posten.")}</p>;
  const connect = (label) => <a className="btn btn--go" href="/linkedin/connect">{t(label)}</a>;
  if (!a.connected) {
    return (
      <div className="wl-account">
        <p>{t(a.lost || a.expired ? "Deine LinkedIn-Verbindung ist abgelaufen." : "Verbinde dein LinkedIn-Profil, dann postet RauteOS freigegebene Beiträge direkt oder zum geplanten Zeitpunkt.")}</p>
        {connect(a.lost || a.expired ? "Neu verbinden" : "Mit LinkedIn verbinden")}
      </div>
    );
  }
  return (
    <div className="wl-account">
      <p>{t("Verbunden als")} <strong>{a.name || t("dein Profil")}</strong> · {t(a.expiring ? "läuft ab am" : "gültig bis")} {day(a.expires_at.slice(0, 10))}</p>
      {a.expiring && connect("Neu verbinden")}
      <Action action="/linkedin/disconnect" label="Trennen" className="wl-quiet" />
    </div>
  );
}

// Posting one card: now, or at a moment the scheduler keeps.
function OnLinkedIn({ p, a = {} }) {
  if (p.on_linkedin) return null;
  const error = p.post_error && <p className="wl-error" role="alert">{p.post_error}</p>;
  if (p.post_at) {
    return (
      <div className="wl-li">
        <p>{t("Geht am")} {moment(p.post_at)} {t("auf LinkedIn raus")}{p.post_as ? ` · ${p.post_as}` : ""}</p>
        <Action action={`/linkedin/${p.id}/unschedule`} label="Nicht mehr einplanen" className="wl-quiet" />
      </div>
    );
  }
  if (!a.connected || !p.body) return error || null;
  return (
    <div className="wl-li">
      {error}
      <form method="post" action={`/linkedin/${p.id}/publish`} className="platform-action"
        onSubmit={(e) => { if (!window.confirm(t("Diesen Beitrag jetzt öffentlich auf deinem LinkedIn-Profil posten?"))) e.preventDefault(); }}>
        <button type="submit">{t("Jetzt auf LinkedIn posten")}</button>
      </form>
      <form method="post" action={`/linkedin/${p.id}/schedule`} className="wl-li__plan">
        <label><span className="sr-only">{t("Zeitpunkt")}</span>
          <input type="datetime-local" name="post_at" required defaultValue={p.planned_on ? `${p.planned_on}T09:00` : ""} /></label>
        <button type="submit" className="btn btn--quiet">{t("Einplanen")}</button>
      </form>
    </div>
  );
}

export function LinkedInPage({ data: d }) {
  const [adding, setAdding] = useState(!!d.error && !!Object.keys(d.draft || {}).length);
  const [editing, setEditing] = useState(null);
  const keys = d.states.map(([k]) => k);
  const columns = d.states.map(([key, label]) => ({ key, label: t(label), note: "", items: d.posts.filter((p) => p.status === key) }));
  return (
    <section className="worklist">
      <PageHeading eyebrow="KOMMUNIKATION" title="LinkedIn" description="Redaktionsarbeit für die Sprecher der Mandanten. Geplant, freigegeben und gepostet wird hier." />
      <Notice>{d.error || d.notice}</Notice>
      <div className="wl-bar"><Account a={d.account} /><Toggle open={adding} onClick={() => setAdding(!adding)}>+ Neuer Beitrag</Toggle></div>
      {adding && <div className="wl-card"><Form action="/linkedin" fields={postFields(d, d.draft)} submit="Beitrag anlegen" onCancel={() => setAdding(false)} /></div>}
      <Suggestions {...(d.suggestions || {})} />
      <Board columns={columns} render={(p) => (
        <article key={p.id} id={`post-${p.id}`} className="wl-item">
          <h3>{p.source_href ? <a href={p.source_href}>{p.title}</a> : p.title}</h3>
          <p>{[p.client.name, p.author, p.planned_on && day(p.planned_on)].filter(Boolean).join(" · ")}</p>
          {p.body && <p className="wl-note">{p.body.slice(0, 140)}{p.body.length > 140 ? " …" : ""}</p>}
          {p.published_url && <a href={p.published_url} target="_blank" rel="noreferrer">{t("Auf LinkedIn ansehen")}</a>}
          <OnLinkedIn p={p} a={d.account} />
          <div className="wl-item__acts">
            <Move action={`/linkedin/${p.id}`} field="status" keys={keys} current={p.status} />
            <button type="button" className="btn btn--quiet" onClick={() => setEditing(editing === p.id ? null : p.id)}>{t("Bearbeiten")}</button>
          </div>
          {editing === p.id && <><Form action={`/linkedin/${p.id}`} fields={postFields(d, p)} submit="Speichern" onCancel={() => setEditing(null)} />
            <Action action={`/linkedin/${p.id}/delete`} label="Beitrag löschen" className="wl-del" /></>}
        </article>
      )} />
    </section>
  );
}

// --- Sales CRM ---------------------------------------------------------------------

function dealFields(d, v = {}) {
  return (
    <>
      <Field name="company" label="Unternehmen" value={v.company} required maxLength={200} />
      <Field name="stage" label="Phase" value={v.stage || "lead"} options={d.stages} />
      <Field name="contact_name" label="Ansprechpartner" value={v.contact_name} maxLength={120} />
      <Field name="contact_email" label="E-Mail" type="email" value={v.contact_email} maxLength={200} />
      <Field name="value_eur" label="Potenzial pro Monat (€)" type="number" min={0} value={v.value_eur ?? ""} />
      <Field name="owner" label="Betreut von" value={v.owner} maxLength={120} />
      <Field name="next_step" label="Nächster Schritt" value={v.next_step} maxLength={300} />
      <Field name="next_step_on" label="Am" type="date" value={v.next_step_on || ""} />
      <Field name="note" label="Notiz" type="textarea" value={v.note} rows={3} />
    </>
  );
}

export function SalesPage({ data: d }) {
  const [adding, setAdding] = useState(!!d.error && !!Object.keys(d.draft || {}).length);
  const [editing, setEditing] = useState(null);
  const keys = d.stages.map(([k]) => k);
  const columns = d.pipeline.map((c) => ({ key: c.stage, label: t(c.label), note: c.value ? euro(c.value) : "", items: c.deals }));
  return (
    <section className="worklist">
      <PageHeading eyebrow="WACHSTUM" title="Sales CRM" description={`${t("Offenes Potenzial")}: ${euro(d.open_value)} ${t("pro Monat")}`} />
      <Notice>{d.error}</Notice>
      <div className="wl-bar"><span /><Toggle open={adding} onClick={() => setAdding(!adding)}>+ Neuer Deal</Toggle></div>
      {adding && <div className="wl-card"><Form action="/sales" fields={dealFields(d, d.draft)} submit="Deal anlegen" onCancel={() => setAdding(false)} /></div>}
      <Board columns={columns} render={(x) => (
        <article key={x.id} id={`deal-${x.id}`} className="wl-item">
          <h3>{x.company}</h3>
          <p>{[x.contact_name, x.value_eur != null && `${euro(x.value_eur)}/Monat`, x.owner].filter(Boolean).join(" · ")}</p>
          {x.next_step && <p className="wl-note">{t("Nächster Schritt")}: {x.next_step}{x.next_step_on ? ` (${day(x.next_step_on)})` : ""}</p>}
          <div className="wl-item__acts">
            <Move action={`/sales/${x.id}`} field="stage" keys={keys} current={x.stage} />
            <button type="button" className="btn btn--quiet" onClick={() => setEditing(editing === x.id ? null : x.id)}>{t("Bearbeiten")}</button>
          </div>
          {editing === x.id && <><Form action={`/sales/${x.id}`} fields={dealFields(d, x)} submit="Speichern" onCancel={() => setEditing(null)} />
            <Action action={`/sales/${x.id}/delete`} label="Deal löschen" className="wl-del" /></>}
        </article>
      )} />
    </section>
  );
}
