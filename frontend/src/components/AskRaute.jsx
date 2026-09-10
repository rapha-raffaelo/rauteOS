import React, {useEffect, useRef, useState} from 'react';

export function askHref(context) {return `/ask?${new URLSearchParams(context)}`;}
const names={global:'Gesamtes Portfolio',client:'Mandant',opportunity:'Opportunity',asset:'Gespeicherter Text'};
const suggestions={global:['Wo fehlen Leistungen?', 'Welche Opportunities verdienen Aufmerksamkeit?'],client:['Wo fehlen Belege im Twin?', 'Welche Story passt zur Positionierung?'],opportunity:['Wie belastbar ist diese Gelegenheit?', 'Welche Storyline und welcher Journalist passen?'],asset:['Schärfe diesen Entwurf.', 'Welche Aussagen brauchen bessere Belege?']};
function promptHistory(turns){let budget=4000;const result=[];for(const turn of turns.slice(-12).reverse()){if(turn.text.length>budget)break;result.unshift(turn);budget-=turn.text.length;}return result;}
function initialContext(){const p=new URLSearchParams(window.location.search);const result=Object.fromEntries(['date','scope','client_id','opportunity_kind','opportunity_id','asset_type','asset_id'].filter(k=>p.has(k)).map(k=>[k,p.get(k)]));return {...result,scope:result.scope||(result.client_id?'client':'global')};}
export function AskRaute(){
 const [context,setContext]=useState(initialContext),[clients,setClients]=useState([]),[turns,setTurns]=useState([]),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState('');
 const stream=useRef(null);const scope=context.scope||(context.client_id?'client':'global');
 const key=`raute:ask:${JSON.stringify(Object.entries(context).sort())}`;
 useEffect(()=>{let live=true;fetch('/api/assistant/clients').then(r=>{if(!r.ok)throw Error();return r.json();}).then(v=>{if(live)setClients(v);}).catch(()=>{if(live)setError('Mandanten konnten nicht geladen werden.');});return()=>{live=false;stream.current?.close();};},[]);
 useEffect(()=>{stream.current?.close();stream.current=null;setBusy(false);setStatus('');setError('');window.history.replaceState({},'',askHref(context));try{const saved=JSON.parse(sessionStorage.getItem(key)||'[]');setTurns(Array.isArray(saved)?saved.filter(v=>v&&['user','assistant'].includes(v.role)&&typeof v.text==='string').slice(-24):[]);}catch{setTurns([]);}},[key]);
 function keep(next){setTurns(next);try{sessionStorage.setItem(key,JSON.stringify(next.slice(-24)));}catch{/* Storage may be unavailable. */}}
 function ask(value){const q=value.trim();if(!q||busy)return;const previous=promptHistory(turns);let next=[...turns,{role:'user',text:q},{role:'assistant',text:''}];setTurns(next);setQuestion('');setBusy(true);setError('');
  const source=new EventSource(`/api/assistant/stream?${new URLSearchParams({...context,q,history:JSON.stringify(previous)})}`);stream.current=source;
  const active=()=>stream.current===source;
  function finish(){source.close();if(active()){stream.current=null;setBusy(false);setStatus('');keep(next);}}
  source.addEventListener('status',e=>{if(active())setStatus(JSON.parse(e.data));});
  source.addEventListener('text',e=>{if(!active())return;next=next.map((v,i)=>i===next.length-1?{...v,text:v.text+JSON.parse(e.data)}:v);setTurns(next);});
  source.addEventListener('done',finish);
  source.addEventListener('error',e=>{if(!active())return;let message='Antwort konnte nicht geladen werden. Kontext prüfen und erneut versuchen.';try{if(e.data)message=JSON.parse(e.data);}catch{}setError(message);finish();});
 }
 return <section className="ask-page"><h1>Ask RAUTE</h1><p>Beratung zum aktuellen Kontext. Vorschläge werden nicht gespeichert, freigegeben oder versendet.</p>
  <p><strong>Kontext: {names[scope]||scope}</strong>{context.client_id&&` · ${clients.find(c=>String(c.id)===context.client_id)?.name||`Mandant ${context.client_id}`}`}{context.opportunity_id&&` · #${context.opportunity_id}`}{context.asset_id&&` · #${context.asset_id}`}</p>
  <label>Kontext wechseln<select value={context.client_id||''} onChange={e=>setContext(e.target.value?{scope:'client',client_id:e.target.value}:{scope:'global'})}><option value="">Gesamtes Portfolio</option>{clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
  <div className="workbench-controls">{(suggestions[scope]||suggestions.global).map(q=><button className="btn" key={q} disabled={busy} onClick={()=>ask(q)}>{q}</button>)}<button className="btn" disabled={busy} onClick={()=>keep([])}>Gespräch löschen</button></div>
  <div className="ask-turns" aria-live="polite">{turns.map((v,i)=><article key={i}><strong>{v.role==='user'?'Du':'RAUTE'}</strong><p>{v.text||'Antwort wird vorbereitet…'}</p></article>)}</div>
  {error&&<p role="alert">{error}</p>}{status&&<p role="status">{status}</p>}
  <form onSubmit={e=>{e.preventDefault();ask(question);}}><label>Frage<textarea value={question} maxLength={500} rows={3} onChange={e=>setQuestion(e.target.value)} required/></label><button className="btn btn--go" disabled={busy}>{busy?'Antwort wird geschrieben…':'Fragen'}</button>{busy&&<button type="button" className="btn" onClick={()=>{stream.current?.close();stream.current=null;setBusy(false);setStatus('Abgebrochen');}}>Abbrechen</button>}</form>
 </section>;
}
