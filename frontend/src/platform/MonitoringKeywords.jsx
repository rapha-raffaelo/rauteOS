import React, {useEffect,useState} from 'react';
export function MonitoringKeywords({clientId}) {
 const [draft,setDraft]=useState(null),[draftRevision,setDraftRevision]=useState(null);
 const base=`/api/v1/clients/${clientId}/keywords`;
 const [data,setData]=useState(null),[options,setOptions]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[term,setTerm]=useState(''),[saved,setSaved]=useState(false);
 async function request(path='',method='GET',body){
  const r=await fetch(base+path,{method,headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Suchbegriffe konnten nicht gespeichert werden.');return d;
 }
 function apply(d){setData(d);setOptions(old=>[...new Set([...old,...d.keywords,...(d.suggestions||[]).map(p=>p.term)])]);}
 useEffect(()=>{let active=true,timer;async function load(){try{const d=await request();if(active){apply(d);if(d.state==='läuft')timer=setTimeout(load,3000);}}catch(e){if(active)setError(e.message);}}load();return()=>{active=false;clearTimeout(timer);};},[clientId,data?.state==='läuft']);
 const selected=draft??data?.keywords??[];
 const dirty=!!data&&draft!==null&&(draft.length!==data.keywords.length||draft.some(k=>!data.keywords.includes(k)));
 function toggle(value){
  if(draft===null)setDraftRevision(data.revision);
  setOptions(old=>old.includes(value)?old:[...old,value]);
  setDraft(selected.includes(value)?selected.filter(k=>k!==value):[...selected,value]);setSaved(false);setTerm('');
 }
 async function save(){
  setBusy(true);setError('');setSaved(false);
  try{const next=await request('','PUT',{keywords:selected,revision:draftRevision});setOptions(old=>old.filter(k=>!data.keywords.includes(k)||selected.includes(k)));apply(next);setDraft(null);setDraftRevision(null);setSaved(true);setTerm('');}
  catch(e){setError(e.message);}finally{setBusy(false);}
 }
 async function suggest(){setBusy(true);setError('');try{await request('/suggest','POST');setData(d=>({...d,state:'läuft'}));}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section className="profile-section monitoring-keywords" aria-labelledby={`keywords-${clientId}`}>
  <header className="onb-head"><div><h2 id={`keywords-${clientId}`}>Keywords für die News-Suche</h2><p>Aktive Begriffe steuern Themen-Radar und tägliche KI-Recherche. Auswahl ändern und anschließend speichern.</p></div></header>
  {!data&&!error&&<p role="status">Suchbegriffe werden geladen …</p>}
  {data&&<><div className="keyword-chips" role="group" aria-label="Suchbegriffe auswählen">{options.map(value=>{
   const p=data.suggestions?.find(p=>p.term===value),active=selected.includes(value);
   return <button type="button" key={value} className={`keyword-chip${active?' is-active':''}`} aria-pressed={active} disabled={busy} onClick={()=>toggle(value)} title={p?`${p.reason} · ${p.external} Marktmeldungen in 90 Tagen`:undefined}>{active?'✓ ':'+ '}{value}{p&&<small>{p.external} Treffer / 90 Tage</small>}</button>;
  })}</div>
  {!selected.length&&<p>Keine Themen-Keywords aktiv. Die Suche nach dem Unternehmensnamen bleibt aktiv.</p>}
  <form className="keyword-add" onSubmit={e=>{e.preventDefault();const value=term.trim();if(value&&!selected.includes(value))toggle(value);}}><input aria-label="Eigenes Keyword" placeholder="Eigenes Keyword ergänzen" value={term} maxLength={100} onChange={e=>setTerm(e.target.value)}/><button className="btn" disabled={busy||!term.trim()} aria-label="Keyword hinzufügen">+</button><button type="button" className="btn" disabled={busy||dirty||data.state==='läuft'} onClick={suggest}>{data.state==='läuft'?'KI recherchiert …':'KI-Vorschläge aus dem Profil'}</button></form>
  {dirty&&<div className="keyword-save"><button type="button" className="btn btn--go" aria-label="Keywords speichern" title="Keywords speichern" disabled={busy} onClick={save}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 3h13l4 4v14H3V3zM7 3v6h10V3M7 21v-8h10v8"/></svg></button><span>Ungespeicherte Änderungen</span><button type="button" className="btn" disabled={busy} onClick={()=>{setDraft(null);setDraftRevision(null);}}>Verwerfen</button></div>}
  <p className="onb-meta">KI-Vorschläge werden erst nach Auswahl und Speichern aktiv. Trefferzahlen beziehen sich auf die letzten 90 Tage.</p>
  {saved&&<p role="status">Gespeichert. Gilt ab der nächsten Suche.</p>}{data.error&&<p role="alert">{data.error}</p>}
  </>}{error&&<p role="alert">{error}</p>}
 </section>;
}
