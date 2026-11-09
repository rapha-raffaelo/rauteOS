import React, {useEffect, useState} from 'react';
import {OnboardingPage} from './OnboardingPage.jsx';

export function OnboardingAccess({slug}) {
  const [ready,setReady]=useState(false), [checking,setChecking]=useState(true);
  const [password,setPassword]=useState(''), [busy,setBusy]=useState(false), [error,setError]=useState('');
  useEffect(()=>{
    let active=true;
    fetch('/api/onboarding',{credentials:'same-origin',headers:{'X-Onboarding-Slug':slug}})
      .then(r=>{if(active&&r.ok)setReady(true);})
      .catch(()=>{}) .finally(()=>{if(active)setChecking(false);});
    return()=>{active=false;};
  },[slug]);
  async function unlock(e){
    e.preventDefault();setBusy(true);setError('');
    try{
      const r=await fetch('/api/onboarding/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug,password})});
      if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(typeof d.detail==='string'?d.detail:'Anmeldung nicht möglich. Bitte erneut versuchen.');}
      setPassword('');setReady(true);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  if(ready)return <OnboardingPage slug={slug}/>;
  return <main className="onb-access"><p className="onb-access-brand">raute+kopf</p><h1>Ihr Kundenfragebogen</h1>
    {checking?<p role="status">Zugang wird geprüft …</p>:<form onSubmit={unlock}>
      <p>Bitte geben Sie das separat übermittelte Passwort ein.</p>
      <label htmlFor="onboarding-password">Passwort</label>
      <input id="onboarding-password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/>
      <button disabled={busy} type="submit">{busy?'Wird geöffnet …':'Fragebogen öffnen'}</button>
      {error&&<p role="alert">{error}</p>}
    </form>}
    <aside><h2>Ihre Daten sind geschützt</h2><p>Die Übertragung erfolgt verschlüsselt. Der Zugang gilt nur für diesen Fragebogen und kann von raute+kopf deaktiviert werden. Antworten werden für Ihr Kundenprofil und die Kommunikationsarbeit gespeichert. Bitte tragen Sie keine Passwörter oder Zugangsdaten ein.</p><p>Fragen zu Zugriff, Berichtigung oder Löschung richten Sie bitte an Ihren Ansprechpartner bei raute+kopf.</p></aside>
  </main>;
}
