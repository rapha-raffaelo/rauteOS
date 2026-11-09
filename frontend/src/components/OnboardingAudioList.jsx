import React, {useEffect, useRef, useState} from 'react';

function Icon({name}) {
  const paths = {
    answer: <path d="M5 3h14v18H5zM8 9l3 3 5-5M8 16h8"/>,
    edit: <path d="m4 16 12-12 4 4L8 20H4zm10-10 4 4"/>,
    blank: <path d="M14 3H5v18h14V8zm0 0v5h5M8 14h8M12 10v8"/>,
    delete: <path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>,
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
function AudioReview({item: a, base, onUpdate, onRemove}) {
  const [editor,setEditor]=useState(false), [value,setValue]=useState('');
  const [busy,setBusy]=useState(false), [error,setError]=useState('');
  const archived=a.review==='archiviert';
  async function act(suffix,method,body) {
    setBusy(true);setError('');
    try {
      const r=await fetch(`${base}/${a.id}${suffix}`,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
      const next=await r.json().catch(()=>({}));
      if(!r.ok)throw Error(typeof next.detail==='string'?next.detail:'Die Aufnahme konnte nicht gespeichert werden. Bitte erneut versuchen.');
      if(method==='DELETE')onRemove(a.id);else onUpdate(next);
      if(suffix==='/answer')setEditor(false);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function open(text){setValue(text);setEditor(true);}
  return <article className="onb-audio-review">
    <div className="onb-audio-review-head"><strong>{a.filename || 'Audioaufnahme'}</strong><button type="button" className="onb-icon onb-icon--danger" title="Audioaufnahme löschen" aria-label="Audioaufnahme löschen" disabled={busy} onClick={()=>act('','DELETE')}><Icon name="delete"/></button></div>
    {a.retained&&<audio controls preload="none" src={`${base}/${a.id}/content`} style={{width:'100%'}}/>}
    <p className="onb-meta">{a.status==='ready'?'Transkribiert':a.status==='failed'?a.note:a.status==='expired'?'Temporäre Aufnahme abgelaufen':a.transcription_configured?'Transkription läuft …':'Wartet auf Transkription'}{archived?' · Archiviert':''}</p>
    {a.transcript&&<details><summary>Transkript anzeigen</summary><p style={{whiteSpace:'pre-wrap'}}>{a.transcript}</p></details>}
    {archived ? a.answer&&<div><strong>Gespeicherte Antwort</strong><p style={{whiteSpace:'pre-wrap'}}>{a.answer}</p></div> : <>
      <div className="onb-icon-actions" aria-label="Audioantwort bearbeiten">
        {[
          ['answer','Als Antwort übernehmen',()=>open(a.transcript),!a.transcript],
          ['edit','Antwort bearbeiten',()=>open(editor?value:a.transcript||''),false],
          ['blank','Leeres Antwortfeld öffnen',()=>open(''),false],
        ].map(([icon,label,click,disabled])=><button key={icon} type="button" className="onb-icon" title={label} aria-label={label} disabled={busy||disabled} onClick={click}><Icon name={icon}/></button>)}
      </div>
      {editor&&<form onSubmit={e=>{e.preventDefault();act('/answer','POST',{value});}}>
        <label className="platform-field"><span>Antwort auf {a.question || a.question_key}</span><textarea autoFocus rows={6} maxLength={20000} required value={value} onChange={e=>setValue(e.target.value)} placeholder="Antwort eingeben oder Text hierher kopieren …" disabled={busy}/></label>
        <p className="onb-meta">Beim Absenden wird die Antwort gespeichert und die Audioaufnahme ins Kundenarchiv verschoben.</p>
        <button type="submit" className="btn btn--go" disabled={busy||!value.trim()}>{busy?'Wird gespeichert …':'Antwort absenden'}</button>
        <button type="button" className="btn" disabled={busy} onClick={()=>setEditor(false)}>Abbrechen</button>
      </form>}
    </>}
    {a.status==='failed'&&<button type="button" className="btn" disabled={busy} onClick={()=>act('/retry','POST')}>Erneut transkribieren</button>}
    {error&&<p role="alert">{error}</p>}
  </article>;
}
export function OnboardingAudioList({clientId, children, onAnswered}) {
  const [items,setItems]=useState([]),[error,setError]=useState('');
  const version=useRef(0);
  const base=`/client/${clientId}/onboarding-audio`;
  useEffect(()=>{let active=true,timer;async function load(){const snapshot=version.current;try{const r=await fetch(base);if(!r.ok)throw Error('Audios konnten nicht geladen werden.');const d=await r.json();if(active&&snapshot===version.current){setItems(Array.isArray(d)?d:[]);setError('');}}catch(e){if(active)setError(e.message);}if(active)timer=setTimeout(load,5000);}load();return()=>{active=false;clearTimeout(timer);};},[base]);
  const pending=items.filter(a=>a.review!=='archiviert'), archived=items.filter(a=>a.review==='archiviert');
  const review=a=><AudioReview key={a.id} item={a} base={base} onUpdate={next=>{version.current++;setItems(previous=>previous.map(row=>row.id===a.id?{...row,...next}:row));if(next.review==='archiviert')onAnswered?.();}} onRemove={id=>{version.current++;setItems(previous=>previous.filter(row=>row.id!==id));}}/>;
  function grouped(rows){return [...new Set(rows.map(a=>a.question_key))].map(key=><section key={key} className="onb-audio-question"><h3>{rows.find(a=>a.question_key===key).question || key}</h3>{rows.filter(a=>a.question_key===key).map(review)}</section>);}
  const archive=<details className="onb-audio-archive"><summary>Kundenarchiv ({archived.length})</summary>{archived.length?grouped(archived):<p>Noch keine archivierten Audioaufnahmen.</p>}</details>;
  if(children)return children({forQuestion:key=>pending.filter(a=>a.question_key===key).map(review),archive,error});
  return <section className="profile-section" aria-label="Audioaufnahmen und Kundenarchiv">
    <h2>Audioaufnahmen</h2>{error&&<p role="alert">{error}</p>}
    {pending.length?grouped(pending):<p className="onb-meta">Keine offenen Audioaufnahmen.</p>}
    {archive}
  </section>;
}
