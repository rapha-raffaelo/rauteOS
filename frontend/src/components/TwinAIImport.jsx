import React,{useEffect,useState,useRef} from 'react';
import {twinRequest} from '../twin-api.js';

function AnswerEditor({clientId,previewId,row,disabled,onDirty,onSaved}) {
 const [value,setValue]=useState(row.data.value),[saving,setSaving]=useState(false),[error,setError]=useState('');
 const pending=useRef(false);
 const dirty=value!==row.data.value;
 async function save(){
  if(!dirty||pending.current)return;
  if(!value.trim()){setError('Bitte eine Antwort eintragen oder die Änderung verwerfen.');return;}
  pending.current=true;setSaving(true);setError('');
  try{const updated=await twinRequest(clientId,`/ai-import/${previewId}/answers/${row.index}`,{method:'PATCH',body:JSON.stringify({value,fingerprint:row.fingerprint})});onSaved(updated);setValue(updated.data.value);onDirty(false);}
  catch(e){setError(e.message);}finally{pending.current=false;setSaving(false);}
 }
 return <div className="twin-answer-editor">
  <label>Antwort<textarea aria-label={`Antwort ${row.data.key}`} rows={Math.min(8,Math.max(3,Math.ceil(value.length/110)))} maxLength={20000} value={value} disabled={disabled||saving} onChange={e=>{setValue(e.target.value);onDirty(e.target.value!==row.data.value);}} onBlur={save}/></label>
  <div className="twin-toolbar"><small role="status">{saving?'Wird gespeichert…':dirty?'Ungespeicherte Änderung':row.edited_at?'Änderung gespeichert':'Direkt bearbeitbar · wird beim Verlassen des Feldes gespeichert'}</small>
   {dirty&&<><button className="btn btn--quiet" disabled={disabled||saving} onClick={save}>Änderung speichern</button><button className="btn btn--quiet" disabled={disabled||saving} onMouseDown={e=>e.preventDefault()} onClick={()=>{setValue(row.data.value);setError('');onDirty(false);}}>Änderung verwerfen</button></>}
  </div>{error&&<p role="alert">{error}</p>}
  {row.edited_at&&<details><summary>Ursprünglichen KI-Vorschlag ansehen</summary><p>{row.original_value}</p><p>Quellen und KI-Herleitung beziehen sich auf diesen ursprünglichen Vorschlag.</p></details>}
 </div>;
}

export function TwinAIImport({clientId,fields,onImported,onStatus,onRestore}){
 const [text,setText]=useState(''),[title,setTitle]=useState(''),[section,setSection]=useState(''),[web,setWeb]=useState(true);
 const [edits,setEdits]=useState({});
 const hasEdits=Object.values(edits).some(Boolean);
 useEffect(()=>{if(!hasEdits)return;const warn=e=>{e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[hasEdits]);
 const [restoring,setRestoring]=useState(true);
 const previewId=useRef(null), chosenPreview=useRef('');
 const [history,setHistory]=useState([]);
 const statusPath=()=>'/ai-import'+(chosenPreview.current?'?preview_id='+encodeURIComponent(chosenPreview.current):'');
 const [job,setJob]=useState(null),[preview,setPreview]=useState(null),[selected,setSelected]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 function receive(data){setHistory(data.previews||[]);onStatus?.(data);setJob(data.job);if(previewId.current!==data.preview?.id){setSelected([]);setEdits({});previewId.current=data.preview?.id;}setPreview(data.preview);setError('');}
 useEffect(()=>{let active=true;const controller=new AbortController();setRestoring(true);chosenPreview.current='';setJob(null);setPreview(null);setSelected([]);
  twinRequest(clientId,statusPath(),{signal:controller.signal}).then(v=>{if(active){receive(v);onRestore?.(v);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setRestoring(false);});
  return()=>{active=false;controller.abort();};},[clientId]);
 const running=job?.status==='running';
 useEffect(()=>{if(!running)return;let active=true,timer;const controller=new AbortController();
  async function poll(){try{const data=await twinRequest(clientId,statusPath(),{signal:controller.signal});if(active)receive(data);}catch(e){if(active)setError(e.message);}finally{if(active)timer=setTimeout(poll,2500);}}
  timer=setTimeout(poll,2500);return()=>{active=false;clearTimeout(timer);controller.abort();};},[clientId,running]);
 async function start(e){e.preventDefault();if(restoring||busy||running)return;setBusy(true);setError('');try{setJob(await twinRequest(clientId,'/ai-import',{method:'POST',body:JSON.stringify({text,source_title:title,section,web})}));chosenPreview.current='';setSelected([]);}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function choosePreview(id){chosenPreview.current=id;setBusy(true);try{receive(await twinRequest(clientId,statusPath()));}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function resume(){setBusy(true);setError('');try{const next=await twinRequest(clientId,'/ai-import/resume',{method:'POST'});setJob(next);onStatus?.({job:next,preview});}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function commit(){setBusy(true);setError('');try{const result=await twinRequest(clientId,'/import/commit',{method:'POST',body:JSON.stringify({preview_id:preview.id,selected,fingerprints:Object.fromEntries(preview.rows.filter(r=>selected.includes(r.index)).map(r=>[r.index,r.fingerprint]))})});setPreview(null);setSelected([]);setJob(null);onStatus?.({job:null,preview:null});await onImported(result);}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section className="twin-ai-import" aria-label="Mit KI importieren"><header><p className="twin-eyebrow">KI-UNTERSTÜTZTER IMPORT</p><h2>Vorhandenes Wissen in Antworten übersetzen</h2><p>Die KI wertet die Mandantenakte, bestehende Profil-Aussagen, Guide-Dokumente und deine Quellen aus. Sie schlägt Antworten für offene Fragen vor. Bereits beantwortete Felder bleiben erhalten.</p></header>
  <p className="twin-muted">Fertige Fragenpakete werden automatisch gespeichert. Du kannst die Seite verlassen und später hier weiterarbeiten.</p>
  {job?.status==='failed'&&job.resumable&&<button className="btn btn--go" disabled={busy||restoring||hasEdits} onClick={resume}>Gespeicherten Import fortsetzen</button>}
  <details open={!job&&!preview}><summary>Neuen Import vorbereiten</summary><form onSubmit={start}><div className="twin-form-grid"><label>Bereich für den KI-Import<select value={section} onChange={e=>setSection(e.target.value)} disabled={restoring||running||busy||hasEdits}><option value="">Alle offenen Fragen</option>{[...new Set(fields.filter(f=>f.section!=='Profil').map(f=>f.section))].map(s=><option key={s}>{s}</option>)}</select></label><label>Bezeichnung der Quelle (optional)<input value={title} maxLength={300} onChange={e=>setTitle(e.target.value)} disabled={restoring||running||busy||hasEdits} placeholder="Zum Beispiel: Unternehmenspräsentation"/></label></div>
   <label>Quelltext ergänzen (optional)<textarea rows={5} value={text} maxLength={30000} onChange={e=>setText(e.target.value)} disabled={restoring||running||busy||hasEdits} placeholder="Informationen von der Website, aus Präsentationen oder Gesprächsnotizen einfügen …"/></label>
   <label className="twin-ai-check"><input type="checkbox" checked={web} onChange={e=>setWeb(e.target.checked)} disabled={restoring||running||busy||hasEdits}/>Öffentliche Unternehmensinformationen recherchieren</label>
   <p className="twin-muted">Pro Durchgang bis zu 100 Vorschläge. Unbelegte Fragen bleiben offen. Vorschläge sind KI-Ableitungen und benötigen Prüfung sowie eine separate externe Freigabe.</p>
   <button className="btn btn--go" disabled={restoring||running||busy||hasEdits}>{restoring?'Importstatus wird geladen…':running?'KI wertet die Quellen aus…':job?.status==='failed'?'Erneut versuchen':'Antwortvorschläge erstellen'}</button></form></details>
  {error&&<p role="alert" className="twin-error">{error}</p>}{running ? <div className="twin-ai-progress" role="status"><progress aria-label="Fortschritt des KI-Imports" {...(job.total_batches ? {max:job.total_batches+1,value:job.completed_batches||0} : {})}/><p>{job.note}</p></div> : job&&<p role={job.status==='failed'?'alert':'status'} className={job.status==='failed'?'twin-error':undefined}>{job.note}</p>}
  {history.length>1&&<label>Gespeicherte Importläufe<select aria-label="Gespeicherte Importläufe" disabled={busy||hasEdits} value={preview?.id||''} onChange={e=>choosePreview(e.target.value)}>{history.map(h=><option key={h.id} value={h.id}>{new Date(h.created_at).toLocaleString('de-DE')} · {h.count} Vorschläge</option>)}</select></label>}
  {preview&&<div className="twin-ai-preview"><h3>{preview.rows.length} Vorschläge zur Prüfung</h3>{running&&<p>Zwischenstand gespeichert. Weitere Pakete werden noch bearbeitet.</p>}<p>{preview.unanswered} Fragen bleiben in diesem Durchgang offen.</p>{preview.rows.length>0&&<><div className="twin-toolbar"><button className="btn" disabled={busy||running} onClick={()=>setSelected(preview.rows.map(r=>r.index))}>Alle auswählen</button><button className="btn" disabled={busy||running} onClick={()=>setSelected([])}>Auswahl aufheben</button></div>
   {preview.rows.map(row=><article className="twin-ai-answer" key={row.index}><label className="twin-ai-check"><input type="checkbox" disabled={busy||running} checked={selected.includes(row.index)} onChange={e=>setSelected(e.target.checked?[...selected,row.index]:selected.filter(i=>i!==row.index))}/><strong>{row.data.key} · {fields.find(f=>f.key===row.data.key)?.label}</strong></label><AnswerEditor key={`${preview.id}-${row.index}`} clientId={clientId} previewId={preview.id} row={row} disabled={busy||running} onDirty={dirty=>setEdits(v=>({...v,[row.index]:dirty}))} onSaved={updated=>setPreview(p=>({...p,rows:p.rows.map(r=>r.index===updated.index?updated:r)}))}/><div className="twin-badges"><span>{row.edited_at?'Manuell angepasst · ungeprüft':'KI-Ableitung · ungeprüft'}</span><span>{row.data.confidentiality}</span><span>{row.data.external_use}</span></div><p className="twin-muted">{row.message}</p><details><summary>Quellen und Herleitung prüfen</summary>{row.sources.map(s=><div key={s.id}><strong>{s.title}</strong>{s.url&&<> · <a href={s.url} target="_blank" rel="noreferrer">Quelle öffnen</a></>}<p>{s.text}</p></div>)}</details></article>)}
   <button className="btn btn--go" disabled={busy||running||hasEdits||!selected.length} onClick={commit}>{selected.length} geprüfte Antworten übernehmen</button></>}</div>}
 </section>;
}
