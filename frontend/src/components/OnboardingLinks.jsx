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
  async function copyLink(){
    setError('');
    try{await navigator.clipboard.writeText(link);setCopied(true);}
    catch{setError('Kopieren nicht möglich. Bitte den Link im Feld markieren und kopieren.');}
  }
  const running=['queued','running'].includes(state?.status);
  const contact=state?.contact||{};
  const [panel,setPanel]=useState('');
  const toggle=name=>setPanel(panel===name?'':name);
  const ready=state?.status==='ready';
  const status=!state?null:running?['running','Recherche läuft']:state.status==='failed'?['failed','Recherche unterbrochen']
    :state.status==='not_started'?['idle','Noch nicht gestartet']:state.completed?['done','Vom Kunden abgeschlossen']
    :state.answered?['active','Kunde füllt aus']:['ready','Bereit für den Kunden'];
  const waiting=state?.status==='queued'?(state.stage==='Wartet auf Recherche-Kontingent'?'Recherche pausiert, das Such-Kontingent ist aufgebraucht. Sie läuft automatisch weiter.'
    :state.stage==='Recherche wird gleich fortgesetzt'?'Die Suche hat zu lange gedauert. Die Recherche läuft in Kürze automatisch weiter.':'Recherche wartet auf den Start'):state?.stage;
  return <section id="kunden-onboarding" className="profile-section onb" aria-labelledby="onboarding-links-title">
    <header className="onb-head">
      <div><h2 id="onboarding-links-title">Kunden-Onboarding</h2>
        <p>{contact.contact_name?`Fragebogen für ${contact.contact_name}${contact.contact_role?`, ${contact.contact_role}`:''}`:'Noch kein Ansprechpartner hinterlegt'}</p></div>
      {status&&<span className={`onb-status onb-status--${status[0]}`}>{status[1]}</span>}
    </header>
    {!state && !error && <p role="status">Status wird geladen …</p>}
    {(ready||running)&&<dl className="onb-stats">
      <div><dt>Recherchiert</dt><dd>{state.researched_fields||0}<span> von {state.total_fields} Angaben</span></dd></div>
      <div><dt>Quellen</dt><dd>{state.sources||0}</dd></div>
      <div><dt>Kundenantworten</dt><dd>{state.answered||0}<span> von {state.total_questions||'–'}</span></dd></div>
    </dl>}
    {running && <div role="status" className="onb-running"><p>{waiting}</p><progress aria-label="Recherchefortschritt" value={state.completed_batches||0} max={state.total_batches||1}/><small>Läuft auch bei geschlossenem Browser weiter.</small></div>}
    {state?.status==='failed' && <div role="alert" className="onb-alert"><p>{state.note}</p><button className="btn" disabled={busy} onClick={()=>act(base)}>Recherche fortsetzen</button></div>}
    {state?.status==='not_started' && <div className="onb-start"><p>Website und öffentliche Quellen recherchieren, Profil befüllen und den persönlichen Kundenlink vorbereiten.</p><button className="btn btn--go" disabled={busy} onClick={()=>act(base)}>Recherche & Onboarding starten</button></div>}
    {ready && state.outdated && <div className="onb-alert"><p>Diese Recherche stammt noch aus dem alten Feldkatalog.</p><button className="btn" disabled={busy} onClick={()=>act(base)}>Recherche aktualisieren</button></div>}
    {link ? <div className="onb-link">
      <input readOnly aria-label="Kundenlink" value={link} onFocus={e=>e.target.select()}/>
      <button type="button" className="btn btn--go" disabled={busy} onClick={copyLink}>{copied?'Link kopiert':'Link kopieren'}</button>
      <a className="btn" href={link} target="_blank" rel="noopener noreferrer">Fragebogen öffnen</a>
    </div> : state && <div className="onb-link onb-link--empty"><p>Noch kein Kundenlink.</p><button type="button" className="btn btn--go" disabled={busy} onClick={ensureLink}>{busy?'Link wird vorbereitet …':'Onboarding-Link erstellen'}</button></div>}
    {link&&<p className="onb-meta">Gültig bis {new Date(state.expires_at).toLocaleDateString('de-DE',{day:'numeric',month:'long',year:'numeric'})} · persönlicher Link, nur an den Kunden weitergeben</p>}
    {state&&<nav className="onb-more" aria-label="Onboarding verwalten">
      <button type="button" className="linkbtn" aria-expanded={panel==='contact'} onClick={()=>toggle('contact')}>Ansprechpartner bearbeiten</button>
      {ready&&<button type="button" className="linkbtn" aria-expanded={panel==='scope'} onClick={()=>toggle('scope')}>Recherche-Details</button>}
      {items.length>0&&<button type="button" className="linkbtn" aria-expanded={panel==='links'} onClick={()=>toggle('links')}>Links verwalten ({items.length})</button>}
    </nav>}
    {panel==='contact'&&<form className="onb-panel" onSubmit={e=>{e.preventDefault();act(`/client/${clientId}/onboarding-contact`,'PUT',Object.fromEntries(new FormData(e.currentTarget)));}}>
      <div className="onb-grid">{[['contact_name','Name',255,'text'],['contact_role','Funktion',255,'text'],['contact_email','E-Mail',320,'email'],['contact_phone','Telefon',80,'tel']].map(([key,label,max,type])=><label className="platform-field" key={key}><span>{label}</span><input name={key} type={type} maxLength={max} defaultValue={contact[key]||''}/></label>)}</div>
      <button className="btn" disabled={busy} type="submit">Ansprechpartner speichern</button>
    </form>}
    {panel==='scope'&&<p className="onb-panel">{state.pages} Unternehmensseiten gelesen, {state.researched_fields} von {state.total_fields} Angaben öffentlich belegt. Was sich nicht öffentlich belegen lässt, bleibt offen für den Kunden. Die Quellen stehen bei jeder Aussage im Profil.</p>}
    {panel==='links'&&<ul className="onb-panel onb-links">{items.map(i=><li key={i.id}><span>Link {i.id}</span><span>{i.answered}/{i.total} Antworten</span><span className="onb-muted">{i.revoked?'Deaktiviert':i.completed?'Abgeschlossen':new Date(i.expires_at)<new Date()?'Abgelaufen':'Offen'}</span>{!i.revoked && <button className="linkbtn" disabled={busy} onClick={()=>act(`/client/${clientId}/onboarding-invites/${i.id}/revoke`)}>Deaktivieren</button>}</li>)}</ul>}
    {error && <p role="alert">{error}</p>}
    <OnboardingAudioList clientId={clientId}/>
  </section>;
}
