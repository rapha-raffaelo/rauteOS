import React,{useEffect,useId,useRef,useState} from 'react';
import {journalistRequest as request} from '../journalists-api.js';
const fields={name:'Name',industry:'Branche',country:'Ländercode',actions_per_quarter:'Zugesagte Leistungen pro Quartal'};
const monitoring={aliases:'Weitere Unternehmensnamen',keywords:'Suchbegriffe',alert_topics:'Alarm-Themen',excluded_terms:'Ausgeschlossene Begriffe',required_terms:'Erforderliche Begriffe'};

export function ClientActions({client,onChanged=()=>window.location.assign('/clients')}){
 const [mode,setMode]=useState(null),[settings,setSettings]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const dialog=useRef(null),titleId=useId();
 useEffect(()=>{if(!mode)return;dialog.current.showModal();let live=true;
  if(mode==='edit')request(`workbench/clients/${client.id}/settings`).then(v=>{if(live)setSettings(v);}).catch(e=>{if(live)setError(e.message);});
  return()=>{live=false;};
 },[mode,client.id]);
 function open(value){setSettings(null);setError('');setMode(value);}
 function close(){if(!busy){dialog.current.close();setMode(null);}}
 async function submit(event){event.preventDefault();setBusy(true);setError('');
  try{await request(`workbench/clients/${client.id}${mode==='edit'?'/settings':''}`,{
   method:mode==='edit'?'PUT':'DELETE',body:JSON.stringify(mode==='edit'?{...settings.values,revision:settings.revision}:{name:client.name})});
   onChanged();
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }
 function input(key,label){return <label key={key}>{label}<input required={key==='name'} type={key==='actions_per_quarter'?'number':'text'} min={key==='actions_per_quarter'?0:undefined} step={key==='actions_per_quarter'?1:undefined}
  value={settings.values[key]} onChange={e=>setSettings({...settings,values:{...settings.values,[key]:e.target.value}})}/></label>;}
 return <><details className="client-card-actions action-disclosure"><summary aria-label={`${client.name} verwalten`}>Verwalten</summary><div className="action-disclosure-body"><button className="btn" aria-label={`${client.name} bearbeiten`} onClick={()=>open('edit')}>Bearbeiten</button><button className="btn client-delete" aria-label={`${client.name} löschen`} onClick={()=>open('delete')}>Löschen</button></div></details>
 {mode&&<dialog ref={dialog} className="client-dialog" aria-labelledby={titleId} onCancel={e=>{e.preventDefault();close();}}>
 <form onSubmit={submit}><h2 id={titleId}>{mode==='edit'?'Mandant bearbeiten':'Mandant löschen?'}</h2><p>{client.name}</p>
 {mode==='delete'?<p>„{client.name}“ wird aus der aktiven Mandantenliste entfernt und nicht mehr überwacht. Archiv, Profil und bisherige Arbeit bleiben erhalten. Unter Einstellungen kann der Mandant reaktiviert werden.</p>
 :!settings&&!error?<p role="status">Mandant wird geladen…</p>:settings&&<fieldset disabled={busy}>
 <div className="client-edit-fields">{Object.entries(fields).map(([key,label])=>input(key,label))}</div>
 <details><summary>Monitoring-Einstellungen</summary><p>Mehrere Begriffe durch Komma oder Semikolon trennen.</p>{Object.entries(monitoring).map(([key,label])=>input(key,label))}</details>
 </fieldset>}
 {error&&<p role="alert" className="twin-error">{error}</p>}
 <div className="client-dialog-actions"><button type="button" className="btn" autoFocus disabled={busy} onClick={close}>Abbrechen</button><button className={`btn ${mode==='delete'?'client-delete':'btn--go'}`} disabled={busy||(mode==='edit'&&!settings)}>{busy?'Wird gespeichert…':mode==='edit'?'Änderungen speichern':'Mandant löschen'}</button></div>
 </form></dialog>}</>;
}
