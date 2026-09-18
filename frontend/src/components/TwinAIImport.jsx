import React,{useEffect,useState,useRef} from 'react';
import {twinRequest} from '../twin-api.js';

export function TwinAIImport({clientId,fields,onImported}){
 const [text,setText]=useState(''),[title,setTitle]=useState(''),[section,setSection]=useState(''),[web,setWeb]=useState(true);
 const [restoring,setRestoring]=useState(true);
 const previewId=useRef(null);
 const [job,setJob]=useState(null),[preview,setPreview]=useState(null),[selected,setSelected]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 function receive(data){setJob(data.job);if(previewId.current!==data.preview?.id){setSelected([]);previewId.current=data.preview?.id;}setPreview(data.preview);setError('');}
 useEffect(()=>{let active=true;const controller=new AbortController();setRestoring(true);setJob(null);setPreview(null);setSelected([]);
  twinRequest(clientId,'/ai-import',{signal:controller.signal}).then(v=>{if(active)receive(v);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setRestoring(false);});
  return()=>{active=false;controller.abort();};},[clientId]);
 const running=job?.status==='running';
 useEffect(()=>{if(!running)return;let active=true,timer;const controller=new AbortController();
  async function poll(){try{const data=await twinRequest(clientId,'/ai-import',{signal:controller.signal});if(active)receive(data);}catch(e){if(active)setError(e.message);}finally{if(active)timer=setTimeout(poll,2500);}}
  timer=setTimeout(poll,2500);return()=>{active=false;clearTimeout(timer);controller.abort();};},[clientId,running]);
 async function start(e){e.preventDefault();if(restoring||busy||running)return;setBusy(true);setError('');try{setJob(await twinRequest(clientId,'/ai-import',{method:'POST',body:JSON.stringify({text,source_title:title,section,web})}));setPreview(null);setSelected([]);}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function commit(){setBusy(true);setError('');try{const result=await twinRequest(clientId,'/import/commit',{method:'POST',body:JSON.stringify({preview_id:preview.id,selected})});setPreview(null);setSelected([]);setJob(null);await onImported(result);}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section className="twin-ai-import" aria-label="Mit KI importieren"><header><p className="twin-eyebrow">KI-UNTERSTÜTZTER IMPORT</p><h2>Vorhandenes Wissen in Antworten übersetzen</h2><p>Die KI wertet die Mandantenakte, bestehende Profil-Aussagen, Guide-Dokumente und deine Quellen aus. Sie schlägt Antworten für offene Fragen vor. Bereits beantwortete Felder bleiben erhalten.</p></header>
  <form onSubmit={start}><div className="twin-form-grid"><label>Bereich für den KI-Import<select value={section} onChange={e=>setSection(e.target.value)} disabled={restoring||running||busy}><option value="">Alle offenen Fragen</option>{[...new Set(fields.filter(f=>f.section!=='Profil').map(f=>f.section))].map(s=><option key={s}>{s}</option>)}</select></label><label>Bezeichnung der Quelle (optional)<input value={title} maxLength={300} onChange={e=>setTitle(e.target.value)} disabled={restoring||running||busy} placeholder="Zum Beispiel: Unternehmenspräsentation"/></label></div>
   <label>Quelltext ergänzen (optional)<textarea rows={5} value={text} maxLength={30000} onChange={e=>setText(e.target.value)} disabled={restoring||running||busy} placeholder="Informationen von der Website, aus Präsentationen oder Gesprächsnotizen einfügen …"/></label>
   <label className="twin-ai-check"><input type="checkbox" checked={web} onChange={e=>setWeb(e.target.checked)} disabled={restoring||running||busy}/>Öffentliche Unternehmensinformationen recherchieren</label>
   <p className="twin-muted">Pro Durchgang bis zu 100 Vorschläge. Unbelegte Fragen bleiben offen. Vorschläge sind KI-Ableitungen und benötigen Prüfung sowie eine separate externe Freigabe.</p>
   <button className="btn btn--go" disabled={restoring||running||busy}>{restoring?'Importstatus wird geladen…':running?'KI wertet die Quellen aus…':job?.status==='failed'?'Erneut versuchen':'Antwortvorschläge erstellen'}</button></form>
  {error&&<p role="alert" className="twin-error">{error}</p>}{running ? <div className="twin-ai-progress" role="status"><progress aria-label="Fortschritt des KI-Imports" {...(job.total_batches ? {max:job.total_batches+1,value:job.completed_batches||0} : {})}/><p>{job.note}</p></div> : job&&<p role={job.status==='failed'?'alert':'status'} className={job.status==='failed'?'twin-error':undefined}>{job.note}</p>}
  {preview&&<div className="twin-ai-preview"><h3>{preview.rows.length} Vorschläge zur Prüfung</h3><p>{preview.unanswered} Fragen bleiben in diesem Durchgang offen.</p>{preview.rows.length>0&&<><div className="twin-toolbar"><button className="btn" disabled={busy} onClick={()=>setSelected(preview.rows.map(r=>r.index))}>Alle auswählen</button><button className="btn" disabled={busy} onClick={()=>setSelected([])}>Auswahl aufheben</button></div>
   {preview.rows.map(row=><article className="twin-ai-answer" key={row.index}><label className="twin-ai-check"><input type="checkbox" disabled={busy} checked={selected.includes(row.index)} onChange={e=>setSelected(e.target.checked?[...selected,row.index]:selected.filter(i=>i!==row.index))}/><strong>{row.data.key} · {fields.find(f=>f.key===row.data.key)?.label}</strong></label><p className="twin-value">{row.data.value}</p><div className="twin-badges"><span>KI-Ableitung · ungeprüft</span><span>{row.data.confidentiality}</span><span>{row.data.external_use}</span></div><p className="twin-muted">{row.message}</p><details><summary>Quellen und Herleitung prüfen</summary>{row.sources.map(s=><div key={s.id}><strong>{s.title}</strong>{s.url&&<> · <a href={s.url} target="_blank" rel="noreferrer">Quelle öffnen</a></>}<p>{s.text}</p></div>)}</details></article>)}
   <button className="btn btn--go" disabled={busy||!selected.length} onClick={commit}>{selected.length} geprüfte Antworten übernehmen</button></>}</div>}
 </section>;
}
