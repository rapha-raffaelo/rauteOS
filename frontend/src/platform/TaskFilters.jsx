import React, { useEffect, useRef, useState } from "react";

const dateValue = value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return "";
  const parsed = new Date(value+"T12:00:00");
  return Number.isFinite(parsed.getTime()) && iso(parsed) === value ? value : "";
};
const iso = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
const pretty = value => value ? new Date(value + "T12:00:00").toLocaleDateString("de-DE") : "";
export const EMPTY_FILTERS = {view:"alle", person:"", area:"", client:"", from:"", to:"", priority:"", favorite:""};

export function readTaskFilters(params) {
  const old = params.get("liste") || "alle";
  const filters = {
    view: ["heute","geplant","erledigt","archiv"].includes(old) ? old : "alle",
    priority: params.get("prioritaet") || (old === "wichtig" ? "hoch" : ""),
    favorite: params.get("favoriten") === "1" ? "1" : "",
    person: params.get("person") || (old.startsWith("person:") ? old.slice(7) : ""),
    area: params.get("bereich") || (old === "intern" ? "intern" : old === "kunden" || old.startsWith("kunde:") ? "kunde" : ""),
    client: params.get("kunde") || (old.startsWith("kunde:") ? old.slice(6) : ""),
    from: dateValue(params.get("von")), to: dateValue(params.get("bis")),
  };
  if (filters.from && !filters.to) filters.to = filters.from;
  if (filters.to && !filters.from) filters.from = filters.to;
  if (filters.from > filters.to) [filters.from, filters.to] = [filters.to, filters.from];
  if (filters.client) filters.area = "kunde";
  return filters;
}

export function setFilterParams(params, filters) {
  for (const [key,value] of Object.entries({
    liste: filters.view === "alle" ? "" : filters.view, person:filters.person,
    bereich:filters.area, kunde:filters.client, prioritaet:filters.priority, favoriten:filters.favorite, von:filters.from, bis:filters.to,
  })) { if (value) params.set(key,value); else params.delete(key); }
  return params;
}

export function matchesTaskFilters(task, filters) {
  return (!filters.priority || task.priority === filters.priority)
    && (!filters.favorite || task.favorite)
    && (!filters.person || task.assignees.includes(filters.person))
    && (!filters.area || (filters.area === "intern" ? !task.client : !!task.client))
    && (!filters.client || String(task.client?.id) === filters.client)
    && (!filters.from || (!!task.due_on && task.due_on >= filters.from && task.due_on <= filters.to));
}

function DateCalendar({ filters, onChange }) {
  const [open,setOpen] = useState(false);
  const [mode,setMode] = useState("day");
  const [from,setFrom] = useState("");
  const [to,setTo] = useState("");
  const [month,setMonth] = useState(() => new Date());
  const root = useRef(null), trigger = useRef(null);
  useEffect(() => {
    if (!open) return;
    const outside = event => { if (!root.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown",outside);
    document.addEventListener("keydown",escape);
    return () => { document.removeEventListener("pointerdown",outside); document.removeEventListener("keydown",escape); };
  },[open]);
  function toggle() {
    if (!open) {
      setFrom(filters.from); setTo(filters.to);
      setMode(filters.from && filters.from !== filters.to ? "range" : "day");
      setMonth(filters.from ? new Date(filters.from+"T12:00:00") : new Date());
    }
    setOpen(!open);
  }
  function pick(value) {
    if (mode === "day") { setFrom(value); setTo(value); }
    else if (!from || to) { setFrom(value); setTo(""); }
    else { setFrom(value < from ? value : from); setTo(value < from ? from : value); }
  }
  function apply(start,end) {
    onChange({from:start,to:end, ...(["heute","geplant"].includes(filters.view) ? {view:"alle"} : {})});
    setOpen(false); trigger.current?.focus();
  }
  const first = new Date(month.getFullYear(),month.getMonth(),1);
  const offset = (first.getDay()+6)%7;
  const days = new Date(month.getFullYear(),month.getMonth()+1,0).getDate();
  return <div className="tm-date-filter" ref={root}>
    <span className="tm-filter-label">Fälligkeit</span>
    <button ref={trigger} type="button" className="tm-date-trigger" aria-expanded={open} aria-haspopup="dialog" onClick={toggle}>
      ▦ {filters.from ? pretty(filters.from)+(filters.to !== filters.from ? " – "+pretty(filters.to) : "") : "Datum / Zeitraum"}
    </button>
    {open && <div className="tm-calendar" role="dialog" aria-label="Fälligkeit auswählen">
      <div className="tm-calendar-modes">
        <button type="button" aria-pressed={mode === "day"} onClick={() => {setMode("day");setTo(from);}}>Einzelner Tag</button>
        <button type="button" aria-pressed={mode === "range"} onClick={() => {setMode("range");setFrom("");setTo("");}}>Zeitraum</button>
      </div>
      <div className="tm-calendar-inputs">
        <label>{mode === "day" ? "Datum" : "Von"}<input aria-label={mode === "day" ? "Datum" : "Von"} type="date" value={from} onChange={event => {
          const value=event.target.value; setFrom(value);
          if(mode === "day") setTo(value);
          if(value) setMonth(new Date(value+"T12:00:00"));
        }} /></label>
        {mode === "range" && <label>Bis<input aria-label="Bis" type="date" value={to} min={from} onChange={event=>setTo(event.target.value)} /></label>}
      </div>
      <div className="tm-calendar-month">
        <button type="button" aria-label="Vorheriger Monat" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}>‹</button>
        <strong aria-live="polite">{month.toLocaleDateString("de-DE",{month:"long",year:"numeric"})}</strong>
        <button type="button" aria-label="Nächster Monat" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}>›</button>
      </div>
      <div className="tm-calendar-grid">
        {["Mo","Di","Mi","Do","Fr","Sa","So"].map(day=><span key={day}>{day}</span>)}
        {Array.from({length:offset},(_,index)=><span key={"empty"+index} />)}
        {Array.from({length:days},(_,index)=>{
          const value=iso(new Date(month.getFullYear(),month.getMonth(),index+1));
          const selected=value===from || value===to;
          return <button type="button" key={value} aria-label={value} aria-pressed={selected}
            aria-current={value===iso(new Date()) ? "date" : undefined}
            className={from && to && value>from && value<to ? "tm-calendar-between" : ""}
            onClick={()=>pick(value)}>{index+1}</button>;
        })}
      </div>
      {mode === "range" && <small>Start- und Endtag auswählen</small>}
      <div className="tm-calendar-actions">
        <button type="button" className="btn btn--quiet" onClick={()=>apply("","")}>Alle Termine</button>
        <button type="button" className="btn btn--go" disabled={!from || !to || from>to} onClick={()=>apply(from,to)}>Anwenden</button>
      </div>
    </div>}
  </div>;
}

export function TaskFilters({ filters, onChange, team, clients }) {
  const active=Object.entries(filters).some(([key,value])=>key==="view" ? value!=="alle" : !!value);
  return <div className="tm-filters" aria-label="Aufgabenfilter">
    <label><span>Ansicht</span><select aria-label="Ansicht filtern" value={filters.view} onChange={e=>onChange({view:e.target.value,...(e.target.value==="heute" ? {from:"",to:""} : {})})}>
      <option value="alle">Alle Aufgaben</option><option value="heute">Heute & überfällig</option><option value="geplant">Mit Fälligkeit</option><option value="erledigt">Erledigt</option><option value="archiv">Archiv</option>
    </select></label>
    <label><span>Person</span><select aria-label="Person filtern" value={filters.person} onChange={e=>onChange({person:e.target.value})}>
      <option value="">Alle Personen</option>{team.map(person=><option key={person.key} value={person.key}>{person.name}</option>)}
    </select></label>
    <label><span>Bereich</span><select aria-label="Bereich filtern" value={filters.area} onChange={e=>onChange({area:e.target.value,...(e.target.value!=="kunde" ? {client:""} : {})})}>
      <option value="">Alle Bereiche</option><option value="intern">Intern</option><option value="kunde">Kunde</option>
    </select></label>
    <label><span>Kunde</span><select aria-label="Kunde filtern" value={filters.client} disabled={filters.area==="intern"} onChange={e=>onChange({client:e.target.value,...(e.target.value ? {area:"kunde"} : {})})}>
      <option value="">Alle Kunden</option>{clients.map(client=><option key={client.id} value={client.id}>{client.name}</option>)}
    </select></label>
    <label><span>Priorität</span><select aria-label="Priorität filtern" value={filters.priority || ""} onChange={e=>onChange({priority:e.target.value})}>
      <option value="">Alle Prioritäten</option><option value="niedrig">Niedrig</option><option value="mittel">Mittel</option><option value="hoch">Hoch</option><option value="urgent">Urgent</option>
    </select></label>
    <label><span>Favoriten</span><select aria-label="Favoriten filtern" value={filters.favorite || ""} onChange={e=>onChange({favorite:e.target.value})}>
      <option value="">Alle Aufgaben</option><option value="1">★ Nur Favoriten</option>
    </select></label>
    <DateCalendar filters={filters} onChange={onChange} />
    {active && <button type="button" className="btn btn--quiet" onClick={()=>onChange({...EMPTY_FILTERS})}>Filter zurücksetzen</button>}
  </div>;
}
