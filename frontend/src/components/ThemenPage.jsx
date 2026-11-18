import React,{useEffect,useRef,useState} from 'react';
import {setTopicActive} from '../topic-actions.js';
import {ThemenWorkflow} from './ThemenWorkflow.jsx';
import {PageHeading} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';

// Spec 12: what could become communication, from a starred article ("Aus
// Medien") or a proposal by RAUTE. The Deep Dive opens as a detail page;
// "Thema aktivieren" moves the Thema to Assets, where it is written.
const day=value=>value?new Date(value).toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'}):'';
const MONTHS=['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
const FILTERS=[['alle','Alle'],['medien','★ Aus Medien'],['raute','Vorschläge von RAUTE'],['aktiv','In Bearbeitung'],['abgeschlossen','Abgeschlossen']];
export const fromMedien=row=>row.origin==='medien';
const ORIGIN={anlass:'Anlass aus dem Radar',pitch:'Themen-Pitch',plan:'Aus der Agenda',medien:'★ Aus Medien'};

// The pitch is the line the Thema would be argued with: the chosen storyline,
// else RAUTE's first one, else its summary.
export const pitchOf=detail=>(detail?.storyline||detail?.storylines?.[0]||'').trim();

export function ThemaDetails(props){return <ThemenWorkflow {...props}/>;}

// Who to talk to: bylines from the stories, else the outlets that cover the
// field. Never an invented name (workspaces.recipients).
export function Recipients({list}){
 if(!list?.length)return <p className="themen-empty">Noch keine passenden Medien gefunden.</p>;
 return <ul className="themen-recipients">{list.map((r,i)=><li key={i}><strong>{r.name}</strong>{r.outlet&&` · ${r.outlet}`}{r.reason&&<small>{r.reason}</small>}</li>)}</ul>;
}

const details=new Map();
function loadDetail(path){if(!details.has(path))details.set(path,request(path).catch(e=>{details.delete(path);throw e;}));return details.get(path);}

// The Deep Dive on the card, as in the mockup: it opens while the pointer or
// the keyboard focus is on "Deep Dive", and is read once.
export function DeepDive({clientId,clientName,row}){
 const path=`clients/${clientId}/opportunities/${row.context_kind}/${row.context_id}`;
 const [open,setOpen]=useState(false),[detail,setDetail]=useState(null),[error,setError]=useState('');
 const timer=useRef(0);
 function show(){clearTimeout(timer.current);setOpen(true);if(!detail)loadDetail(path).then(setDetail).catch(e=>setError(e.message));}
 function hide(){clearTimeout(timer.current);timer.current=setTimeout(()=>setOpen(false),150);}
 const missing=<span className="themen-empty">bitte ergänzen</span>;
 return <div className="themen-dive" onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
  <button type="button" className="btn btn--quiet themen-dive__trigger" aria-expanded={open} onClick={()=>open?setOpen(false):show()}>Deep Dive</button>
  {open&&<div className="themen-dive__pop" role="tooltip">
   {error?<p role="alert">{error}</p>:!detail?<p role="status">Deep Dive wird geladen…</p>:<>
    {detail.deep_dive==='pending'&&<p role="status" className="themen-hint">RAUTE schreibt den Deep Dive noch.</p>}
    <section><h3>Was ist passiert?</h3><p>{detail.situation?.trim()||missing}</p></section>
    <section><h3>Warum für {clientName} relevant?</h3><p>{detail.relevance?.trim()||missing}</p></section>
    <section className="themen-dive__pitch"><h3>Pitch</h3><p>{pitchOf(detail)||missing}</p></section>
    <section><h3>Passende Ansprechpartner</h3><Recipients list={detail.recipients}/></section>
   </>}
  </div>}
 </div>;
}

function Card({clientId,clientName,row,onChanged}){
 const o=row.occasion;
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const active=row.status==='active'&&!row.workflow_summary?.completed;
 async function toggle(){setBusy(true);setError('');try{const next=await setTopicActive(clientId,row,!active);if(!next)return;details.delete(`clients/${clientId}/opportunities/${row.context_kind}/${row.context_id}`);onChanged(next);}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <article id={`thema-${row.context_kind}-${row.context_id}`} className={`themen-card${active?' themen-card--active':''}`}>
  <div className="themen-card__meta"><span className={`themen-tag${fromMedien(row)?' themen-tag--star':''}`}>{ORIGIN[row.origin]||'Vorschlag von RAUTE'}{row.starred_by&&` · @${row.starred_by}`}</span>
   {active&&<span className="themen-tag themen-tag--on">✓ Aktiviert</span>}{!active&&row.workflow_summary?.label&&<span className="themen-tag">{row.workflow_summary.label}</span>}
   {o&&<span className="themen-card__source">{o.source}{o.published_at&&` · ${day(o.published_at)}`}</span>}</div>
  <h2>{row.title}</h2>
  {o?.url&&<p className="themen-hint">Auslöser: <a href={o.url} target="_blank" rel="noopener noreferrer">{o.title||o.source} ↗</a></p>}
  <div className="themen-card__acts">
   <span className="themen-card__left"><DeepDive clientId={clientId} clientName={clientName} row={row}/>
    <a className="themen-card__more" href={`/client/${clientId}/themen?kind=${row.context_kind}&context=${row.context_id}`}>Details ansehen</a></span>
   <div className="topic-actions">
   {row.workflow_summary?.completed?<a className="btn btn--go" href={`/client/${clientId}/themen?kind=${row.context_kind}&context=${row.context_id}&step=ergebnis`}>Ergebnis ansehen →</a>:<>
    {active&&<a className="btn btn--quiet" href={`/client/${clientId}/themen?kind=${row.context_kind}&context=${row.context_id}&step=${row.workflow_summary?.step||'assets'}`}>Weiterarbeiten →</a>}
    <button type="button" className={`btn ${active?'btn--quiet':'btn--go'}`} disabled={busy} onClick={toggle}>{busy?'Wird gespeichert…':active?'Thema deaktivieren':'Thema aktivieren'}</button>
    {active&&<a className="btn btn--go" href={`/client/${clientId}/assets?kind=${row.context_kind}&context=${row.context_id}`}>Zu den Assets →</a>}
   </>}
   </div>
  </div>
  {error&&<p role="alert" className="topic-error">{error}</p>}
 </article>;
}

export function Agenda({clientId}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{request(`clients/${clientId}/agenda`).then(setData).catch(e=>setError(e.message));},[clientId]);
 const when=item=>item.kind==='topic'?'Aktueller Anlass':item.day?`${String(item.day).padStart(2,'0')}.${item.month.slice(5)}.`:`${MONTHS[Number(item.month.slice(5))-1]} ${item.month.slice(0,4)}`;
 const formatLabel=value=>({linkedin:'LinkedIn-Post',pressemitteilung:'Pressemitteilung',statement:'Statement',gastbeitrag:'Gastbeitrag',pitch:'Medienpitch',interviewangebot:'Interviewangebot',kundenmail:'Kundenmail',briefing:'Briefing'})[value]||value;
 return <aside className="themen-agenda" aria-labelledby="agenda-title">
  <header><h2 id="agenda-title">Agenda</h2><a href={data?.href||`/client/${clientId}/plan`}>Ganze Agenda →</a></header>
  {error&&<p role="alert">{error}</p>}
  {data&&!data.items.length&&<p className="themen-empty">Noch keine Termine. Die Agenda füllt sich aus Marktsignalen und Themen.</p>}
  {data?.items.length>0&&<ol className="themen-timeline">{data.items.map(item=><li key={item.id} className={`themen-timeline__item themen-timeline__item--${item.state}`}>
   <div className="themen-agenda-meta"><span className="themen-timeline__when">{when(item)}</span><span className={`themen-agenda-status${item.state==='angenommen'?' themen-agenda-status--planned':''}`}>{item.state==='angenommen'?(item.kind==='topic'?'Aktiv':'Geplant'):'Vorschlag'}</span></div>
   <h3 className="themen-agenda-topic"><a href={item.href}>{item.title||'Ohne Titel'}</a></h3>
   <p className="themen-agenda-caption">{item.format&&<span>{formatLabel(item.format)}</span>}{!item.day&&<span>Termin noch offen</span>}</p>
   {item.next_steps?.length>0&&<div className="themen-agenda-actions"><strong>Nächste Schritte</strong><ol>{item.next_steps.map((step,index)=><li key={index}>{step}</li>)}</ol></div>}
   <a className="themen-agenda-detail-link" href={item.href}>Details ansehen →</a>
  </li>)}</ol>}
  <a className="btn btn--quiet themen-agenda__add" href={`/client/${clientId}/plan#agenda`}>Agenda bearbeiten</a>
 </aside>;
}

export function ThemenPage({clientId}){
 const params=new URLSearchParams(window.location.search),kind=params.get('kind'),identity=Number(params.get('context'));
 if(['detected','developed'].includes(kind)&&Number.isInteger(identity)&&identity>0)return <ThemaDetails clientId={clientId} kind={kind} identity={identity}/>;
 return <ThemenList clientId={clientId}/>;
}

function ThemenList({clientId}){
 const [board,setBoard]=useState(null),[error,setError]=useState(''),[filter,setFilter]=useState('alle');
 const [developing,setDeveloping]=useState(false),[focus,setFocus]=useState('');
 const path=`clients/${clientId}/opportunities`;
 const [suggestion,setSuggestion]=useState(null);
 useEffect(()=>{let active=true;let timer;
  const endpoint=`clients/${clientId}/themen/suggestions`;
  async function check(start=false){try{
   const value=await request(endpoint,start?{method:'POST'}:{});
   if(!active)return;setSuggestion(value);
   if(value?.status==='running')timer=setTimeout(()=>check(),3000);
   else {const next=await request(path);if(active)setBoard(next);}
  }catch(e){if(active)setError(e.message);}}
  check(true);return()=>{active=false;clearTimeout(timer);};
 },[clientId,path]);
 useEffect(()=>{let active=true;request(path).then(v=>{if(active)setBoard(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
 const running=board?.development?.status==='running'&&Date.now()-new Date(board.development.started_at).getTime()<1200000;
 useEffect(()=>{if(!running)return;const timer=setInterval(()=>request(path).then(setBoard).catch(e=>setError(e.message)),2500);return()=>clearInterval(timer);},[path,running]);
 async function develop(event){event.preventDefault();setError('');try{const job=await request(path+'/develop',{method:'POST',body:JSON.stringify({focus})});setBoard(v=>({...v,development:job}));setFocus('');}catch(e){setError(e.message);}}
 const all=board?.opportunities||[];
 const isClosed=row=>row.workflow_summary?.completed||row.status==='closed';
 const open=all.filter(row=>!isClosed(row));
 const counts={alle:open.length,medien:open.filter(fromMedien).length,raute:open.filter(r=>!fromMedien(r)).length,aktiv:open.filter(r=>r.status==='active').length,abgeschlossen:all.filter(isClosed).length};
 const shown=filter==='abgeschlossen'?all.filter(isClosed):open.filter(r=>filter==='alle'||(filter==='medien'?fromMedien(r):filter==='raute'?!fromMedien(r):r.status==='active'));
 const crisis=board?.reaction?.crisis,issues=board?.reaction?.issues||[];
 return <section className="themen-page">
  <PageHeading eyebrow={board?.client.name} title="Themen" description="Aus Medien übernommen oder von RAUTE vorgeschlagen. Vom ersten Anlass bis zum Ergebnis bleibt alles am Thema.">
   <div className="themen-head-acts">
    <a className={`btn${crisis?' btn--alert':' btn--quiet'}`} href={crisis?crisis.href:`/client/${clientId}/issues`}>{crisis?'Krise offen':`Issues & Krisen${issues.length?` · ${issues.length}`:' · keine aktiv'}`}</a>
    <button type="button" className="btn" aria-expanded={developing} onClick={()=>setDeveloping(!developing)}>+ Eigenes Thema</button>
   </div>
  </PageHeading>
  {error&&<p className="twin-error" role="alert">{error}</p>}
  {(developing||running)&&<form className="themen-develop" onSubmit={develop}>
   <label>Welches Thema soll {board?.client.name||'der Kunde'} besetzen?<input aria-label="Recherchefokus" required minLength={3} maxLength={300} value={focus} onChange={e=>setFocus(e.target.value)} disabled={running}/></label>
   <button className="btn btn--go" disabled={running}>{running?'RAUTE recherchiert und entwickelt…':'Thema entwickeln lassen'}</button>
   {board?.development&&!running&&board.development.note&&<p role="status">{board.development.note}</p>}
  </form>}
  {!board&&!error&&<p role="status">Themen werden geladen…</p>}
  {board&&<div className="themen-layout">
   <main>
    <p className="themen-hint">RAUTE schlägt Themen aus den Meldungen der letzten vier Wochen vor.</p>
    {suggestion?.note&&<p role={suggestion.status==='failed'?'alert':'status'}>{suggestion.note}</p>}
    <div className="themen-filters" role="group" aria-label="Themen filtern">{FILTERS.map(([key,label])=><button key={key} type="button" aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label} · {counts[key]}</button>)}</div>
    {shown.length?shown.map(row=><Card key={`${row.context_kind}-${row.context_id}`} clientId={clientId} clientName={board.client.name} row={row} onChanged={next=>setBoard(current=>({...current,opportunities:current.opportunities.map(item=>item.context_kind===row.context_kind&&item.context_id===row.context_id?{...item,status:next.status,workflow_summary:next.workflow_summary}:item)}))}/>)
     :<p className="themen-empty">{filter==='medien'?'Noch nichts aus Medien übernommen. Unter Medien macht der Stern einen Artikel zum Thema.':'Gerade kein offenes Thema.'}</p>}
    <p className="themen-hint"><a href={`/client/${clientId}/medien`}>Weitere Themen in Medien finden →</a></p>
   </main>
   <Agenda key={`${clientId}-${suggestion?.checked_at}-${suggestion?.status}`} clientId={clientId}/>
  </div>}
 </section>;
}
