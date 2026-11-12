import React,{useEffect,useRef,useState} from 'react';
import {PageHeading} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';
import {EvidenceReview} from './ActivationPanel.jsx';

// Spec 12: an activated Thema is written here. RAUTE drafts each asset from
// Thema, pitch and profile; the text is edited in place. Sending comes later.
export const KINDS=[['kundenmail','Kundenmail','Abstimmung mit dem Kunden'],['statement','Statement','Zitierfähige Position'],
 ['pressemitteilung','Pressemitteilung','Mit Kunden-Logo'],['gastbeitrag','Gastbeitrag','Für ein Fachmedium'],
 ['pitch','Pitch','An eine:n Journalist:in'],['custom','Custom','Eigene Vorgabe, eigenes Format']];
const LABEL=Object.fromEntries(KINDS.map(([k,l])=>[k,l]));
const NEEDS_CONTACT=new Set(['pitch']);
const speakerValue=d=>d.speaker_person_id?`p:${d.speaker_person_id}`:'';

// Export one asset or a whole Thema: as Word or PDF, downloaded or put into
// the shared Drive folder "7. Assets" under the client's own sub-folder.
export function ExportBox({base,label='Exportieren'}){
 const [open,setOpen]=useState(false),[format,setFormat]=useState('docx'),[busy,setBusy]=useState(false),[result,setResult]=useState(null),[error,setError]=useState('');
 async function drive(){setBusy(true);setError('');setResult(null);
  try{setResult(await request(base.replace('/api/v1/','')+'/drive',{method:'POST',body:JSON.stringify({format})}));}
  catch(e){setError(e.message);}finally{setBusy(false);}}
 return <div className="asset-export">
  <button type="button" className="btn btn--quiet" aria-expanded={open} onClick={()=>setOpen(!open)}>{label}</button>
  {open&&<div className="asset-export__panel" role="group" aria-label={label}>
   <fieldset><legend>Format</legend>
    <label><input type="radio" name={`fmt-${base}`} checked={format==='docx'} onChange={()=>setFormat('docx')}/> Word (.docx)</label>
    <label><input type="radio" name={`fmt-${base}`} checked={format==='pdf'} onChange={()=>setFormat('pdf')}/> PDF</label>
   </fieldset>
   <div className="asset-export__acts">
    <a className="btn btn--quiet" href={`${base}/export.${format}`} download>Herunterladen</a>
    <button type="button" className="btn" disabled={busy} onClick={drive}>{busy?'Wird abgelegt…':'In Drive ablegen'}</button>
   </div>
   {result&&<p role="status">Abgelegt in {result.folder}. <a href={result.url} target="_blank" rel="noreferrer">In Drive öffnen ↗</a></p>}
   {error&&<p className="twin-error" role="alert">{error}{/verbunden|Einstellungen/.test(error)&&<> <a href="/settings#drive">Drive verbinden</a></>}</p>}
  </div>}
 </div>;
}

export function Editor({text,path,onSaved,exportBase,onCheck,checking=false}){
 const [title,setTitle]=useState(text.title),[body,setBody]=useState(text.body);
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[saving,setSaving]=useState(false);
 const dirty=title!==text.title||body!==text.body;
 const released=Boolean(text.released_at);
 async function save(){setSaving(true);setError('');setNotice('');try{onSaved(await request(`${path}/${text.type}/${text.id}`,{method:'PUT',body:JSON.stringify({digest:text.digest,title,body})}));setNotice('Gespeichert.');}catch(e){setError(e.message);}finally{setSaving(false);}}
 async function copy(){try{await navigator.clipboard.writeText(title?`${title}\n\n${body}`:body);setNotice('Text kopiert.');}catch{setNotice('Bitte den Text im Feld markieren und kopieren.');}}
 return <article className="asset-editor" aria-label={`${LABEL[text.kind]||text.kind} bearbeiten`}>
  <header className="asset-editor__bar">
   <div><h2>{LABEL[text.kind]||text.kind_label||text.kind}</h2>
    <span className={`themen-tag${released?' themen-tag--on':' themen-tag--star'}`}>{released?'Freigegeben':dirty?'Ungespeicherte Änderungen':'Entwurf'}</span></div>
   <div className="asset-editor__acts">
    {exportBase&&<ExportBox base={exportBase}/>}
    {!released&&onCheck&&<button type="button" className="btn btn--quiet" disabled={dirty||checking} title={dirty?'Erst speichern, dann prüfen':''} onClick={()=>onCheck(text)}>{checking?'Wird geprüft…':'Aussagen prüfen'}</button>}
    <button type="button" className="btn btn--quiet" onClick={copy}>Kopieren</button>
    <button type="button" className="btn" disabled title="Kommt später">Senden · bald</button>
    <button type="button" className="btn btn--go" disabled={released||!dirty||saving} onClick={save}>{saving?'Wird gespeichert…':'Speichern'}</button>
   </div>
  </header>
  {error&&<p className="twin-error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <div className="asset-editor__sheet">
   <label>Betreff oder Titel<input aria-label="Titel" value={title} onChange={e=>setTitle(e.target.value)} disabled={released}/></label>
   <label>Text<textarea aria-label="Text" value={body} onChange={e=>setBody(e.target.value)} disabled={released} rows={18}/></label>
  </div>
  {text.quality&&<aside className="asset-editor__evidence" aria-label="Belegprüfung"><EvidenceReview text={{...text,quality_stale:text.quality_stale||dirty}}/></aside>}
 </article>;
}

function NewAsset({detail,running,onCreate}){
 const [kind,setKind]=useState(''),[contact,setContact]=useState(''),[instruction,setInstruction]=useState('');
 const needsContact=NEEDS_CONTACT.has(kind);
 return <section className="asset-new" aria-labelledby="asset-new-title">
  <h2 id="asset-new-title">Neues Asset</h2>
  <p>RAUTE schreibt einen Entwurf aus Thema, Pitch und Kundenprofil. Du bearbeitest ihn direkt im Fenster.</p>
  <div className="asset-kinds" role="group" aria-label="Asset wählen">{KINDS.map(([key,label,note])=>
   <button key={key} type="button" className={`asset-kind${key==='custom'?' asset-kind--custom':''}`} aria-pressed={kind===key} disabled={running} onClick={()=>setKind(key)}>
    <strong>{label}</strong><span>{note}</span></button>)}</div>
  {kind&&<form className="asset-new__form" onSubmit={e=>{e.preventDefault();onCreate({kind,contact_id:needsContact&&contact?Number(contact):null,instruction});}}>
   {needsContact&&<label>Journalist:in<select aria-label="Journalist:in" required value={contact} onChange={e=>setContact(e.target.value)}>
    <option value="">Bitte wählen</option>{detail.contacts.map(c=><option key={c.id} value={c.id}>{c.name}{c.outlet?` · ${c.outlet}`:''}</option>)}</select></label>}
   <label>{kind==='custom'?'Dein Auftrag':'Zusätzlicher Auftrag (optional)'}<textarea aria-label="Auftrag" required={kind==='custom'} value={instruction} onChange={e=>setInstruction(e.target.value)}
    placeholder={kind==='custom'?'Was soll der Text sagen, und für wen?':'Zum Beispiel: kürzer, mit Fokus auf Apotheken'}/></label>
   <button className="btn btn--go" disabled={running||(needsContact&&!contact)}>{running?'RAUTE schreibt…':`${LABEL[kind]} schreiben lassen`}</button>
  </form>}
 </section>;
}

export function AssetsPage({clientId,params=new URLSearchParams(window.location.search)}){
 const [board,setBoard]=useState(null),[error,setError]=useState('');
 const [selected,setSelected]=useState(params.get('context')?{kind:params.get('kind')||'developed',id:Number(params.get('context'))}:null);
 useEffect(()=>{request(`clients/${clientId}/opportunities`).then(v=>{setBoard(v);
  if(!selected){const first=v.opportunities.find(r=>r.status==='active');if(first)setSelected({kind:first.context_kind,id:first.context_id});}}).catch(e=>setError(e.message));},[clientId]);
 const active=(board?.opportunities||[]).filter(r=>r.status==='active');
 function pick(row){setSelected({kind:row.context_kind,id:row.context_id});history.replaceState(null,'',`?kind=${row.context_kind}&context=${row.context_id}`);}
 return <section className="themen-page assets-page">
  <PageHeading eyebrow={board?.client.name} title="Assets" description="Aktivierte Themen ausarbeiten: Kundenmail, Statement, Pressemitteilung, Gastbeitrag, Pitch oder eigenes Format."/>
  {error&&<p className="twin-error" role="alert">{error}</p>}
  {!board&&!error&&<p role="status">Assets werden geladen…</p>}
  {board&&<div className="assets-layout">
   <aside className="assets-themes" aria-labelledby="assets-themes-title"><h2 id="assets-themes-title">Aktivierte Themen</h2>
    {active.map(row=><button type="button" key={`${row.context_kind}-${row.context_id}`} aria-current={selected?.kind===row.context_kind&&selected?.id===row.context_id?'true':undefined}
     onClick={()=>pick(row)}><strong>{row.title}</strong><span>{row.created_at&&new Date(row.created_at).toLocaleDateString('de-DE')}</span></button>)}
    {!active.length&&<p className="themen-empty">Noch kein Thema aktiviert.</p>}
    <a href={`/client/${clientId}/themen`}>Themen aktivieren →</a>
   </aside>
   <main>{selected?<Workspace key={`${selected.kind}-${selected.id}`} clientId={clientId} kind={selected.kind} identity={selected.id} initialText={params.get('text')||''}/>
    :<p className="themen-empty">Wähle links ein aktiviertes Thema oder aktiviere eines unter Themen.</p>}</main>
  </div>}
 </section>;
}

function Workspace({clientId,kind,identity,initialText=''}){
 const base=`clients/${clientId}/opportunities/${kind}/${identity}`,path=`${base}/activation`;
 const [detail,setDetail]=useState(null),[data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [open,setOpen]=useState(initialText);
 const waiting=useRef(false);
 useEffect(()=>{request(base).then(setDetail).catch(e=>setError(e.message));request(path).then(setData).catch(e=>setError(e.message));},[base,path]);
 const running=data?.latest?.status==='running'&&Date.now()-new Date(data.latest.started_at).getTime()<1200000;
 useEffect(()=>{if(!running)return;const timer=setInterval(()=>request(path).then(v=>{setData(v);
  if(v.latest?.status!=='running'&&waiting.current){waiting.current=false;if(v.latest?.status==='complete'&&v.texts[0])setOpen(`${v.texts[0].type}-${v.texts[0].id}`);}}).catch(e=>setError(e.message)),2500);return()=>clearInterval(timer);},[path,running]);
 async function choose(changes){
  const next={revision:detail.revision,storyline:detail.storyline,speaker_statement_id:null,speaker_person_id:detail.speaker_person_id,contact_ids:detail.contact_ids,...changes};
  const value=await request(base,{method:'PUT',body:JSON.stringify(next)});setDetail(value);return value;
 }
 async function speaker(value){setError('');const [k,id]=value.split(':');
  try{await choose({speaker_person_id:k==='p'?Number(id):null,speaker_statement_id:null});}catch(e){setError(e.message);}}
 async function create(input){setBusy(true);setError('');try{
  if(detail.speaker_statement_id || (input.contact_id&&!detail.contact_ids.includes(input.contact_id)))await choose({contact_ids:input.contact_id?[...new Set([...detail.contact_ids,input.contact_id])]:detail.contact_ids});
  waiting.current=true;
  const job=await request(path,{method:'POST',body:JSON.stringify(input)});
  setData(v=>({...v,latest:{...job,kind:input.kind,started_at:new Date().toISOString()}}));
 }catch(e){waiting.current=false;setError(e.message);}finally{setBusy(false);}}
 if(!detail||!data)return error?<p className="twin-error" role="alert">{error}</p>:<p role="status">Thema wird geladen…</p>;
 const current=data.texts.find(t=>`${t.type}-${t.id}`===open);
 const exportBase=text=>`/api/v1/clients/${clientId}/assets/${text.type}/${text.id}`;
 return <div className="assets-workspace">
  <header className="assets-workspace__head">
   <div><span className="themen-tag themen-tag--on">Thema aktiv</span><h2>{detail.title}</h2>{detail.storyline&&<p>Pitch: {detail.storyline}</p>}</div>
   <div className="assets-workspace__side">
   <ExportBox base={`/api/v1/clients/${clientId}/themen/${kind}/${identity}`} label="Thema exportieren"/>
   <label className="assets-speaker">Ansprechperson (optional)<select aria-label="Ansprechperson (optional)" value={speakerValue(detail)} onChange={e=>speaker(e.target.value)}>
    <option value="">Keine Ansprechperson</option>
    {(detail.people||[]).map(p=><option key={`p${p.id}`} value={`p:${p.id}`}>{p.label}</option>)}
    </select></label>
   </div>
  </header>
  {error&&<p className="twin-error" role="alert">{error}</p>}
  {data.latest&&running&&<p role="status">RAUTE schreibt {LABEL[data.latest.kind]||'den Text'}…</p>}
  {data.latest?.status==='failed'&&<p role="alert" className="twin-error">{data.latest.note||'Der Entwurf ist fehlgeschlagen.'}</p>}
  {data.texts.length>0&&<section aria-labelledby="assets-list-title"><h2 id="assets-list-title" className="assets-section-title">Assets zu diesem Thema</h2>
   <div className="assets-list">{data.texts.map(text=>{const key=`${text.type}-${text.id}`;return <button type="button" key={key} className="asset-card" aria-pressed={open===key} onClick={()=>setOpen(open===key?'':key)}>
    <span>{LABEL[text.kind]||text.kind}<em className={`themen-tag${text.released_at?' themen-tag--on':''}`}>{text.released_at?'Freigegeben':'Entwurf'}</em></span>
    <strong>{text.title||'Ohne Titel'}</strong></button>;})}</div></section>}
  {current&&<Editor key={`${open}-${current.digest}`} text={current} path={path} exportBase={exportBase(current)} onSaved={setData}
   checking={running} onCheck={async t=>{setError('');try{const job=await request(`${path}/${t.type}/${t.id}/check`,{method:'POST'});setData(v=>({...v,latest:{...job,kind:t.kind,started_at:new Date().toISOString()}}));}catch(e){setError(e.message);}}}/>}
  <NewAsset detail={detail} running={running||busy} onCreate={create}/>
 </div>;
}
