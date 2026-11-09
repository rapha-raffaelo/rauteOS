import React,{useEffect,useState} from 'react';
export function CommunicationTargets({clientId}){
 const [data,setData]=useState(null),[value,setValue]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
 const url=`/api/v1/workbench/clients/${clientId}/settings`;
 useEffect(()=>{let active=true;fetch(url,{headers:{Accept:'application/json'}}).then(async r=>{if(!r.ok)throw new Error('Kommunikationsziele konnten nicht geladen werden.');return r.json();}).then(d=>{if(active){setData(d);setValue(d.values.actions_per_quarter);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[clientId]);
 async function save(e){e.preventDefault();setBusy(true);setError('');setSaved(false);try{
  const r=await fetch(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data.values,actions_per_quarter:value,revision:data.revision})});const result=await r.json();if(!r.ok)throw new Error(result.detail||'Speichern nicht möglich.');
  const updated=await fetch(url,{headers:{Accept:'application/json'}});if(!updated.ok)throw new Error('Gespeichert. Bitte zum Aktualisieren neu laden.');setData(await updated.json());setSaved(true);
 }catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section className="profile-section communication-targets"><h2>Vereinbarte Kommunikationsziele</h2><p>Die hinterlegte Quartalszusage bleibt die Grundlage für den Leistungsnachweis.</p>
 {data?<form onSubmit={save}><label className="platform-field"><span>Vereinbarte Actions pro Quartal</span><input type="number" min="0" step="1" max="2147483647" value={value} placeholder="Noch nicht vereinbart" onChange={e=>{setValue(e.target.value);setSaved(false);}}/></label><button className="btn" disabled={busy||value===data.values.actions_per_quarter}>Ziel speichern</button><a href={`/client/${clientId}/actions`}>Zum Leistungsnachweis →</a></form>:!error&&<p role="status">Kommunikationsziele werden geladen …</p>}
 {saved&&<p role="status">Quartalsziel gespeichert.</p>}{error&&<p role="alert">{error}</p>}</section>;
}
