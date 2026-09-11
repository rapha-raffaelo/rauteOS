import React, {useEffect, useState} from 'react';
import {journalistRequest as request} from '../journalists-api.js';

const listLabels = {topics:'Themen', specialties:'Spezialisierungen', story_types:'Story-Typen', companies:'Beobachtete Unternehmen', source_aliases:'Weitere Quellenbezeichnungen'};
const contactLabels = {name:'Name', outlet:'Medium', first_name:'Vorname', last_name:'Nachname', email:'E-Mail', phone:'Telefon', beat:'Ressort', position:'Position', notes:'Notizen'};
const statusLabels = {running:'Recherche läuft', complete:'Recherche abgeschlossen', archive_only:'Nur Archiv verfügbar', failed:'Recherche fehlgeschlagen'};
const providerLabels = {ok:'Abgerufen', failed:'Abruf fehlgeschlagen', not_configured:'Nicht konfiguriert'};
const date = value => value ? new Date(value).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'}) : 'Nicht hinterlegt';
function ErrorMessage({error}) { return error ? <p className="twin-error" role="alert">{error}</p> : null; }
function ArticleList({articles}) {
  return articles.length ? <ul className="journalist-articles">{articles.map(a => <li key={a.url}>
    <a href={a.url} target="_blank" rel="noreferrer">{a.title}</a>
    <small>{a.author} · {a.source} · {date(a.published_at)} · {a.provider}</small>
    {a.snippet && <p>{a.snippet}</p>}
  </li>)}</ul> : <p>Keine zugeordneten Artikel in den verfügbaren Quellen. Das ist kein Nachweis fehlender Veröffentlichungen.</p>;
}
function Relationship({value}) {
  return <div><p>Letzter Kontakt: {date(value.last_interaction_at)}</p>
    <p>{value.tally.anschreiben} Anschreiben · {value.tally.antworten} Antworten · {value.tally.veroeffentlicht} Veröffentlichungen</p>
    <details><summary>Kontakthistorie ({value.timeline.length})</summary>
      {value.timeline.length ? <ul>{value.timeline.map((event,i) => <li key={i}><a href={event.href}>{event.subject}</a> · {event.mandate} · {event.kind} · {date(event.at)}</li>)}</ul> : <p>Keine freigegebenen Anschreiben hinterlegt.</p>}
    </details>{value.capped && <small>Die Historie ist auf die neuesten Einträge begrenzt.</small>}
  </div>;
}
function ProfileEditor({data, onSaved}) {
  const [contact, setContact] = useState(() => Object.fromEntries(Object.keys(contactLabels).map(k => [k,data.contact[k] || ''])));
  const [profile, setProfile] = useState({...data.profile});
  const [lists, setLists] = useState(Object.fromEntries(Object.keys(listLabels).map(k => [k,data.profile[k].join('\n')])));
  const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const {revision, ...values} = profile;
      const saved = await request(`journalists/${data.contact.id}`, {method:'PUT',body:JSON.stringify({contact,
        profile:{...values,...Object.fromEntries(Object.keys(lists).map(k => [k,lists[k].split('\n').map(v=>v.trim()).filter(Boolean)]))},
        revision,contact_updated_at:data.contact.updated_at})});
      onSaved(saved);
    } catch (e) {setError(e.message);} finally {setBusy(false);}
  }
  return <><section className="twin-field journalist-summary"><p className="twin-eyebrow">Journalistenprofil</p><h2>{data.contact.name}</h2><p>{data.contact.outlet} · {data.contact.beat || 'Ressort offen'}</p><p>{data.profile.topics.join(' · ') || 'Noch keine Themen hinterlegt.'}</p><p>{data.profile.preferences || 'Ansprache noch nicht hinterlegt.'}</p><strong>{data.profile.relationship_status}</strong></section><details className="profile-edit"><summary>Profil bearbeiten</summary><form onSubmit={save} className="twin-field"><h2>{data.contact.name}</h2>
    <p>Kontaktangaben und Profilwissen werden von Ihnen gepflegt. E-Mail-Adressen werden nicht geraten.</p>
    <ErrorMessage error={error}/><div className="twin-form-grid">{Object.entries(contactLabels).map(([key,label]) => <label key={key}>{label}
      <input aria-label={label} required={key==='name'} value={contact[key]} onChange={e=>setContact({...contact,[key]:e.target.value})}/>
    </label>)}</div>
    <div className="twin-form-grid">{Object.entries(listLabels).map(([key,label]) => <label key={key}>{label} <small>Ein Eintrag pro Zeile</small>
      <textarea aria-label={label} value={lists[key]} onChange={e=>setLists({...lists,[key]:e.target.value})}/>
    </label>)}</div>
    <label>Bevorzugte Ansprache und Formate<textarea aria-label="Bevorzugte Ansprache und Formate" value={profile.preferences} onChange={e=>setProfile({...profile,preferences:e.target.value})}/></label>
    <label>Beziehungsstatus<select aria-label="Beziehungsstatus" value={profile.relationship_status} onChange={e=>setProfile({...profile,relationship_status:e.target.value})}>
      {data.relationship_options.map(value=><option key={value}>{value}</option>)}</select></label>
    <label>Zusätzlicher letzter Kontakt (Datum)<input aria-label="Zusätzlicher letzter Kontakt" type="date" value={profile.last_interaction_at?.slice(0,10) || ''}
      onChange={e=>setProfile({...profile,last_interaction_at:e.target.value ? `${e.target.value}T12:00:00Z` : null})}/></label>
    <button className="btn btn--go" disabled={busy}>{busy ? 'Wird gespeichert…' : 'Profil speichern'}</button>
  </form></details><section className="twin-field"><h2>Beziehung</h2><Relationship value={data.relationship}/></section>
    <section className="twin-field"><h2>Artikelhistorie</h2><p>Zuordnung über Name und Medium bzw. ausdrücklich hinterlegte Quellenbezeichnungen.</p>
      {data.corpus_capped && <p>Es werden die neuesten 2.000 Artikel je Datenbestand berücksichtigt.</p>}<ArticleList articles={data.articles}/></section></>;
}
export function ResearchPanel({clientId, contextKind, contextId, onContact}) {
  const path = `clients/${clientId}/journalist-research`;
  const [context,setContext] = useState(null); const [research,setResearch] = useState(null);
  const [query,setQuery] = useState(''); const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  const [loaded,setLoaded] = useState(false);
  useEffect(()=>{
    let active=true;
    request(`${path}?context_kind=${encodeURIComponent(contextKind)}&context_id=${contextId}`).then(data=>{
      if(active){setContext(data.context);setResearch(data.research);setQuery(data.research?.query || '');setLoaded(true);}
    }).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[path,contextKind,contextId]);
  const running = research?.status === 'running' && Date.now()-new Date(research.started_at).getTime()<600000;
  useEffect(()=>{
    if(!running)return;
    let active=true;
    const timer=setInterval(()=>request(`${path}?context_kind=${encodeURIComponent(contextKind)}&context_id=${contextId}`)
      .then(data=>{if(active){setResearch(data.research);setError('');}}).catch(e=>{if(active)setError(e.message);}),2500);
    return ()=>{active=false;clearInterval(timer);};
  },[path,contextKind,contextId,running]);
  async function start(event) {
    event.preventDefault();setBusy(true);setError('');
    try {setResearch(await request(path,{method:'POST',body:JSON.stringify({context_kind:contextKind,context_id:contextId,query})}));}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="twin-field"><p className="twin-eyebrow">Recherche für diese Gelegenheit</p><h2>{context?.title || 'Journalisten recherchieren'}</h2>
    <p>Frische Artikel aus konfigurierten Quellen und Archivbelege der letzten sechs Wochen. Jeder Vorschlag nennt seine Belege; die Recherche ist nicht vollständig.</p>
    <ErrorMessage error={error}/><form onSubmit={start}><label>Suchthema<input aria-label="Suchthema" required minLength={3} maxLength={300} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Zum Beispiel: BioLNG Schwerlastverkehr"/></label>
      <button className="btn btn--go" disabled={!loaded || busy || running}>{running ? 'Recherche läuft…' : 'Frisch recherchieren'}</button></form>
    {research && <><p role="status"><strong>{statusLabels[research.status]}</strong> · {date(research.finished_at || research.started_at)}</p>
      <p>Suchthema dieses Laufs: {research.query}</p><p>{research.note}</p>
      <ul>{Object.entries(research.providers).map(([name,value])=><li key={name}>{name}: {providerLabels[value.status]} · {value.articles} Artikel</li>)}</ul>
      {!running && research.results.length===0 && <p>Keine belegten Vorschläge aus dieser Recherche.</p>}
      <div className="research-table-wrap"><table className="research-table"><caption>Belegte Journalisten-Vorschläge</caption><thead><tr><th>Journalist / Medium</th><th>Relevanz für diese Gelegenheit</th><th>Aktuelle Belege & Beziehung</th><th>Profil</th></tr></thead><tbody>{research.results.map(person=><tr key={`${person.name}-${person.outlet}`}><td><strong>{person.name}</strong><small>{person.outlet}</small></td><td><strong>{person.fit}</strong><p>{person.reason}</p><details><summary>Ansprache</summary><p>{person.approach}</p></details></td><td><details><summary>Artikelbelege ({person.article_count})</summary><ArticleList articles={person.evidence}/></details>{person.relationship&&<Relationship value={person.relationship}/>}</td><td>{person.contact_id?<button className="btn" onClick={()=>onContact(person.contact_id)}>Profil öffnen</button>:<button className="btn" onClick={()=>onContact(null,person)}>Kontakt hinterlegen</button>}</td></tr>)}</tbody></table></div></>}
  </section>;
}
export function JournalistsPage({params = new URLSearchParams(window.location.search)}) {
  const [contacts,setContacts]=useState([]);const [selected,setSelected]=useState(Number(params.get('contact')) || null);
  const [data,setData]=useState(null);const [q,setQ]=useState('');const [error,setError]=useState('');
  const [newContact,setNewContact]=useState(null);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const clientId=Number(params.get('client')), contextId=Number(params.get('context')),contextKind=params.get('kind');
  useEffect(()=>{let active=true;request('journalists').then(v=>{if(active)setContacts(v.contacts);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
  useEffect(()=>{let active=true;setData(null);setError('');if(selected)request(`journalists/${selected}`).then(v=>{if(active)setData(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[selected]);
  function openContact(id,person) {setSelected(id);setNotice('');setNewContact(id ? null : {name:person.name,outlet:person.outlet});}
  async function create(event) {
    event.preventDefault();setBusy(true);setError('');
    try {const value=await request('journalists',{method:'POST',body:JSON.stringify(newContact)});setContacts(v=>[...v,value.contact]);setNewContact(null);setSelected(value.contact.id);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function saved(value) {setData(value);setContacts(v=>v.map(c=>c.id===value.contact.id ? value.contact:c));setNotice('Profil gespeichert.');}
  return <div className="twin-page journalists-page"><p className="twin-eyebrow">Medienarbeit</p><h1>Journalisten</h1>
    <p>Profilwissen, Artikelbelege und Beziehungshistorie an einem Ort.</p>
    {clientId>0 && contextId>0 && ['detected','developed'].includes(contextKind) && <ResearchPanel clientId={clientId} contextId={contextId} contextKind={contextKind} onContact={openContact}/>}
    <ErrorMessage error={error}/>{notice && <p role="status">{notice}</p>}
    <div className="journalist-layout"><aside className="twin-field"><label>Kontakte suchen<input aria-label="Kontakte suchen" value={q} onChange={e=>setQ(e.target.value)}/></label>
      <button className="btn" onClick={()=>{setNewContact({name:'',outlet:''});setSelected(null);setNotice('');}}>Neuer Kontakt</button>
      <ul className="journalist-roster">{contacts.filter(c=>`${c.name} ${c.outlet} ${c.beat}`.toLocaleLowerCase().includes(q.toLocaleLowerCase())).map(c=><li key={c.id}>
        <button aria-pressed={selected===c.id} onClick={()=>openContact(c.id)}>{c.name}<small>{c.outlet || 'Medium nicht hinterlegt'}</small></button></li>)}</ul>
      {contacts.length===0 && <p>Noch keine Kontakte hinterlegt.</p>}</aside>
      <div>{newContact && <form className="twin-field" onSubmit={create}><h2>Kontakt hinterlegen</h2>
        <label>Name<input aria-label="Name" required autoFocus value={newContact.name} onChange={e=>setNewContact({...newContact,name:e.target.value})}/></label>
        <label>Medium<input aria-label="Medium" value={newContact.outlet} onChange={e=>setNewContact({...newContact,outlet:e.target.value})}/></label>
        <button className="btn btn--go" disabled={busy}>Kontakt speichern</button></form>}
        {selected && !data && !error && <p role="status">Profil wird geladen…</p>}
        {data && <ProfileEditor key={`${data.contact.id}-${data.contact.updated_at}-${data.profile.revision}`} data={data} onSaved={saved}/>}
        {!selected && !newContact && <section className="twin-field"><h2>Kontakt auswählen</h2><p>Öffnen Sie ein Profil oder hinterlegen Sie einen neuen Kontakt.</p></section>}
      </div></div>
  </div>;
}
