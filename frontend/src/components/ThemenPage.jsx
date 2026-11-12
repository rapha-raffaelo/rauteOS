import React,{useEffect,useRef,useState} from 'react';
import {PageHeading} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';

// Spec 12: what could become communication, from a starred article ("Aus
// Medien") or a proposal by RAUTE. The Deep Dive opens on hover or focus;
// "Thema aktivieren" moves the Thema to Assets, where it is written.
const day=value=>value?new Date(value).toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'}):'';
const MONTHS=['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
const FILTERS=[['alle','Alle'],['medien','★ Aus Medien'],['raute','Vorschläge von RAUTE'],['aktiv','Aktiviert']];
export const fromMedien=row=>row.origin==='medien';
const ORIGIN={anlass:'Anlass aus dem Radar',pitch:'Themen-Pitch',plan:'Aus der Agenda',medien:'★ Aus Medien'};

// The pitch is the line the Thema would be argued with: the chosen storyline,
// else RAUTE's first one, else its summary.
export const pitchOf=detail=>(detail?.storyline||detail?.storylines?.[0]||'').trim();

function DeepDive({clientId,clientName,row,id}){
 const [detail,setDetail]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;request(`clients/${clientId}/opportunities/${row.context_kind}/${row.context_id}`)
  .then(v=>{if(active)setDetail(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[clientId,row.context_kind,row.context_id]);
 const missing=<em>bitte ergänzen</em>;
 return <div className="themen-dive" id={id} role="tooltip">
  {error?<p role="alert">{error}</p>:!detail?<p role="status">Deep Dive wird geladen…</p>:<>
   {detail.deep_dive==='pending'&&<p role="status" className="themen-dive__note">RAUTE schreibt den Deep Dive. Bis dahin steht hier der Artikel.</p>}
   {detail.deep_dive==='failed'&&<p className="themen-dive__note">Der Deep Dive ließ sich nicht schreiben. Pitch beim Aktivieren selbst formulieren.</p>}
   <section><h4>Was ist passiert?</h4><p>{detail.situation?.trim()||missing}</p></section>
   <section><h4>Warum für {clientName||'den Kunden'} relevant?</h4><p>{detail.relevance?.trim()||missing}</p></section>
   <section className="themen-dive__pitch"><h4>Pitch</h4><p>{pitchOf(detail)||row.summary||missing}</p></section>
   <section><h4>Passende Ansprechpartner</h4>
    {detail.recipients?.length?<ul>{detail.recipients.slice(0,3).map(r=><li key={`${r.name}-${r.outlet}`}>{r.name}{r.outlet&&` · ${r.outlet}`}{r.reason&&<small> · {r.reason}</small>}</li>)}</ul>
     :detail.speaker_proposal?<p>Sprecher: {detail.people.find(p=>p.id===detail.speaker_proposal.person_id)?.label}</p>:<p>{missing}</p>}
   </section></>}
 </div>;
}

function Card({clientId,clientName,row,onActivate,busy}){
 const [open,setOpen]=useState(false);const id=`dive-${row.context_kind}-${row.context_id}`;
 const timer=useRef(null);
 const show=()=>{clearTimeout(timer.current);setOpen(true);};
 const hide=()=>{timer.current=setTimeout(()=>setOpen(false),150);};
 const o=row.occasion;
 return <article className={`themen-card${row.status==='active'?' themen-card--active':''}`}>
  <div className="themen-card__meta"><span className={`themen-tag${fromMedien(row)?' themen-tag--star':''}`}>{ORIGIN[row.origin]||'Vorschlag von RAUTE'}{row.starred_by&&` · @${row.starred_by}`}</span>
   {row.status==='active'&&<span className="themen-tag themen-tag--on">Aktiviert</span>}
   {o&&<span className="themen-card__source">{o.source}{o.published_at&&` · ${day(o.published_at)}`}</span>}</div>
  <h2>{row.title}</h2>
  <div className="themen-card__acts" onMouseLeave={hide}>
   <button type="button" className="btn btn--quiet themen-dive-trigger" aria-expanded={open} aria-describedby={open?id:undefined}
    onMouseEnter={show} onFocus={show} onBlur={hide} onClick={()=>setOpen(!open)}>Deep Dive</button>
   {open&&<div onMouseEnter={show}><DeepDive clientId={clientId} clientName={clientName} row={row} id={id}/></div>}
   {row.status==='active'?<a className="btn" href={`/client/${clientId}/assets?kind=${row.context_kind}&context=${row.context_id}`}>Zu den Assets →</a>
    :<button type="button" className="btn btn--go" disabled={busy} onClick={()=>onActivate(row)}>Thema aktivieren</button>}
  </div>
 </article>;
}

export function Agenda({clientId}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{request(`clients/${clientId}/agenda`).then(setData).catch(e=>setError(e.message));},[clientId]);
 const when=item=>item.day?`${String(item.day).padStart(2,'0')}.${item.month.slice(5)}.`:MONTHS[Number(item.month.slice(5))-1];
 return <aside className="themen-agenda" aria-labelledby="agenda-title">
  <header><h2 id="agenda-title">Agenda</h2><a href={data?.href||`/client/${clientId}/plan`}>Ganze Agenda →</a></header>
  {error&&<p role="alert">{error}</p>}
  {data&&!data.items.length&&<p className="themen-empty">Noch keine Termine. Die Agenda füllt sich aus Marktsignalen und Themen.</p>}
  {data?.items.length>0&&<ol className="themen-timeline">{data.items.map(item=><li key={item.id} tabIndex={0} className={`themen-timeline__item themen-timeline__item--${item.state}`}>
   <span className="themen-timeline__dot" aria-hidden="true"/>
   <div><span className="themen-timeline__when">{when(item)}</span><a href={item.href}>{item.title||'Ohne Titel'}</a>
    <span className="themen-timeline__state">{item.state==='angenommen'?'geplant':'Vorschlag'}{item.format&&` · ${item.format}`}</span></div>
   {item.reason&&<div className="themen-timeline__pop" role="tooltip"><strong>{item.title}</strong><p>{item.reason}</p></div>}
  </li>)}</ol>}
  <a className="btn btn--quiet themen-agenda__add" href={`/client/${clientId}/plan#agenda`}>Agenda bearbeiten</a>
 </aside>;
}

export function ThemenPage({clientId}){
 const [board,setBoard]=useState(null),[error,setError]=useState(''),[filter,setFilter]=useState('alle'),[busy,setBusy]=useState(false);
 const [developing,setDeveloping]=useState(false),[focus,setFocus]=useState('');
 const path=`clients/${clientId}/opportunities`;
 useEffect(()=>{let active=true;request(path).then(v=>{if(active)setBoard(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
 const running=board?.development?.status==='running'&&Date.now()-new Date(board.development.started_at).getTime()<1200000;
 useEffect(()=>{if(!running)return;const timer=setInterval(()=>request(path).then(setBoard).catch(e=>setError(e.message)),2500);return()=>clearInterval(timer);},[path,running]);
 async function activate(row){
  setBusy(true);setError('');
  try{
   const base=`${path}/${row.context_kind}/${row.context_id}`;
   const detail=await request(base);
   const storyline=pitchOf(detail)||(row.summary||'').trim();
   if(!storyline)throw new Error('Für dieses Thema fehlt noch ein Pitch. Bitte im Deep Dive ergänzen.');
   await request(`${base}/activate`,{method:'POST',body:JSON.stringify({revision:detail.revision,storyline,
    speaker_statement_id:detail.speaker_statement_id,speaker_person_id:detail.speaker_person_id||detail.speaker_proposal?.person_id||null,
    contact_ids:detail.contact_ids})});
   window.location.assign(`/client/${clientId}/assets?kind=${row.context_kind}&context=${row.context_id}`);
  }catch(e){setError(e.message);setBusy(false);}
 }
 async function develop(event){event.preventDefault();setError('');try{const job=await request(path+'/develop',{method:'POST',body:JSON.stringify({focus})});setBoard(v=>({...v,development:job}));setFocus('');}catch(e){setError(e.message);}}
 const open=(board?.opportunities||[]).filter(row=>row.status!=='closed');
 const counts={alle:open.length,medien:open.filter(fromMedien).length,raute:open.filter(r=>!fromMedien(r)).length,aktiv:open.filter(r=>r.status==='active').length};
 const shown=open.filter(r=>filter==='alle'||(filter==='medien'?fromMedien(r):filter==='raute'?!fromMedien(r):r.status==='active'));
 const crisis=board?.reaction?.crisis,issues=board?.reaction?.issues||[];
 return <section className="themen-page">
  <PageHeading eyebrow={board?.client.name} title="Themen" description="Aus Medien übernommen oder von RAUTE vorgeschlagen. Ein aktiviertes Thema wird unter Assets ausgearbeitet.">
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
    <div className="themen-filters" role="group" aria-label="Themen filtern">{FILTERS.map(([key,label])=><button key={key} type="button" aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label} · {counts[key]}</button>)}</div>
    {shown.length?shown.map(row=><Card key={`${row.context_kind}-${row.context_id}`} clientId={clientId} clientName={board.client.name} row={row} busy={busy} onActivate={activate}/>)
     :<p className="themen-empty">{filter==='medien'?'Noch nichts aus Medien übernommen. Unter Medien macht der Stern einen Artikel zum Thema.':'Gerade kein offenes Thema.'}</p>}
    <p className="themen-hint"><a href={`/client/${clientId}/medien`}>Weitere Themen in Medien finden →</a></p>
   </main>
   <Agenda clientId={clientId}/>
  </div>}
 </section>;
}
