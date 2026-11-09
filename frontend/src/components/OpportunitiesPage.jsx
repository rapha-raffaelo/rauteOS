import React,{useEffect,useRef,useState} from 'react';
import {PageHeading,EmptyState} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';
import {ResearchPanel} from './JournalistsPage.jsx';
import {ActivationPanel,PreparedRelease} from './ActivationPanel.jsx';
import './communication.css';
const date=value=>value ? new Date(value).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'}) : 'Nicht festgelegt';
const statusLabels={draft:'Entwurf',active:'Aktiviert',closed:'Abgeschlossen'};
const originLabels={anlass:'Anlass',pitch:'Themen-Pitch',plan:'Aus dem Plan'};
const eventLabels={idea_developed:'Idee entwickelt',choices_saved:'Auswahl gespeichert',activated:'Aktiviert',text_created:'Text erstellt',text_checked:'Aussagen geprüft',text_edited:'Text bearbeitet'};
const letterStates={entwurf:'Entwurf',raus:'Verschickt',antwort:'Antwort erhalten',absage:'Absage',veroeffentlicht:'Veröffentlicht'};
const actionLabels={kundenmail:'Kundenmail',pitch:'Journalistenpitch',statement:'Statement',pressemitteilung:'Pressemitteilung',qa:'Q&A',gastbeitrag:'Gastbeitrag',interviewangebot:'Interviewangebot',linkedin:'LinkedIn-Post',briefing:'Briefing',custom:'Eigene Aktion'};
const timingPlaceholders=new Set(['zeitfenster noch zu prüfen','kein bestätigtes zeitfenster','aktuelles nachrichtenfenster']);
// Spec 09: the prototype's story steps. Each opens the section of the
// workspace that already does that work.
export const STEPS=[['analyse','Analyse','workspace-context'],['storyline','Storyline','workspace-settings'],['assets','Assets','workspace-writing'],
  ['medien','Medien','workspace-research'],['outreach','Outreach','workspace-writing'],['ergebnisse','Ergebnisse','workspace-history']];
// Where a story stands: the first step whose work is not done yet.
export function currentStep(data){
  if(!data.id)return 'analyse';
  if(!data.storyline?.trim())return 'storyline';
  const letters=data.letters||[];
  if(!data.assets?.length&&!letters.length)return 'assets';
  if(!data.contact_ids?.length&&!letters.length)return 'medien';
  if(data.status!=='closed'&&!data.assets.some(a=>a.released_at)&&!letters.some(l=>l.released_at))return 'outreach';
  return 'ergebnisse';
}
export function Stepper({current,onPick}){
  return <nav className="stepper" aria-label="Arbeitsschritte">{STEPS.map(([key,label],i)=><button type="button" key={key} className={`step${key===current?' step--on':''}`} aria-current={key===current?'step':undefined} onClick={()=>onPick(key)}><span>{i+1}</span>{label}</button>)}</nav>;
}
function ErrorMessage({error}){return error ? <p className="twin-error" role="alert">{error}</p>:null;}
export function JournalistPicker({items,selected,onChange,disabled=false}){
  const [query,setQuery]=useState('');
  const [onlySelected,setOnlySelected]=useState(false);
  const normalize=value=>(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('de').replace(/ß/g,'ss');
  const terms=normalize(query).trim().split(/\s+/).filter(Boolean);
  const selectedIds=new Set(selected);
  const matches=items.filter(contact=>(!onlySelected||selectedIds.has(contact.id))&&terms.every(term=>normalize(`${contact.name} ${contact.outlet||''}`).includes(term)));
  return <fieldset className="journalist-picker" disabled={disabled}><legend>Journalisten auswählen</legend>
    {items.length>0?<>
      <label className="journalist-picker__search">Nach Name oder Medium suchen<input type="search" value={query} placeholder="Name oder Medium eingeben …" onChange={event=>setQuery(event.target.value)}/></label>
      <div className="journalist-picker__toolbar"><span role="status">{selected.length} ausgewählt · {matches.length} von {items.length} Kontakten</span>
        <label className="journalist-picker__filter"><input type="checkbox" checked={onlySelected} onChange={event=>setOnlySelected(event.target.checked)}/>Nur ausgewählte</label></div>
      <div className="opportunity-contacts" role="group" aria-label="Journalistenliste">
        {matches.map(contact=><label className="journalist-picker__row" key={contact.id}>
          <input type="checkbox" checked={selectedIds.has(contact.id)} onChange={event=>onChange(event.target.checked?[...selected,contact.id]:selected.filter(id=>id!==contact.id))}/>
          <span>{contact.name}{contact.outlet&&<> · <span className="journalist-picker__outlet">{contact.outlet}</span></>}</span>
        </label>)}
        {!matches.length&&<p className="journalist-picker__empty">{onlySelected&&!selected.length?'Noch keine Journalisten ausgewählt.':'Keine passenden Journalisten gefunden.'}</p>}
      </div>
    </>:<p>Noch keine Kontakte hinterlegt. Recherchiere passende Kontakte weiter unten.</p>}
  </fieldset>;
}
function ResearchSources({queries,sources}){if(!queries.length&&!sources.length)return null;return <details><summary>Recherche und Quellen ({sources.length})</summary>
  <p>Die Recherche deckt nur die genannten Quellen ab. Ein fehlender Treffer ist kein Nachweis, dass es keine Entwicklung gibt.</p>
  {queries.map((q,i)=><div key={i}><strong>{q.category}</strong> · {q.query}<ul>{Object.entries(q.providers).map(([name,v])=><li key={name}>{name}: {v.status==='ok' ? `${v.articles} Artikel abgerufen`:v.status==='failed'?'Abruf fehlgeschlagen':'Nicht konfiguriert'}</li>)}</ul></div>)}
  <ul>{sources.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.source} · {date(s.published_at)} · {s.provider}</li>)}</ul>
</details>;}
export function OpportunityWorkspace({clientId,kind,identity,onChanged}){
  const path=`clients/${clientId}/opportunities/${kind}/${identity}`;
  const [data,setData]=useState(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const textSection=useRef(null),workspace=useRef(null);const [picked,setPicked]=useState('');
  useEffect(()=>{if(data && new URLSearchParams(window.location.search).get('view')==='assets') textSection.current?.scrollIntoView?.({block:'start'});},[data?.id]);
  const [storyline,setStoryline]=useState('');const [speaker,setSpeaker]=useState('');const [contacts,setContacts]=useState([]);
  const speakerValue=value=>value.speaker_person_id?`person:${value.speaker_person_id}`:value.speaker_statement_id||'';
  function receive(value){setData(value);setStoryline(value.storyline);setSpeaker(speakerValue(value));setContacts(value.contact_ids);}
  useEffect(()=>{let active=true;setData(null);setError('');setNotice('');request(path).then(v=>{if(active)receive(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
  async function save(activate=false){setBusy(true);setError('');setNotice('');try{
    receive(await request(path+(activate?'/activate':''),{method:activate?'POST':'PUT',body:JSON.stringify({revision:data.revision,storyline,speaker_statement_id:speaker&&!String(speaker).startsWith('person:')?Number(speaker):null,speaker_person_id:String(speaker).startsWith('person:')?Number(String(speaker).slice(7)):null,contact_ids:contacts})}));
    setNotice(activate?'Gelegenheit aktiviert. Wählen Sie den nächsten Arbeitsschritt.':'Auswahl gespeichert.');onChanged?.();
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  if(!data)return <><ErrorMessage error={error}/>{!error&&<p role="status">Workspace wird geladen…</p>}</>;
  const angleId=data.angle_id || (kind==='developed'?identity:null);
  const contextDirty=storyline!==data.storyline || String(speaker)!==String(speakerValue(data)) || JSON.stringify(contacts)!==JSON.stringify(data.contact_ids);
  const prepared=data.assets.find(a=>a.kind==='pressemitteilung');
  const step=picked||currentStep(data);
  const whyNow=(data.why_now||'').trim();
  const meaningfulTiming=whyNow&&!timingPlaceholders.has(whyNow.toLowerCase().replace(/[.!]$/,''));
  const timing=data.window_ends_at?`Eingeschätztes Nachrichtenfenster bis ${date(data.window_ends_at)}`:data.proposed_window_days>0?`Vorgeschlagenes Planungsfenster: ${data.proposed_window_days} Tage.`:'';
  const hasEvidence=data.risks.length>0||data.proof_points.length>0||data.research.length>0||data.sources.length>0;
  function pick(key){setPicked(key);const section=STEPS.find(s=>s[0]===key)[2];const node=workspace.current?.querySelector(`.${section}`);
    if(node?.tagName==='DETAILS')node.open=true;node?.scrollIntoView?.({block:'start',behavior:'smooth'});}
  return <div className="opportunity-workspace" ref={workspace}><p className="twin-eyebrow">{kind==='detected'?'Erkannte Gelegenheit':'Entwickelte Gelegenheit'} · {statusLabels[data.status]} · {data.evidence_type}</p><h2 className="opportunity-title">{data.title}</h2>
    <Stepper current={step} onPick={pick}/>
    <ErrorMessage error={error}/>{notice&&<p role="status">{notice}</p>}
    <details className="workspace-context" open={!data.id&&!prepared}><summary>Anlass & Belege <span>Relevanz, Timing und Quellen</span></summary>
    <div className="workspace-overview">
      <section className="twin-field opportunity-brief"><div className="brief-heading"><span className="twin-eyebrow">DAS BRIEFING</span><h3>Die Chance auf einen Blick</h3></div>
        {data.situation?.trim()&&<div className="brief-section"><h3>Was ist die Chance?</h3><p>{data.situation}</p></div>}
        {data.relevance?.trim()&&<div className="brief-section"><h3>Warum relevant?</h3><p>{data.relevance}</p></div>}
        {(meaningfulTiming||timing)&&<div className="brief-section"><h3>{meaningfulTiming?'Warum jetzt?':'Planungsfenster'}</h3>{meaningfulTiming&&<p>{whyNow}</p>}{timing&&<p className="brief-timing">{timing}</p>}</div>}
        {data.recommended_actions.length>0&&<div className="brief-section"><h3>Empfohlene Maßnahmen</h3><ul className="brief-actions">{data.recommended_actions.map(a=><li key={a}>{actionLabels[a]||a}</li>)}</ul></div>}
      </section>
      {hasEvidence&&<section className="twin-field workspace-intelligence"><div className="brief-heading"><span className="twin-eyebrow">RAUTE INTELLIGENCE</span><h3>Belege und offene Fragen</h3></div>
        {data.risks.length>0&&<div className="brief-risks"><h4>Vor der Umsetzung prüfen</h4><ul>{data.risks.map((r,i)=><li key={i}>{r}</li>)}</ul></div>}
        {data.proof_points.map(p=><div className="brief-proof" key={p.id}><p>{p.value}</p><small>{p.evidence_type || 'Herkunft unbekannt'} · {p.fact_status || 'Ungeprüft'} · {p.verified_at?'Bestätigung hinterlegt':'Nicht unabhängig bestätigt'}</small></div>)}
        <ResearchSources queries={data.research} sources={data.sources}/>
      </section>}
    </div></details><details className="workspace-settings" open={!data.id&&!prepared}><summary>Storyline & Kontakte <span>{contacts.length ? `${contacts.length} ausgewählt` : 'Ansprache vorbereiten'}</span></summary><section className="twin-field"><h3>Storyline und Sprecher</h3>{contextDirty&&<p role="status">Ungespeicherte Auswahl</p>}
      {data.storylines.length>0&&<label>Storyline-Vorschlag übernehmen<select aria-label="Storyline-Vorschlag übernehmen" value="" onChange={e=>setStoryline(data.storylines[Number(e.target.value)])} disabled={busy||data.status==='closed'}><option value="" disabled>Vorschlag auswählen …</option>{data.storylines.map((s,i)=><option key={i} value={i}>{s}</option>)}</select></label>}
      <label>Gewählte Storyline<textarea aria-label="Gewählte Storyline" value={storyline} onChange={e=>setStoryline(e.target.value)} disabled={busy||data.status==='closed'}/></label>
      <label>Sprecher aus dem Profil<select aria-label="Sprecher aus dem Profil" value={speaker} onChange={e=>setSpeaker(e.target.value)} disabled={busy||data.status==='closed'}><option value="">Noch nicht gewählt</option>
        {(data.speaker_people||[]).map(person=><option key={`person:${person.id}`} value={`person:${person.id}`}>{person.name}{person.position?` · ${person.position}`:''} · Medienkontakt</option>)}
        {data.speakers.map(s=><option key={s.id} value={s.id}>{s.value} · {s.evidence_type || 'Ungeprüft'}</option>)}</select></label>
      <p><a href={`/client/${clientId}/twin`}>Sprecher und Freigabe im Profil pflegen</a></p>
      <JournalistPicker items={data.contacts} selected={contacts} onChange={setContacts} disabled={busy||data.status==='closed'}/>
      {data.status!=='closed'&&<div className="twin-toolbar"><button className="btn" disabled={busy} onClick={()=>save()}>Auswahl speichern</button>
        {data.status!=='active'&&<button className="btn btn--go" disabled={busy||!storyline.trim()} onClick={()=>save(true)}>Opportunity aktivieren</button>}</div>}

    </section>
    </details><section ref={textSection} className="workspace-writing" aria-label="Texte & Belege">{!data.id&&prepared&&angleId&&<PreparedRelease clientId={clientId} angleId={angleId} asset={prepared}/>}
    {!data.id&&<p>Für weitere Texte: Öffne „Storyline & Kontakte“ und speichere deine Auswahl.</p>}
    {data.id && data.status!=='closed' && <ActivationPanel clientId={clientId} kind={kind} identity={identity} angleId={angleId} existingAssets={data.assets} contextDirty={contextDirty} contacts={data.contacts.filter(c=>data.contact_ids.includes(c.id))} onCompleted={()=>request(path).then(value=>setData(old=>({...old,events:value.events,assets:value.assets}))).catch(e=>setError(e.message))}/>}
    {data.status==='active'&&<p><a href={data.legacy_href}>Freigaben öffnen</a></p>}</section><details className="workspace-research"><summary>Passende Kontakte recherchieren <span>Aktuelle Artikel & Empfehlungen</span></summary><ResearchPanel clientId={clientId} contextKind={kind} contextId={identity} onContact={(id,person)=>{window.location.href=id?`/contacts?contact=${id}`:`/contacts?client=${clientId}&kind=${kind}&context=${identity}`;}}/>
    </details><details className="workspace-history"><summary>Aktivität & gespeicherte Texte <span>{data.events.length} Arbeitsschritte</span></summary><section className="twin-field"><h3>Aktivität dieser Gelegenheit</h3><p>Entwicklung und Aktivierung sind noch keine ausgelieferte Kundenleistung.</p>
      {data.events.length?<ul>{data.events.map(e=><li key={e.id}>{date(e.created_at)} · {eventLabels[e.kind]||e.kind} · {e.actor}{e.detail.kind&&` · ${actionLabels[e.detail.kind]||e.detail.kind}`}{e.detail.contact_ids&&` · ${e.detail.contact_ids.length} Journalisten ausgewählt`}</li>)}</ul>:<p>Noch keine Aktivität hinterlegt.</p>}
      <h3>Texte</h3>{data.assets.length||data.letters?.length?<ul>{data.assets.map(a=><li key={a.id}><a href={a.href}>{a.title||actionLabels[a.kind]||a.kind}</a> · {a.released_at?'Freigegeben':'Entwurf'} · {date(a.generated_at)}</li>)}
        {(data.letters||[]).map(l=><li key={`letter-${l.id}`}><a href={l.href}>{l.subject||actionLabels.pitch}</a> · {[l.journalist,l.outlet].filter(Boolean).join(', ')||actionLabels.pitch} · {letterStates[l.state]||l.state} · {date(l.generated_at)}</li>)}</ul>:<p>Noch keine Texte erstellt.</p>}</section></details>
  </div>;
}
export function OpportunitiesPage({clientId,params=new URLSearchParams(window.location.search)}){
  const [board,setBoard]=useState(null);const [error,setError]=useState('');const [focus,setFocus]=useState('');const [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState(params.get('context')?{kind:params.get('kind')||'developed',id:Number(params.get('context'))}:null);
  const path=`clients/${clientId}/opportunities`;
  async function refresh(){setBoard(await request(path));}
  useEffect(()=>{let active=true;request(path).then(v=>{if(active)setBoard(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
  const running=board?.development?.status==='running'&&Date.now()-new Date(board.development.started_at).getTime()<1200000;
  useEffect(()=>{if(!running)return;let active=true;const timer=setInterval(()=>request(path).then(v=>{if(active){setBoard(v);setError('');}}).catch(e=>{if(active)setError(e.message);}),2500);return()=>{active=false;clearInterval(timer);};},[path,running]);
  async function develop(event){event.preventDefault();setBusy(true);setError('');try{const job=await request(path+'/develop',{method:'POST',body:JSON.stringify({focus})});setBoard(v=>({...v,development:job}));}catch(e){setError(e.message);}finally{setBusy(false);}}
  useEffect(()=>{if(selected)document.querySelector('.communication-workspace')?.scrollIntoView?.({behavior:'smooth',block:'start'});},[selected,board!==null]);
  function open(row){setSelected({kind:row.context_kind,id:row.context_id});history.replaceState(null,'',`?kind=${row.context_kind}&context=${row.context_id}`);}
  // A card shows what it is about at a glance; hovering (or focusing) it shows
  // the core message and the story it rests on, without opening the workspace.
  const card=row=>{const key=`${row.context_kind}-${row.context_id}`,peek=`peek-${key}`,o=row.occasion;
    return <button type="button" className="communication-card communication-card--peek" key={key} aria-describedby={row.summary||o?peek:undefined} aria-pressed={selected?.kind===row.context_kind&&selected?.id===row.context_id} onClick={()=>open(row)}>
      <span>{originLabels[row.origin]||(row.context_kind==='detected'?'Anlass':'Impuls')} · {statusLabels[row.status]||row.status}{row.created_at&&` · ${date(row.created_at).split(',')[0]}`}</span>
      <h3>{row.title}</h3>
      {o&&<small className="communication-card__source">{o.source}{o.published_at&&` · ${date(o.published_at).split(',')[0]}`}</small>}
      {(row.summary||o)&&<span className="communication-peek" id={peek} role="tooltip">
        {row.summary&&<><b>Kernaussage</b><span>{row.summary}</span></>}
        {o&&<><b>Anlass</b><span>{o.title}</span><em>{o.source}{o.published_at&&` · ${date(o.published_at).split(',')[0]}`}</em></>}
      </span>}
      <small>Öffnen →</small></button>;};
  const visible=(board?.opportunities||[]).filter(row=>row.status!=='closed');
  // Market stories, detected or drafted by the radar, are Anlässe; what RAUTE
  // developed on request or a plan hook opened is an Impuls.
  const isAnlass=row=>(row.origin||(row.context_kind==='detected'?'anlass':'pitch'))==='anlass';
  const reactive=visible.filter(isAnlass);
  const proactive=visible.filter(row=>!isAnlass(row));
  return <section className="twin-page opportunities-page"><PageHeading eyebrow={board?.client.name} title="Aktivitäten" description="Issues und Krisen, Opportunities und eigene Impulse an einem Ort."/><ErrorMessage error={error}/>
    {!board&&!error&&<p role="status">Aktivitäten werden geladen…</p>}
    {board&&<><div className="communication-columns">
      <section className="communication-column" aria-label="Issues / Krisen"><header><h2>Issues / Krisen</h2><p>Risiken beobachten und Krisen bearbeiten.</p></header>
        <div className="communication-crisis">
          {board.reaction?.crisis?<a className="communication-card communication-card--urgent" href={board.reaction.crisis.href}><span>Aktive Krise</span><h3>{board.reaction.crisis.title}</h3><small>Krise bearbeiten →</small></a>:<p className="communication-empty">Keine aktive Krise.</p>}
          {(board.reaction?.issues||[]).map(issue=><a className="communication-card" key={issue.id} href={issue.href}><span>Issue · in Beobachtung</span><h3>{issue.title}</h3><small>Issue prüfen →</small></a>)}
          <a href={`/client/${clientId}/issues`}>Issues und mögliche Risiken prüfen →</a>
        </div>
      </section>
      <section className="communication-column" aria-label="Opportunities"><header><h2>Opportunities</h2><p>Aktuelle Anlässe für die Kommunikation aufgreifen.</p></header>
        <h3>Aktuelle Anlässe <span className="communication-count">{reactive.length}</span></h3>
        {reactive.length?reactive.map(card):<p className="communication-empty">Noch kein offener Kommunikationsanlass. Neue Kundenmeldungen stehen im Überblick.</p>}
        <a href={`/client/${clientId}/overview#kundennews`}>Zu den Kundennews →</a>
      </section>
      <section className="communication-column" aria-label="Impulse"><header><h2>Impulse</h2><p>Eigene Themen und Pitches aus dem Kundenwissen entwickeln.</p></header>
        <details className="development-panel" open={params.has('develop')||!proactive.length||running}><summary>Neuen Themen-Pitch entwickeln</summary><p>Aus Profil, Positionierung und Recherche – auch ohne aktuellen Nachrichtenanlass.</p>
          <form onSubmit={develop}><label>Recherchefokus<input aria-label="Recherchefokus" required minLength={3} maxLength={300} value={focus} onChange={e=>setFocus(e.target.value)} placeholder="Welches Thema soll der Kunde besetzen?"/></label>
            <button className="btn btn--go" disabled={busy||running}>{running?'Recherche und Entwicklung laufen…':'Themen-Pitch entwickeln'}</button></form>
          {board.development&&<div><p role="status">{({running:'In Arbeit',complete:'Ideen entwickelt',no_opportunity:'Keine neue tragfähige Idee',failed:'Entwicklung fehlgeschlagen'})[board.development.status]} · {date(board.development.finished_at||board.development.started_at)}</p><p>{board.development.note}</p><ResearchSources queries={board.development.queries} sources={board.development.sources}/></div>}
        </details>
        <h3>Themen-Pitches <span className="communication-count">{proactive.length}</span></h3>
        {proactive.length?proactive.map(card):<p className="communication-empty">Noch keine offenen Themen-Pitches. Beginne mit einem Recherchefokus.</p>}
      </section>
    </div>
    <p className="communication-handoff">Bereit für die Ausarbeitung? <a href={`/client/${clientId}/plan`}>Zur Umsetzung →</a></p>
    {selected&&<section className="communication-workspace" aria-label="Kommunikation bearbeiten"><button type="button" className="btn" onClick={()=>{setSelected(null);history.replaceState(null,'',window.location.pathname);}}>Bearbeitung schließen</button><OpportunityWorkspace key={`${selected.kind}-${selected.id}`} clientId={clientId} kind={selected.kind} identity={selected.id} onChanged={()=>refresh().catch(e=>setError(e.message))}/></section>}
    {board.opportunities.some(row=>row.status==='closed')&&<details className="communication-closed"><summary>Abgeschlossene Vorgänge</summary>{board.opportunities.filter(row=>row.status==='closed').map(card)}</details>}
    </>}
  </section>;
}
