import React,{useEffect,useRef,useState} from 'react';
import {PageHeading,EmptyState} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';
import {ResearchPanel} from './JournalistsPage.jsx';
import {ActivationPanel,PreparedRelease} from './ActivationPanel.jsx';
const date=value=>value ? new Date(value).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'}) : 'Nicht festgelegt';
const statusLabels={draft:'Entwurf',active:'Aktiviert',closed:'Abgeschlossen'};
const eventLabels={idea_developed:'Idee entwickelt',choices_saved:'Auswahl gespeichert',activated:'Aktiviert',text_created:'Text erstellt',text_checked:'Aussagen geprüft',text_edited:'Text bearbeitet'};
const actionLabels={kundenmail:'Kundenmail',pitch:'Journalistenpitch',statement:'Statement',pressemitteilung:'Pressemitteilung',qa:'Q&A',gastbeitrag:'Gastbeitrag',interviewangebot:'Interviewangebot',linkedin:'LinkedIn-Post',briefing:'Briefing',custom:'Eigene Aktion'};
function ErrorMessage({error}){return error ? <p className="twin-error" role="alert">{error}</p>:null;}
function ResearchSources({queries,sources}){return <details><summary>Recherche und Quellen ({sources.length})</summary>
  <p>Die Recherche deckt nur die genannten Quellen ab. Ein fehlender Treffer ist kein Nachweis, dass es keine Entwicklung gibt.</p>
  {queries.map((q,i)=><div key={i}><strong>{q.category}</strong> · {q.query}<ul>{Object.entries(q.providers).map(([name,v])=><li key={name}>{name}: {v.status==='ok' ? `${v.articles} Artikel abgerufen`:v.status==='failed'?'Abruf fehlgeschlagen':'Nicht konfiguriert'}</li>)}</ul></div>)}
  <ul>{sources.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.source} · {date(s.published_at)} · {s.provider}</li>)}</ul>
</details>;}
export function OpportunityWorkspace({clientId,kind,identity,onChanged}){
  const path=`clients/${clientId}/opportunities/${kind}/${identity}`;
  const [data,setData]=useState(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const textSection=useRef(null);
  useEffect(()=>{if(data && new URLSearchParams(window.location.search).get('view')==='assets') textSection.current?.scrollIntoView?.({block:'start'});},[data?.id]);
  const [storyline,setStoryline]=useState('');const [speaker,setSpeaker]=useState('');const [contacts,setContacts]=useState([]);
  function receive(value){setData(value);setStoryline(value.storyline);setSpeaker(value.speaker_statement_id || '');setContacts(value.contact_ids);}
  useEffect(()=>{let active=true;setData(null);setError('');setNotice('');request(path).then(v=>{if(active)receive(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
  async function save(activate=false){setBusy(true);setError('');setNotice('');try{
    receive(await request(path+(activate?'/activate':''),{method:activate?'POST':'PUT',body:JSON.stringify({revision:data.revision,storyline,speaker_statement_id:speaker?Number(speaker):null,contact_ids:contacts})}));
    setNotice(activate?'Gelegenheit aktiviert. Wählen Sie den nächsten Arbeitsschritt.':'Auswahl gespeichert.');onChanged?.();
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  if(!data)return <><ErrorMessage error={error}/>{!error&&<p role="status">Workspace wird geladen…</p>}</>;
  const angleId=data.angle_id || (kind==='developed'?identity:null);
  const contextDirty=storyline!==data.storyline || String(speaker)!==String(data.speaker_statement_id||'') || JSON.stringify(contacts)!==JSON.stringify(data.contact_ids);
  const prepared=data.assets.find(a=>a.kind==='pressemitteilung');
  return <div className="opportunity-workspace"><p className="twin-eyebrow">{kind==='detected'?'Erkannte Gelegenheit':'Entwickelte Gelegenheit'} · {statusLabels[data.status]} · {data.evidence_type}</p><h2 className="opportunity-title">{data.title}</h2>
    <ErrorMessage error={error}/>{notice&&<p role="status">{notice}</p>}
    <details className="workspace-context" open={!data.id&&!prepared}><summary>Anlass & Belege <span>Relevanz, Timing und Quellen</span></summary>
    <div className="workspace-overview">
      <section className="twin-field opportunity-brief"><div className="brief-heading"><span className="twin-eyebrow">DAS BRIEFING</span><h3>Die Chance auf einen Blick</h3></div>
        <div className="brief-section"><h3>Was ist die Chance?</h3><p>{data.situation}</p></div>
        <div className="brief-section"><h3>Warum relevant?</h3><p>{data.relevance}</p></div>
        <div className="brief-section"><h3>Warum jetzt?</h3><p>{data.why_now}</p><p className="brief-timing">{data.window_ends_at?`Nachrichtenfenster bis ${date(data.window_ends_at)}`:data.proposed_window_days?`Vorgeschlagenes Planungsfenster: ${data.proposed_window_days} Tage. Keine bestätigte externe Frist.`:'Kein bestätigtes Zeitfenster.'}</p></div>
        <div className="brief-section"><h3>Empfohlene Maßnahmen</h3><ul className="brief-actions">{data.recommended_actions.map(a=><li key={a}>{actionLabels[a]||a}</li>)}</ul></div>
      </section>
      <section className="twin-field workspace-intelligence"><div className="brief-heading"><span className="twin-eyebrow">RAUTE INTELLIGENCE</span><h3>Belege und offene Fragen</h3></div>
        {data.risks.length>0&&<div className="brief-risks"><h4>Vor der Umsetzung prüfen</h4><ul>{data.risks.map((r,i)=><li key={i}>{r}</li>)}</ul></div>}
        {data.proof_points.map(p=><div className="brief-proof" key={p.id}><p>{p.value}</p><small>{p.evidence_type || 'Herkunft unbekannt'} · {p.fact_status || 'Ungeprüft'} · {p.verified_at?'Bestätigung hinterlegt':'Nicht unabhängig bestätigt'}</small></div>)}
        <ResearchSources queries={data.research} sources={data.sources}/>
      </section>
    </div></details><details className="workspace-settings" open={!data.id&&!prepared}><summary>Storyline & Kontakte <span>{contacts.length ? `${contacts.length} ausgewählt` : 'Ansprache vorbereiten'}</span></summary><section className="twin-field"><h3>Storyline und Sprecher</h3>{contextDirty&&<p role="status">Ungespeicherte Auswahl</p>}
      {data.storylines.length>0&&<label>Storyline-Vorschlag übernehmen<select aria-label="Storyline-Vorschlag übernehmen" value="" onChange={e=>setStoryline(data.storylines[Number(e.target.value)])} disabled={busy||data.status==='closed'}><option value="" disabled>Vorschlag auswählen …</option>{data.storylines.map((s,i)=><option key={i} value={i}>{s}</option>)}</select></label>}
      <label>Gewählte Storyline<textarea aria-label="Gewählte Storyline" value={storyline} onChange={e=>setStoryline(e.target.value)} disabled={busy||data.status==='closed'}/></label>
      <label>Sprecher aus dem Profil<select aria-label="Sprecher aus dem Profil" value={speaker} onChange={e=>setSpeaker(e.target.value)} disabled={busy||data.status==='closed'}><option value="">Noch nicht gewählt</option>
        {data.speakers.map(s=><option key={s.id} value={s.id}>{s.value} · {s.evidence_type || 'Ungeprüft'}</option>)}</select></label>
      <p><a href={`/client/${clientId}/twin`}>Sprecher und Freigabe im Profil pflegen</a></p>
      <fieldset disabled={busy||data.status==='closed'}><legend>Journalisten auswählen</legend><div className="opportunity-contacts">{data.contacts.map(c=><label key={c.id}>
        <input type="checkbox" checked={contacts.includes(c.id)} onChange={e=>setContacts(e.target.checked?[...contacts,c.id]:contacts.filter(id=>id!==c.id))}/>{c.name} · {c.outlet}</label>)}</div>
        {!data.contacts.length&&<p>Noch keine Kontakte hinterlegt. Recherchiere passende Kontakte weiter unten.</p>}</fieldset>
      {data.status!=='closed'&&<div className="twin-toolbar"><button className="btn" disabled={busy} onClick={()=>save()}>Auswahl speichern</button>
        {data.status!=='active'&&<button className="btn btn--go" disabled={busy||!storyline.trim()} onClick={()=>save(true)}>Opportunity aktivieren</button>}</div>}

    </section>
    </details><section ref={textSection} className="workspace-writing" aria-label="Texte & Belege">{!data.id&&prepared&&angleId&&<PreparedRelease clientId={clientId} angleId={angleId} asset={prepared}/>}
    {!data.id&&<p>Für weitere Texte: Öffne „Storyline & Kontakte“ und speichere deine Auswahl.</p>}
    {data.id && data.status!=='closed' && <ActivationPanel clientId={clientId} kind={kind} identity={identity} angleId={angleId} existingAssets={data.assets} contextDirty={contextDirty} contacts={data.contacts.filter(c=>data.contact_ids.includes(c.id))} onCompleted={()=>request(path).then(value=>setData(old=>({...old,events:value.events,assets:value.assets}))).catch(e=>setError(e.message))}/>}
    {data.status==='active'&&<p><a href={data.legacy_href}>Freigaben öffnen</a></p>}</section><details className="workspace-research"><summary>Passende Kontakte recherchieren <span>Aktuelle Artikel & Empfehlungen</span></summary><ResearchPanel clientId={clientId} contextKind={kind} contextId={identity} onContact={(id,person)=>{window.location.href=id?`/contacts?contact=${id}`:`/contacts?client=${clientId}&kind=${kind}&context=${identity}`;}}/>
    </details><details className="workspace-history"><summary>Aktivität & gespeicherte Texte <span>{data.events.length} Arbeitsschritte</span></summary><section className="twin-field"><h3>Aktivität dieser Gelegenheit</h3><p>Entwicklung und Aktivierung sind noch keine ausgelieferte Kundenleistung.</p>
      {data.events.length?<ul>{data.events.map(e=><li key={e.id}>{date(e.created_at)} · {eventLabels[e.kind]||e.kind} · {e.actor}{e.detail.kind&&` · ${actionLabels[e.detail.kind]||e.detail.kind}`}{e.detail.contact_ids&&` · ${e.detail.contact_ids.length} Journalisten ausgewählt`}</li>)}</ul>:<p>Noch keine Aktivität hinterlegt.</p>}
      <h3>Texte</h3>{data.assets.length?<ul>{data.assets.map(a=><li key={a.id}><a href={a.href}>{a.title||a.kind}</a> · {a.released_at?'Freigegeben':'Entwurf'} · {date(a.generated_at)}</li>)}</ul>:<p>Noch keine Texte erstellt.</p>}</section></details>
  </div>;
}
export function OpportunitiesPage({clientId,params=new URLSearchParams(window.location.search)}){
  const [filter,setFilter]=useState('all');
  const [board,setBoard]=useState(null);const [error,setError]=useState('');const [focus,setFocus]=useState('');const [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState(params.get('context')?{kind:params.get('kind')||'developed',id:Number(params.get('context'))}:null);
  const path=`clients/${clientId}/opportunities`;
  async function refresh(){setBoard(await request(path));}
  useEffect(()=>{let active=true;request(path).then(v=>{if(active)setBoard(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
  const running=board?.development?.status==='running'&&Date.now()-new Date(board.development.started_at).getTime()<1200000;
  useEffect(()=>{if(!running)return;let active=true;const timer=setInterval(()=>request(path).then(v=>{if(active){setBoard(v);setError('');}}).catch(e=>{if(active)setError(e.message);}),2500);return()=>{active=false;clearInterval(timer);};},[path,running]);
  async function develop(event){event.preventDefault();setBusy(true);setError('');try{const job=await request(path+'/develop',{method:'POST',body:JSON.stringify({focus})});setBoard(v=>({...v,development:job}));}catch(e){setError(e.message);}finally{setBusy(false);}}
  function open(row){setSelected({kind:row.context_kind,id:row.context_id});history.replaceState(null,'',`?kind=${row.context_kind}&context=${row.context_id}`);}
  return <main className="twin-page opportunities-page"><PageHeading eyebrow={board?.client.name} title="Opportunities" description="Relevante Anlässe erkennen. Gute Geschichten entwickeln."/><ErrorMessage error={error}/>
    <details className="twin-field development-panel" open={params.has('develop')||!board?.opportunities.length||running}><summary>Neue Kommunikationschance entwickeln</summary><p>Aus Profil, Positionierung und aktueller Recherche. Ein einzelner Nachrichtenanlass ist nicht nötig. Die Ideen bleiben Vorschläge zur Prüfung.</p>
      <form onSubmit={develop}><label>Recherchefokus<input aria-label="Recherchefokus" required minLength={3} maxLength={300} value={focus} onChange={e=>setFocus(e.target.value)} placeholder="Zum Beispiel: BioLNG im Schwerlastverkehr"/></label>
        <button className="btn btn--go" disabled={!board||busy||running}>{running?'Recherche und Entwicklung laufen…':'Chance entwickeln'}</button></form>
      {board?.development&&<div><p role="status">{({running:'In Arbeit',complete:'Ideen entwickelt',no_opportunity:'Keine neue tragfähige Idee',failed:'Entwicklung fehlgeschlagen'})[board.development.status]} · {date(board.development.finished_at||board.development.started_at)}</p>
        <p>{board.development.note}</p><ResearchSources queries={board.development.queries} sources={board.development.sources}/></div>}
    </details>
    <div className="opportunity-layout"><aside className="twin-field"><h2>Gelegenheiten</h2>{(filter!=='all'||new Set(board?.opportunities.map(row=>row.context_kind)).size>1)&&<label>Ansicht<select aria-label="Gelegenheiten filtern" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">Alle</option><option value="detected">Erkannt</option><option value="developed">Entwickelt</option></select></label>}<ul className="journalist-roster">{board?.opportunities.filter(row=>filter==='all'||row.context_kind===filter).map(row=><li key={`${row.context_kind}-${row.context_id}`}>
      <button aria-pressed={selected?.kind===row.context_kind&&selected?.id===row.context_id} onClick={()=>open(row)}>{row.title}<small>{row.context_kind==='detected'?'Erkannt':'Entwickelt'} · {statusLabels[row.status]}</small></button></li>)}</ul>
      {board?.opportunities.length===0&&<p>Noch keine Gelegenheiten. Entwickeln Sie eine neue Chance oder prüfen Sie die aktuellen Nachrichten.</p>}</aside>
      <div>{selected?<OpportunityWorkspace key={`${selected.kind}-${selected.id}`} clientId={clientId} kind={selected.kind} identity={selected.id} onChanged={()=>refresh().catch(e=>setError(e.message))}/>:<EmptyState title="Gelegenheit öffnen">Wählen Sie einen Vorschlag, um Quellen, Storyline und nächste Schritte zu prüfen.</EmptyState>}</div></div>
  </main>;
}
