import React, {useEffect, useState} from 'react';
import {OnboardingAudioList} from './OnboardingAudioList.jsx';

export function OnboardingLinks({clientId}) {
  const [state,setState]=useState(null), [items,setItems]=useState([]), [error,setError]=useState(''), [busy,setBusy]=useState(false), [copied,setCopied]=useState(false);
  const base=`/client/${clientId}/onboarding-workflow`;
  async function request(path,method='GET',body) {
    const r=await fetch(path,{method,headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(typeof d.detail==='string'?d.detail:'Der Onboarding-Status konnte nicht gespeichert oder geladen werden. Bitte erneut versuchen.');}
    return r.json();
  }
  useEffect(()=>{
    let active=true,timer;
    async function load(){
      try{const [s,links]=await Promise.all([request(base),request(`/client/${clientId}/onboarding-invites`)]);if(active){setState(s);setItems(links);setError('');}}
      catch(e){if(active)setError(e.message);}
      if(active)timer=setTimeout(load,5000);
    }
    load();return()=>{active=false;clearTimeout(timer);};
  },[clientId]);
  async function act(path,method='POST',body){
    setBusy(true);setError('');setCopied(false);
    try{await request(path,method,body);setState(await request(base));setItems(await request(`/client/${clientId}/onboarding-invites`));}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function ensureLink(){
    setBusy(true);setError('');setCopied(false);
    try{
      const next=await request(base+'/link/ensure','POST');setState(next);
      setItems(await request(`/client/${clientId}/onboarding-invites`));
      try{await navigator.clipboard.writeText(window.location.origin+next.path);setCopied(true);}
      catch{setError('Link erstellt. Bitte im Textfeld kopieren.');}
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  const link=state?.path?window.location.origin+state.path:'';
  const running=['queued','running'].includes(state?.status);
  const contact=state?.contact||{};
  return <section id="kunden-onboarding" className="profile-section" aria-labelledby="onboarding-links-title">
    <h2 id="onboarding-links-title">Kunden-Onboarding</h2>
    <div className="platform-actions"><button type="button" className="btn btn-primary" disabled={busy} onClick={ensureLink}>{busy?'Link wird vorbereitet …':copied?'Link kopiert':link?'Onboarding-Link kopieren':'Onboarding-Link erstellen'}</button></div>
    {link&&<div><label className="platform-field" style={{marginTop:16}}><span>Kundenlink</span><input readOnly value={link} onFocus={e=>e.target.select()}/></label><a href={link} target="_blank" rel="noopener noreferrer">Fragebogen öffnen ↗</a><p><small>Gültig bis {new Date(state.expires_at).toLocaleDateString('de-DE')}.</small></p></div>}
    {!state && !error && <p role="status">Status wird geladen …</p>}
    {running && <div role="status"><p><strong>{state.status==='queued'?'Recherche wartet auf den Start':state.stage}</strong></p><progress style={{width:'100%'}} aria-label="Recherchefortschritt" value={state.completed_batches||0} max={state.total_batches||1}/><p>{state.researched_fields||0} belegte Angaben · {state.sources||0} Quellen. Die Recherche läuft auch bei geschlossenem Browser weiter.</p></div>}
    {state?.status==='failed' && <div role="alert"><p>{state.note}</p><button disabled={busy} onClick={()=>act(base)}>Recherche fortsetzen</button></div>}
    {state?.status==='not_started' && <><p>Website und öffentliche Quellen recherchieren, Profil befüllen und den persönlichen Kundenlink vorbereiten.</p><button disabled={busy} onClick={()=>act(base)}>Recherche & Onboarding starten</button></>}
    {state?.status==='ready' && <>
      <p><strong>{state.completed?'Vom Kunden abgeschlossen':state.answered?'Kunde beantwortet den Fragebogen':'Bereit für den Kunden'}</strong></p>
      <p>{state.researched_fields} belegte Angaben · {state.sources} Quellen · {state.answered}/5 CEO-Antworten</p>

      <details><summary>Rechercheumfang</summary><p>{state.pages} Unternehmensseiten gelesen. {state.researched_fields} von {state.total_fields} öffentlichen Katalogfeldern konnten belegt werden. Nicht öffentlich belegbare Angaben bleiben offen. Die Quellen stehen bei den Aussagen im Profil.</p></details>
    </>}
    {state && <details><summary>Ansprechpartner{contact.contact_name?` · ${contact.contact_name}`:''}</summary>
      <form onSubmit={e=>{e.preventDefault();act(`/client/${clientId}/onboarding-contact`,'PUT',Object.fromEntries(new FormData(e.currentTarget)));}}>
        {[['contact_name','Name',255,'text'],['contact_role','Funktion',255,'text'],['contact_email','E-Mail',320,'email'],['contact_phone','Telefon',80,'tel']].map(([key,label,max,type])=><label className="platform-field" key={key}><span>{label}</span><input name={key} type={type} maxLength={max} defaultValue={contact[key]||''}/></label>)}
        <button disabled={busy} type="submit">Ansprechpartner speichern</button>
      </form>
    </details>}
    <OnboardingAudioList clientId={clientId}/>
    {error && <p role="alert">{error}</p>}
    {items.length>0 && <details><summary>Kundenlinks verwalten</summary><ul>{items.map(i=><li key={i.id}>Link {i.id} · {i.answered}/{i.total} Antworten · {i.revoked?'Deaktiviert':i.completed?'Abgeschlossen':new Date(i.expires_at)<new Date()?'Abgelaufen':'Offen'} {!i.revoked && <button disabled={busy} onClick={()=>act(`/client/${clientId}/onboarding-invites/${i.id}/revoke`)}>Deaktivieren</button>}</li>)}</ul></details>}
  </section>;
}
