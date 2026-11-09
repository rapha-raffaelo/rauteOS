import React, {useEffect, useState} from 'react';

export function OnboardingLinks({clientId}) {
  const [state,setState]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false), [copied,setCopied]=useState(false), [passwordCopied,setPasswordCopied]=useState(false);
  const base=`/client/${clientId}/onboarding-workflow`;
  async function request(path,method='GET',body) {
    const r=await fetch(path,{method,headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(typeof d.detail==='string'?d.detail:'Der Onboarding-Status konnte nicht gespeichert oder geladen werden. Bitte erneut versuchen.');}
    return r.json();
  }
  useEffect(()=>{
    let active=true,timer;
    async function load(){
      try{const s=await request(base);if(active){setState(s);setError('');}}
      catch(e){if(active)setError(e.message);}
      if(active)timer=setTimeout(load,5000);
    }
    load();return()=>{active=false;clearTimeout(timer);};
  },[clientId]);
  async function act(path,method='POST',body){
    setBusy(true);setError('');setCopied(false);setPasswordCopied(false);
    try{await request(path,method,body);setState(await request(base));}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function ensureLink(){
    setBusy(true);setError('');setCopied(false);setPasswordCopied(false);
    try{
      const next=await request(base+'/link/ensure','POST');setState(next);
      try{await navigator.clipboard.writeText(next.public_url || window.location.origin+next.path);setCopied(true);}
      catch{setManual(true);setError('Link erstellt. Bitte im Textfeld kopieren.');}
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  const link=state?.path?(state.public_url || window.location.origin+state.path):'';
  // Manual fallback for browsers without clipboard permission.
  const [manual,setManual]=useState(false);
  async function copyLink(){
    setError('');
    try{await navigator.clipboard.writeText(link);setCopied(true);}
    catch{setManual(true);setError('Kopieren nicht möglich. Bitte den Link im Feld markieren und kopieren.');}
  }
  async function copyPassword(){
    setError('');
    try{await navigator.clipboard.writeText(state.password);setPasswordCopied(true);}
    catch{setError('Bitte das Passwort im Feld markieren und kopieren.');}
  }
  const running=['queued','running'].includes(state?.status);
  const contact=state?.contact||{};
  const [panel,setPanel]=useState('');
  const toggle=name=>setPanel(panel===name?'':name);
  const ready=state?.status==='ready';
  const status=!state?null:state.completed?['done','Vom Kunden abgeschlossen']:running?['running','Recherche läuft']:state.status==='failed'?['failed','Recherche unterbrochen']
    :state.status==='not_started'?['idle','Noch nicht gestartet']
    :state.answered?null:['ready','Bereit für den Kunden'];
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
    {link ? <div className="onb-access-controls">
      <div className="onb-link">
        <span className="onb-short-url">{new URL(link).host}{state.path}</span>
        <div className="onb-icon-actions" aria-label="Fragebogen verwalten">
          <button type="button" className="onb-icon" title="Link kopieren" aria-label="Link kopieren" disabled={busy} onClick={copyLink}><LinkIcon name="copy"/></button>
          <a className="onb-icon" title="Fragebogen öffnen" aria-label="Fragebogen öffnen" href={link} target="_blank" rel="noopener noreferrer"><LinkIcon name="open"/></a>
          <button type="button" className="onb-icon onb-icon--danger" title="Deaktivieren" aria-label="Deaktivieren" disabled={busy} onClick={()=>act(`/client/${clientId}/onboarding-invites/${state.invite_id}/revoke`)}><LinkIcon name="off"/></button>
        </div>
      </div>
      <p className="onb-meta">Gültig bis {new Date(state.expires_at).toLocaleDateString('de-DE',{day:'numeric',month:'long',year:'numeric'})}</p>
      {copied&&<p role="status" className="onb-meta">Link kopiert.</p>}
      {manual&&<input readOnly aria-label="Kundenlink" value={link} onFocus={e=>e.target.select()}/>}
      {state.password&&<div className="onb-password"><label htmlFor={`onb-password-${clientId}`}>Zugangspasswort</label><div className="onb-password-row"><input id={`onb-password-${clientId}`} readOnly value={state.password} onFocus={e=>e.target.select()}/><button type="button" className="onb-icon" title="Passwort kopieren" aria-label="Passwort kopieren" onClick={copyPassword}><LinkIcon name="copy"/></button></div><p>{passwordCopied?'Passwort kopiert.':'Separat an den Kunden weitergeben.'}</p></div>}
    </div> : state && <div className="onb-link onb-link--empty"><p>Kein aktiver Fragebogen-Link.</p><button type="button" className="onb-icon" title="Neuen Fragebogen erstellen" aria-label="Neuen Fragebogen erstellen" disabled={busy} onClick={ensureLink}><LinkIcon name="add"/></button><span className="onb-meta">Neuen Fragebogen erstellen</span><small>Vorhandene Antworten bleiben erhalten.</small></div>}
    {state&&<nav className="onb-more" aria-label="Onboarding verwalten">
      <button type="button" className="linkbtn" aria-expanded={panel==='contact'} onClick={()=>toggle('contact')}>Ansprechpartner bearbeiten</button>
      {ready&&<button type="button" className="linkbtn" aria-expanded={panel==='scope'} onClick={()=>toggle('scope')}>Recherche-Details</button>}
    </nav>}
    {panel==='contact'&&<form className="onb-panel" onSubmit={e=>{e.preventDefault();act(`/client/${clientId}/onboarding-contact`,'PUT',Object.fromEntries(new FormData(e.currentTarget)));}}>
      <div className="onb-grid">{[['contact_name','Name',255,'text'],['contact_role','Funktion',255,'text'],['contact_email','E-Mail',320,'email'],['contact_phone','Telefon',80,'tel']].map(([key,label,max,type])=><label className="platform-field" key={key}><span>{label}</span><input name={key} type={type} maxLength={max} defaultValue={contact[key]||''}/></label>)}</div>
      <button className="btn" disabled={busy} type="submit">Ansprechpartner speichern</button>
    </form>}
    {panel==='scope'&&<p className="onb-panel">{state.pages} Unternehmensseiten gelesen, {state.researched_fields} von {state.total_fields} Angaben öffentlich belegt. Was sich nicht öffentlich belegen lässt, bleibt offen für den Kunden. Die Quellen stehen bei jeder Aussage im Profil.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

function LinkIcon({name}) {
  const paths={copy:<><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3"/></>,open:<><path d="M14 3h7v7M21 3 10 14"/><path d="M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/></>,off:<><path d="M12 2v10M6 5a9 9 0 1 0 12 0"/></>,add:<path d="M12 5v14M5 12h14"/>};
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
