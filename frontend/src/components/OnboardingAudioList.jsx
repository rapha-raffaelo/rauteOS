import React, {useEffect, useState} from 'react';

// The archive of customer recordings. An open recording waits under its
// question in the profile's Kundenfragebogen (QuestionAudio); here are the
// ones put away, still playable and deletable.
export function OnboardingAudioList({clientId}) {
  const [items,setItems]=useState([]),[error,setError]=useState('');
  const base=`/client/${clientId}/onboarding-audio`;
  async function load(){try{const r=await fetch(base);if(!r.ok)throw Error('Audios konnten nicht geladen werden.');setItems((await r.json()).filter(a=>a.review==='archiviert'));setError('');}catch(e){setError(e.message);}}
  useEffect(()=>{load();},[clientId]);
  async function remove(id){
    if(!window.confirm('Diese Aufnahme endgültig löschen?'))return;
    try{const r=await fetch(`${base}/${id}`,{method:'DELETE'});if(!r.ok)throw Error('Aufnahme konnte nicht gelöscht werden.');setItems(items.filter(a=>a.id!==id));}catch(e){setError(e.message);}
  }
  if(!items.length&&!error)return null;
  return <section className="profile-section qa-archive"><h2>Audio-Archiv</h2>{error&&<p role="alert">{error}</p>}
    {items.map(a=><article key={a.id} className="qa-rec"><header className="qa-rec__head"><span>Frage {a.question_key.split('.')[1]} · {new Date(a.created_at).toLocaleDateString('de-DE')}</span>
      <button type="button" className="qa-icon" aria-label="Aufnahme löschen" title="Löschen" onClick={()=>remove(a.id)}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/></svg></button></header>
      {a.retained&&<audio controls preload="none" src={`${base}/${a.id}/content`}/>}
      {a.transcript&&<p className="qa-rec__transcript">{a.transcript}</p>}</article>)}</section>;
}
