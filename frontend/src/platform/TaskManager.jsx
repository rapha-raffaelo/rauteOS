import React, { useEffect, useMemo, useState } from "react";
import { Notice, t } from "./shared.jsx";

// Shared tasks in a status board or list, with inline creation and a detail drawer.
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
  if (list === "kunden") return !!x.client;
  if (list === "mir") return !!me && x.assignees.includes(me);
  if (list.startsWith("person:")) return x.assignees.includes(list.slice(7));
  if (list.startsWith("kunde:")) return String(x.client?.id) === list.slice(6);
  return true; // alle
}

function listTitle(list, d) {
  const smart = SMART.find(([key]) => key === list);
  if (smart) return t(smart[1]);
  if (list === "intern") return t("Intern");
  if (list === "kunden") return t("Kunde");
  if (list === "mir") return t("Mir zugewiesen");
  if (list.startsWith("person:")) return d.team.find((p) => p.key === list.slice(7))?.name || list;
  if (list.startsWith("kunde:")) return d.clients.find((c) => String(c.id) === list.slice(6))?.name || t("Kunde");
  return t("Alle");
}

// What a task added to this list should start with, so it lands where it was typed.
function defaultsFor(list, me) {
  const today = isoToday();
  if (list === "mir" && me) return { assignees: me };
  if (list === "geplant" || list === "heute") return { due_on: today };
  if (list === "wichtig") return { priority: "hoch" };
  if (list.startsWith("person:")) return { assignees: list.slice(7) };
  if (list.startsWith("kunde:")) return { client_id: list.slice(6) };
  return {};
}

const href = (list, task) => {
  const q = new URLSearchParams();
  if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("ansicht") === "liste") q.set("ansicht", "liste");
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

function AreaFields({ clients, clientId, customer = false }) {
  const [area, setArea] = useState(clientId || customer ? "kunde" : "intern");
  return <>
    <label className="tm-field"><span>Bereich</span>
      <select aria-label="Bereich" value={area} onChange={e => setArea(e.target.value)}>
        <option value="intern">Intern</option><option value="kunde">Kunde</option>
      </select>
    </label>
    {area === "kunde" ? <label className="tm-field"><span>Kunde auswählen</span>
      <select aria-label="Kunde auswählen" name="client_id" defaultValue={clientId || ""} required>
        <option value="">Bitte auswählen</option>
        {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
    </label> : <input type="hidden" name="client_id" value="" />}
  </>;
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
        <label className="tm-field"><span>{t("Status")}</span><select aria-label="Status" name="status" defaultValue={task.status}>{STATES.map(([key, label]) => <option key={key} value={key}>{t(label)}</option>)}</select></label>
        <input type="hidden" name="owner" value={task.owner || ""} />
        <label className="tm-field"><span>{t("Aufgabe")}</span>
          <input type="text" name="title" defaultValue={task.title} required maxLength={200} /></label>
        <fieldset className="tm-field tm-people">
          <legend>{t("Zuständig")}</legend>
          {d.team.map((p) => (
            <label key={p.key} className="tm-tag">
              <input type="checkbox" name="assignees" value={p.key} defaultChecked={task.assignees.includes(p.key)} />
              <span>@{p.name}</span>
            </label>
          ))}
        </fieldset>
        <AreaFields clients={d.clients} clientId={task.client?.id} />
        <small>{t("Einem Kunden zugeordnet, erscheint die Aufgabe auch auf seinem Dashboard.")}</small>
        <label className="tm-field"><span>{t("Fällig am")}</span>
          <input type="date" name="due_on" defaultValue={task.due_on || ""} /></label>
        <label className="tm-field"><span>{t("Priorität")}</span>
          <select aria-label="Priorität" name="priority" defaultValue={task.priority}>
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

const STATES = [["offen", "Offen"], ["in_arbeit", "In Bearbeitung"], ["review", "Review"], ["erledigt", "Erledigt"]];

function CreateTask({ d, list, status = "offen", onClose }) {
  const defaults = defaultsFor(list, d.me);
  return <form method="post" action="/aufgaben" className="tm-add tm-add--inline">
    <div className="tm-add-title"><strong>Neue Aufgabe</strong><button type="button" className="tm-close" aria-label="Neue Aufgabe schließen" onClick={onClose}>×</button></div>
    <input type="text" name="title" required maxLength={200} autoFocus placeholder="Name der Aufgabe" aria-label="Aufgabe hinzufügen" />
    <Hidden values={{ status, redirect_to: href(list) }} />
    <div className="tm-add-options">
      <AreaFields clients={d.clients} clientId={defaults.client_id} customer={list === "kunden"} />
      <fieldset className="tm-field tm-people"><legend>Zuständig</legend>{d.team.map(person =>
        <label className="tm-tag" key={person.key}><input type="checkbox" name="assignees" value={person.key} defaultChecked={defaults.assignees === person.key} /><span>@{person.name}</span></label>)}</fieldset>
      <label className="tm-field"><span>Fällig am</span><input type="date" name="due_on" defaultValue={defaults.due_on || ""} /></label>
      <label className="tm-field"><span>Priorität</span><select aria-label="Priorität" name="priority" defaultValue={defaults.priority || "mittel"}>{d.priorities.map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    </div>
    <button type="submit" className="btn btn--go">Aufgabe erstellen</button>
  </form>;
}

function Board({ tasks, d, list, selectedId, createStatus, onCreate }) {
  const [dragged, setDragged] = useState(null);
  const [target, setTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function move(taskId, status) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/aufgaben/${taskId}`, {
        method: "POST", headers: { Accept: "application/json" },
        body: new URLSearchParams({status, redirect_to: href(list, selectedId)}),
      });
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (result.status !== status) throw new Error();
      window.location.assign(href(list, selectedId));
    } catch {
      setError("Die Aufgabe konnte nicht verschoben werden. Bitte erneut versuchen.");
      setBusy(false);
    }
  }
  return <>
    {error && <p role="alert">{error}</p>}
    <div className="tm-board" aria-busy={busy}>
      {STATES.map(([status,label]) => <section key={status}
        className={`tm-column tm-column--${status}${target === status ? " tm-column--drop" : ""}`}
        aria-label={label}
        onDragOver={event => { if (dragged && !busy) { event.preventDefault(); setTarget(status); } }}
        onDrop={event => { event.preventDefault(); setTarget(null); if (dragged && dragged.status !== status) move(dragged.id,status); setDragged(null); }}>
        <h2><span className="tm-status-dot" aria-hidden="true" />{label}<span className="tm-column-count">{tasks.filter(task => task.status === status).length}</span></h2>
        <ul className="tm-rows">{tasks.filter(task => task.status === status).map(task =>
          <li key={task.id} id={`task-${task.id}`} className={`tm-board-card${task.id === selectedId ? " tm-board-card--selected" : ""}`}
            draggable={!busy} onDragStart={event => { setDragged(task); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(task.id)); }}
            onDragEnd={() => { setDragged(null); setTarget(null); }}>
            <div className="tm-card-title"><Check task={task} back={href(list)} /><a href={href(list,task.id)}>{task.title}</a><Star task={task} back={href(list)} /></div>
            <div className="tm-card-meta">
              {task.assignees.map(key => <span className="tm-avatar" title={d.team.find(p => p.key === key)?.name || key} key={key}>{key === "raphael" ? "RM" : key === "lucas" ? "L" : key.slice(0,2).toUpperCase()}</span>)}
              {task.due_on && <span className={task.status !== "erledigt" && task.due_on < isoToday() ? "tm-overdue" : ""}>▦ {shortDay(task.due_on)}</span>}
              <span className={`tm-priority tm-priority--${task.priority}`}>⚑ {d.priorities.find(([key]) => key === task.priority)?.[1]}</span>
            </div>
            <div className="tm-card-footer"><span>{task.client?.name || "Intern"}</span>
              <details><summary aria-label={`Status ändern: ${task.title}`}>•••</summary>
                <form method="post" action={`/aufgaben/${task.id}`} className="tm-move">
                  <Hidden values={{redirect_to: href(list)}} />
                  <select name="status" aria-label={`Status: ${task.title}`} defaultValue={task.status}>{STATES.map(([key,name]) => <option key={key} value={key}>{name}</option>)}</select>
                  <button className="btn btn--quiet" type="submit">Ändern</button>
                </form>
              </details>
            </div>
          </li>)}</ul>
        {createStatus === status ? <CreateTask key={status} d={d} list={list} status={status} onClose={() => onCreate(null)} /> :
          <button type="button" className="tm-column-add" onClick={() => onCreate(status)}>+ Aufgabe hinzufügen<span className="sr-only">: {label}</span></button>}
      </section>)}
    </div>
  </>;
}

export function TasksPage({ data: d }) {
  const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
  const list = params.get("liste") || "alle";
  const selectedId = Number(params.get("aufgabe")) || null;
  const [showDone, setShowDone] = useState(false);
  const board = params.get("ansicht") !== "liste";
  const [createStatus, setCreateStatus] = useState(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("datum");
  const matches = x => [x.title, x.note, x.client?.name, ...x.assignees].join(" ").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  const viewLink = value => { const q = new URLSearchParams(params); q.set("ansicht", value); return "/aufgaben?" + q; };
  const tasks = d.tasks;
  const me = d.me;
  const count = (key) => tasks.filter((x) => belongs(key, x, me)).length;
  const shown = useMemo(() => {
    const rows = tasks.filter((x) => belongs(list, x, me) && matches(x));
    if (sort === "datum") rows.sort((a, b) => (a.due_on || "9999").localeCompare(b.due_on || "9999"));
    if (sort === "titel") rows.sort((a, b) => a.title.localeCompare(b.title));
    if (sort === "prioritaet") rows.sort((a, b) => ["hoch", "mittel", "niedrig"].indexOf(a.priority) - ["hoch", "mittel", "niedrig"].indexOf(b.priority));
    return rows;
  }, [tasks, list, me, query, sort]);
  // A list other than "Erledigt" keeps its finished tasks below, on request.
  const finished = list === "erledigt" ? [] : tasks.filter((x) => x.status === "erledigt" && matches(x) && belongs(list, { ...x, status: "offen" }, me));
  const selected = tasks.find((x) => x.id === selectedId);
  useEffect(() => { document.getElementById(`task-${selectedId}`)?.scrollIntoView?.({ block: "nearest" }); }, [selectedId]);


  return (
    <section className={`tm${selected ? " tm--detail" : ""}`}>
      <div className="tm-main">
        <header className="tm-head">
          <p className="tm-eyebrow">Arbeitsplatz</p>
          <h1>{list === "alle" ? "Aufgaben" : listTitle(list, d)}</h1>
          <button className="btn btn--go" type="button" onClick={() => setCreateStatus("offen")}>+ Neue Aufgabe</button>
          {list === "heute" && <p className="tm-sub">{new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })}</p>}
        </header>
        <div className="tm-toolbar">
          <nav aria-label="Ansicht"><a className="btn btn--quiet" aria-current={!board ? "page" : undefined} href={viewLink("liste")}>Liste</a><a className="btn btn--quiet" aria-current={board ? "page" : undefined} href={viewLink("board")}>Board</a></nav>
          <select aria-label="Aufgaben filtern" value={list} onChange={event => window.location.assign(href(event.target.value))}>
            <optgroup label="Ansicht">{SMART.map(([key,label]) => <option key={key} value={key}>{label} ({count(key)})</option>)}</optgroup>
            <optgroup label="Personen">{d.team.map(person => <option key={person.key} value={`person:${person.key}`}>{person.name}</option>)}</optgroup>
            <optgroup label="Bereich"><option value="intern">Intern</option><option value="kunden">Kunde</option></optgroup>
            <optgroup label="Kunden">{d.clients.map(client => <option key={client.id} value={`kunde:${client.id}`}>{client.name}</option>)}</optgroup>
          </select>
          <input type="search" aria-label="Aufgaben suchen" placeholder="Aufgaben suchen" value={query} onChange={e => setQuery(e.target.value)} />
          <select aria-label="Sortieren" value={sort} onChange={e => setSort(e.target.value)}><option value="datum">Fälligkeit</option><option value="prioritaet">Priorität</option><option value="titel">Titel</option></select>
        </div>
        <Notice>{d.error}</Notice>
        {!board && createStatus && <CreateTask d={d} list={list} status={createStatus} onClose={() => setCreateStatus(null)} />}
        {board ? <Board tasks={[...shown, ...finished]} d={d} list={list} selectedId={selectedId} createStatus={createStatus} onCreate={setCreateStatus} /> : <ul className="tm-rows">
          {shown.map((x) => <Row key={x.id} task={x} d={d} list={list} selected={x.id === selectedId} />)}
        </ul>}
        {!board && !shown.length && <p className="tm-empty">{t(list === "erledigt" ? "Noch keine erledigten Aufgaben" : "Keine offenen Aufgaben")}</p>}
        {!board && finished.length > 0 && (
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
