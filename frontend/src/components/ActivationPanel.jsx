import React,{useEffect,useState} from 'react';
import {journalistRequest as request} from '../journalists-api.js';

function EvidenceReview({text}){
 const [open,setOpen]=useState(false);
 const quality=text.quality;
 return <div className="asset-evidence"><p><strong>{text.quality_stale?'Prüfung veraltet oder ausstehend':quality.status==='complete'?`${quality.warnings} Aussagen mit Prüfhinweisen`:'Text ist ungeprüft'}</strong></p>
  {text.quality_stale&&<p>Text oder Kontext wurden geändert. Vor Verwendung erneut prüfen.</p>}
  {quality.checked_at&&<p>Geprüft am {new Date(quality.checked_at).toLocaleString('de-DE')}</p>}
  <p>{quality.note || 'Noch keine abgeschlossene Aussagenprüfung.'}</p>
  {quality.findings?.length>0&&<><button className="btn" onClick={()=>setOpen(!open)} aria-expanded={open}>{open?'Prüfung schließen':'Aussage für Aussage prüfen'}</button>
   {open&&<ol>{quality.findings.map((f,i)=><li key={i}><blockquote>{f.quote}</blockquote><strong>{f.classification}</strong><p>{f.reason}</p>
    {f.warnings.length>0&&<ul>{f.warnings.map((warning,j)=><li key={j}>{warning}</li>)}</ul>}
    {f.statement_ids.map(id=>{const source=text.evidence_statements.find(r=>r.id===id);return source&&<p key={id}>Twin: {source.value} · {source.evidence_type} · {source.source_title||'Quelle nicht benannt'}{source.source_url&&<> · <a href={source.source_url} target="_blank" rel="noreferrer">Quelle öffnen</a></>}</p>;})}
    {f.source_ids.map(id=>{const source=text.evidence_sources[id];return source&&<p key={id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> · {source.source} · {source.published_at?.slice(0,10)}</p>;})}
    {f.contradiction_ids.map(id=>{const source=text.evidence_statements.find(r=>r.id===id);return source&&<p key={id}>Widerspruch prüfen gegen: {source.value} · {source.source_title||'Quelle nicht benannt'}</p>;})}
    {f.no_go_rules.map((rule,j)=><p key={j}>No-Go im Guide: {rule}</p>)}
   </li>)}</ol>}</>}
 </div>;
}
function TextEditor({text,clientId,path,onSaved,onCheck,busy}){
 const [title,setTitle]=useState(text.title),[body,setBody]=useState(text.body),[error,setError]=useState(''),[saving,setSaving]=useState(false),[notice,setNotice]=useState('');
 async function save(event){event.preventDefault();setSaving(true);setError('');try{onSaved(await request(`${path}/${text.type}/${text.id}`,{method:'PUT',body:JSON.stringify({digest:text.digest,title,body})}));}catch(e){setError(e.message);}finally{setSaving(false);}}
 async function copy(){try{await navigator.clipboard.writeText(`${title}\n\n${body}`);setNotice('Text kopiert.');}catch{setNotice('Bitte den Text im Feld markieren und kopieren.');}}
 return <article className="activation-text"><h3>{text.title||text.kind}</h3><p>{text.released_at?'Freigegeben':'Entwurf'} · {text.kind}</p>
  {error&&<p className="twin-error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <div className="asset-review-layout"><form onSubmit={save}><label>Betreff / Titel<input aria-label={`Titel ${text.id}`} value={title} onChange={e=>setTitle(e.target.value)} disabled={Boolean(text.released_at)}/></label>
   <label>Text<textarea aria-label={`Text ${text.id}`} value={body} onChange={e=>setBody(e.target.value)} disabled={Boolean(text.released_at)} rows={12}/></label>
   <div className="twin-toolbar">{!text.released_at&&<button className="btn btn--go" disabled={saving||busy||title===text.title&&body===text.body}>Änderungen speichern</button>}
    {!text.released_at&&<button type="button" className="btn" disabled={busy||title!==text.title||body!==text.body} onClick={()=>onCheck(text)}>Aussagen prüfen</button>}
    {text.type==='outreach'&&<a className="btn" href={text.href}>Kundenfreigabe und Versand öffnen</a>}<details className="quiet-actions"><summary>Weitere Textaktionen</summary><div className="quiet-actions-body">    <a className="btn" href={`/ask?scope=asset&client_id=${clientId}&asset_type=${text.type}&asset_id=${text.id}`}>Ask RAUTE zum gespeicherten Text</a>
    <button type="button" className="btn" onClick={copy}>Text kopieren</button>
</div></details></div>
  </form><aside aria-label="Belegprüfung"><h3>Qualität & Belege</h3><EvidenceReview text={{...text,quality_stale:text.quality_stale||title!==text.title||body!==text.body}}/></aside></div>
 </article>;
}
export function ActivationPanel({clientId,kind,identity,contacts=[],onCompleted}){
 const path=`clients/${clientId}/opportunities/${kind}/${identity}/activation`;
 const [selectedText,setSelectedText]=useState(()=>new URLSearchParams(window.location.search).get('text')||'');
 const [data,setData]=useState(null),[format,setFormat]=useState('kundenmail'),[contact,setContact]=useState(''),[instruction,setInstruction]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;request(path).then(v=>{if(active)setData(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[path]);
 const running=data?.latest?.status==='running'&&Date.now()-new Date(data.latest.started_at).getTime()<1200000;
 useEffect(()=>{if(!running)return;let active=true;const timer=setInterval(()=>request(path).then(v=>{if(active){setData(v);if(v.latest?.status!=='running')onCompleted?.();}}).catch(e=>{if(active)setError(e.message);}),2500);return()=>{active=false;clearInterval(timer);};},[path,running]);
 async function generate(event){event.preventDefault();setBusy(true);setError('');try{const job=await request(path,{method:'POST',body:JSON.stringify({kind:format,contact_id:needsContact&&contact?Number(contact):null,instruction})});setData(v=>({...v,latest:{...job,kind:format,started_at:new Date().toISOString()}}));}catch(e){setError(e.message);}finally{setBusy(false);}}
 async function check(text){setBusy(true);setError('');try{const job=await request(`${path}/${text.type}/${text.id}/check`,{method:'POST'});setData(v=>({...v,latest:{...job,started_at:new Date().toISOString()}}));}catch(e){setError(e.message);}finally{setBusy(false);}}
 const needsContact=['pitch','interviewangebot','interview_briefing'].includes(format);
 const visibleText=data?.texts.find(text=>selectedText===`${text.type}-${text.id}`)||data?.texts[0];
 const visibleTextKey=visibleText?`${visibleText.type}-${visibleText.id}`:'';
 return <section className="twin-field"><p className="twin-eyebrow">Activation</p><h2>Mit der Kundenmail beginnen</h2><p>Die Chance erklären, einen Vorschlag machen und Freigabe einholen. Danach können Sie weitere Texte aus derselben Gelegenheit erstellen.</p>
  {error&&<p className="twin-error" role="alert">{error}</p>}
  {data&&<><details open={!data.texts.length}><summary>Weiteren Text erstellen</summary><form onSubmit={generate}><label>Format<select aria-label="Format" value={format} onChange={e=>setFormat(e.target.value)}>{data.formats.map(f=><option key={f.key} value={f.key}>{f.label}</option>)}</select></label>
   {needsContact&&<label>Journalist für diesen Text<select aria-label="Journalist für diesen Text" required value={contact} onChange={e=>setContact(e.target.value)}><option value="">Bitte wählen</option>{contacts.map(c=><option key={c.id} value={c.id}>{c.name} · {c.outlet}</option>)}</select></label>}
   <label>{format==='custom'?'Ihr Auftrag':'Ergänzender Auftrag (optional)'}<textarea aria-label="Ergänzender Auftrag" required={format==='custom'} value={instruction} onChange={e=>setInstruction(e.target.value)}/></label>
   <button className="btn btn--go" disabled={busy||running}>{running?'Text und Prüfung in Arbeit…':'Entwurf erstellen'}</button></form></details>
   {data.latest&&<p role="status">{data.latest.status==='running'?'In Arbeit':data.latest.status==='complete'?'Arbeitsschritt abgeschlossen':data.latest.status==='stale'?'Prüfung veraltet':'Arbeitsschritt fehlgeschlagen'}{data.latest.note&&` · ${data.latest.note}`}</p>}
   {data.texts.length>1&&<label>Gespeicherter Text<select aria-label="Gespeicherter Text" value={visibleTextKey} onChange={e=>setSelectedText(e.target.value)}>{data.texts.map(text=><option key={`${text.type}-${text.id}`} value={`${text.type}-${text.id}`}>{text.title||text.kind} · {text.released_at?'Freigegeben':'Entwurf'}</option>)}</select></label>}
   {data.texts.map(text=><div key={`${text.type}-${text.id}`} hidden={visibleTextKey!==`${text.type}-${text.id}`}><TextEditor clientId={clientId} key={`${text.type}-${text.id}-${text.digest}`} text={text} path={path} busy={busy||running} onSaved={value=>{setData(value);onCompleted?.();}} onCheck={check}/></div>)}
  </>}
 </section>;
}
