import React, { useEffect, useMemo, useState } from "react";
import { Notice, t } from "./shared.jsx";

// Aufgaben as a task manager in the manner of Microsoft To Do and Apple's
// Reminders: lists on the left, a quick add on top, round checkboxes, a star
// for what matters, and the details of one task on the right.
//
// Every change is a plain form that posts and comes back to the same list
// (``redirect_to``); the server checks each value (newspulse.worklists). The
// lists themselves are views over the same tasks, computed here.

const isoToday = () => new Date().toLocaleDateString("en-CA");
const shortDay = (iso) => {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  const today = isoToday();
  const tomorrow = new Date(Date.now() + 864e5).toLocaleDateString("en-CA");
  if (iso === today) return t("Heute");
  if (iso === tomorrow) return t("Morgen");
  return d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });
};

const SMART = [
  ["heute", "Heute", "☀"],
  ["geplant", "Geplant", "▦"],
  ["wichtig", "Wichtig", "★"],
  ["alle", "Alle", "≡"],
  ["erledigt", "Erledigt", "✓"],
];

function belongs(list, x, me) {
  const open = x.status !== "erledigt";
  const today = isoToday();
  if (list === "erledigt") return !open;
  if (!open) return false;
  if (list === "heute") return !!x.due_on && x.due_on <= today;
  if (list === "geplant") return !!x.due_on;
  if (list === "wichtig") return x.priority === "hoch";
  if (list === "intern") return !x.client;
  if (list === "mir") return !!me && x.assignees.includes(me);
  if (list.startsWith("person:")) return x.assignees.includes(list.slice(7));
  if (list.startsWith("kunde:")) return String(x.client?.id) === list.slice(6);
  return true; // alle
}

function listTitle(list, d) {
  const smart = SMART.find(([key]) => key === list);
  if (smart) return t(smart[1]);
  if (list === "intern") return t("Intern");
  if (list === "mir") return t("Mir zugewiesen");
  if (list.startsWith("person:")) return d.team.find((p) => p.key === list.slice(7))?.name || list;
  if (list.startsWith("kunde:")) return d.clients.find((c) => String(c.id) === list.slice(6))?.name || t("Kunde");
  return t("Alle");
}

// What a task added to this list should start with, so it lands where it was typed.
function defaultsFor(list) {
  const today = isoToday();
  if (list === "heute") return { due_on: today };
  if (list === "wichtig") return { priority: "hoch" };
  if (list.startsWith("person:")) return { assignees: list.slice(7) };
  if (list.startsWith("kunde:")) return { client_id: list.slice(6) };
  return {};
}

const href = (list, task) => {
  const q = new URLSearchParams();
  if (list && list !== "alle") q.set("liste", list);
  if (task) q.set("aufgabe", task);
  return "/aufgaben" + (q.toString() ? "?" + q : "");
};

function Hidden({ values }) {
  return Object.entries(values).map(([k, v]) => <input key={k} type="hidden" name={k} value={v ?? ""} />);
}

function Check({ task, back }) {
  const done = task.status === "erledigt";
  return (
    <form method="post" action={`/aufgaben/${task.id}`} className="tm-check">
      <Hidden values={{ status: done ? "offen" : "erledigt", redirect_to: back }} />
      <button type="submit" className={`tm-circle${done ? " tm-circle--done" : ""}`}
        aria-label={`${t(done ? "Wieder öffnen" : "Erledigt")}: ${task.title}`}>{done ? "✓" : ""}</button>
    </form>
  );
}

function Star({ task, back }) {
  const on = task.priority === "hoch";
  return (
    <form method="post" action={`/aufgaben/${task.id}`} className="tm-star-form">
      <Hidden values={{ priority: on ? "mittel" : "hoch", redirect_to: back }} />
      <button type="submit" className={`tm-star${on ? " tm-star--on" : ""}`} aria-pressed={on}
        aria-label={`${t("Wichtig")}: ${task.title}`}>{on ? "★" : "☆"}</button>
    </form>
  );
}

function Row({ task, d, list, selected }) {
  const back = href(list, selected ? task.id : null);
  const late = task.status !== "erledigt" && task.due_on && task.due_on < isoToday();
  const names = Object.fromEntries(d.team.map((p) => [p.key, p.name]));
  return (
    <li className={`tm-row${selected ? " tm-row--on" : ""}${task.status === "erledigt" ? " tm-row--done" : ""}`} id={`task-${task.id}`}>
      <Check task={task} back={href(list, selected ? task.id : null)} />
      <a className="tm-row__main" href={href(list, task.id)} aria-current={selected ? "true" : undefined}>
        <span className="tm-row__title">{task.title}</span>
        <span className="tm-row__meta">
          <span className={`tm-chip${task.client ? " tm-chip--client" : ""}`}>{task.client ? task.client.name : t("Intern")}</span>
          {task.due_on && <span className={`tm-chip${late ? " tm-chip--late" : ""}`}>▦ {shortDay(task.due_on)}</span>}
          {task.assignees.map((key) => <span className="tm-chip tm-chip--person" key={key}>@{names[key] || key}</span>)}
          {task.note && <span className="tm-chip" title={task.note}>✎</span>}
        </span>
      </a>
      <Star task={task} back={back} />
    </li>
  );
}

function Details({ task, d, list }) {
  const back = href(list, task.id);
  return (
    <aside className="tm-detail" aria-label={t("Aufgabe bearbeiten")}>
      <div className="tm-detail__head">
        <Check task={task} back={back} />
        <a className="tm-close" href={href(list)} aria-label={t("Details schließen")}>×</a>
      </div>
      <form method="post" action={`/aufgaben/${task.id}`} className="tm-detail__form">
        <input type="hidden" name="redirect_to" value={back} />
        <input type="hidden" name="status" value={task.status} />
        <label className="tm-field"><span>{t("Aufgabe")}</span>
          <input name="title" defaultValue={task.title} required maxLength={200} /></label>
        <fieldset className="tm-field tm-people">
          <legend>{t("Zuständig")}</legend>
          {d.team.map((p) => (
            <label key={p.key} className="tm-tag">
              <input type="checkbox" name="assignees" value={p.key} defaultChecked={task.assignees.includes(p.key)} />
              <span>@{p.name}</span>
            </label>
          ))}
        </fieldset>
        <label className="tm-field"><span>{t("Kunde")}</span>
          <select name="client_id" defaultValue={task.client?.id ?? ""}>
            <option value="">{t("Intern (kein Kunde)")}</option>
            {d.clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <small>{t("Einem Kunden zugeordnet, erscheint die Aufgabe auch auf seinem Dashboard.")}</small>
        </label>
        <label className="tm-field"><span>{t("Fällig am")}</span>
          <input type="date" name="due_on" defaultValue={task.due_on || ""} /></label>
        <label className="tm-field"><span>{t("Priorität")}</span>
          <select name="priority" defaultValue={task.priority}>
            {d.priorities.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
          </select></label>
        <label className="tm-field"><span>{t("Notiz")}</span>
          <textarea name="note" defaultValue={task.note} rows={5} /></label>
        <input type="hidden" name="context_href" value={task.context_href || ""} />
        {task.context_href && <a className="tm-link" href={task.context_href}>{t("Zum Vorgang")} →</a>}
        <button type="submit" className="btn btn--go">{t("Speichern")}</button>
      </form>
      <form method="post" action={`/aufgaben/${task.id}/delete`} className="tm-detail__delete"
        onSubmit={(e) => { if (!window.confirm(t("Diese Aufgabe endgültig löschen?"))) e.preventDefault(); }}>
        <input type="hidden" name="redirect_to" value={href(list)} />
        <button type="submit" className="btn btn--quiet tm-danger">{t("Löschen")}</button>
      </form>
    </aside>
  );
}

// What the Desk counts as "Entscheidungen offen". They are settled where they
// live (the letter, the impulse, the profile), so each row opens that place.
const DECISION = { kundenfreigabe: "Kundenfreigabe", freigabe: "Freigabe", impuls: "Impuls", profil: "Profil" };

function Decisions({ items }) {
  if (!items?.length) return null;
  return (
    <section className="tm-decisions" id="entscheidungen" aria-label={t("Offene Entscheidungen")}>
      <h2>{t("Offene Entscheidungen")} <span>{items.length}</span></h2>
      <ul>
        {items.map((x, i) => (
          <li key={`${x.href}-${i}`}>
            <a href={x.href}>
              <span className="tm-row__title">{x.title}</span>
              <span className="tm-row__meta"><span className="tm-chip tm-chip--client">{x.client.name}</span>
                <span className="tm-chip">{t(DECISION[x.kind] || x.kind)}</span></span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TasksPage({ data: d }) {
  const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
  const list = params.get("liste") || "alle";
  const selectedId = Number(params.get("aufgabe")) || null;
  const [showDone, setShowDone] = useState(false);
  const tasks = d.tasks;
  const me = d.me;
  const count = (key) => tasks.filter((x) => belongs(key, x, me)).length;
  const shown = useMemo(() => {
    const rows = tasks.filter((x) => belongs(list, x, me));
    if (list === "geplant") rows.sort((a, b) => (a.due_on || "").localeCompare(b.due_on || ""));
    return rows;
  }, [tasks, list, me]);
  // A list other than "Erledigt" keeps its finished tasks below, on request.
  const finished = list === "erledigt" ? [] : tasks.filter((x) => x.status === "erledigt" && belongs(list, { ...x, status: "offen" }, me));
  const selected = tasks.find((x) => x.id === selectedId);
  const defaults = defaultsFor(list);
  const [title, setTitle] = useState("");
  useEffect(() => { document.getElementById(`task-${selectedId}`)?.scrollIntoView?.({ block: "nearest" }); }, [selectedId]);

  const nav = (key, label, icon, n) => (
    <a key={key} href={href(key)} className="tm-list" aria-current={list === key ? "page" : undefined}>
      <span className="tm-list__icon" aria-hidden="true">{icon}</span><span>{label}</span>
      {n > 0 && <span className="tm-list__n">{n}</span>}
    </a>
  );
  const clientsWithTasks = d.clients.filter((c) => tasks.some((x) => x.status !== "erledigt" && x.client?.id === c.id));

  return (
    <section className={`tm${selected ? " tm--detail" : ""}`}>
      <nav className="tm-lists" aria-label={t("Listen")}>
        {SMART.map(([key, label, icon]) => nav(key, t(label), icon, key === "erledigt" ? 0 : count(key)))}
        <p className="tm-lists__h">{t("Personen")}</p>
        {me && nav("mir", t("Mir zugewiesen"), "@", count("mir"))}
        {d.team.map((p) => nav(`person:${p.key}`, p.name, "@", count(`person:${p.key}`)))}
        <p className="tm-lists__h">{t("Kunden")}</p>
        {nav("intern", t("Intern"), "◇", count("intern"))}
        {clientsWithTasks.map((c) => nav(`kunde:${c.id}`, c.name, "◆", count(`kunde:${c.id}`)))}
      </nav>

      <div className="tm-main">
        <header className="tm-head">
          <p className="tm-eyebrow">{t("Aufgaben")}</p>
          <h1>{listTitle(list, d)}</h1>
          {list === "heute" && <p className="tm-sub">{new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })}</p>}
        </header>
        <Notice>{d.error}</Notice>
        {list !== "erledigt" && (
          <form method="post" action="/aufgaben" className="tm-add">
            <span className="tm-circle tm-circle--add" aria-hidden="true">+</span>
            <input name="title" required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder={t("Aufgabe hinzufügen")} aria-label={t("Aufgabe hinzufügen")} />
            <Hidden values={{ ...defaults, redirect_to: href(list) }} />
            {title && <button type="submit" className="btn btn--go">{t("Hinzufügen")}</button>}
          </form>
        )}
        <ul className="tm-rows">
          {shown.map((x) => <Row key={x.id} task={x} d={d} list={list} selected={x.id === selectedId} />)}
        </ul>
        {!shown.length && <p className="tm-empty">{t(list === "erledigt" ? "Noch nichts erledigt." : "Nichts offen. Gut so.")}</p>}
        {finished.length > 0 && (
          <>
            <button type="button" className="btn btn--quiet tm-done-toggle" aria-expanded={showDone} onClick={() => setShowDone(!showDone)}>
              {t(showDone ? "Erledigte ausblenden" : "Erledigte anzeigen")} · {finished.length}
            </button>
            {showDone && <ul className="tm-rows">{finished.map((x) => <Row key={x.id} task={x} d={d} list={list} selected={x.id === selectedId} />)}</ul>}
          </>
        )}
        {(list === "alle" || list === "heute") && <Decisions items={d.decisions} />}
      </div>

      {selected && <Details key={selected.id} task={selected} d={d} list={list} />}
    </section>
  );
}
