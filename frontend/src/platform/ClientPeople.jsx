import React, {useEffect, useState} from 'react';
const empty={name:'',email:'',phone:'',position:'',topics:'',media_contact:false};
function NewsButton({active,disabled,onClick}) {
  return <button type="button" className={`btn people-news${active?' is-active':''}`} aria-label="Kommuniziert mit Medien" aria-pressed={active} disabled={disabled} onClick={onClick}><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h4v4H7zM14 8h3m-3 4h3M7 16h10"/></svg>News · {active?'Ja':'Nein'}</button>;
}
export function ClientPeople({clientId}) {
  const [people,setPeople]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(false),[draft,setDraft]=useState(null),[saved,setSaved]=useState('');
  const base=`/client/${clientId}/people`;
  async function request(path='',method='GET',body){
    const r=await fetch(base+path,{method,headers:{Accept:'application/json','Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
    const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Kontakt konnte nicht gespeichert werden. Bitte Eingaben prüfen.');return data;
  }
  useEffect(()=>{let active=true;request().then(data=>{if(active)setPeople(Array.isArray(data)?data:[]);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[clientId]);
  async function save(person,close=false){
    setBusy(true);setError('');setSaved('');
    try{const {id,...body}=person;const next=await request(id?`/${id}`:'',id?'PUT':'POST',body);setPeople(rows=>id?rows.map(row=>row.id===id?next:row):[...rows,next]);if(close)setDraft(null);setSaved('Kontakt gespeichert.');}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="platform-panel client-people" aria-labelledby={`people-title-${clientId}`}>
    <header className="onb-head"><h2 id={`people-title-${clientId}`}>Kontakte & Sprecher</h2><button type="button" className="btn" disabled={busy||!!draft} onClick={()=>{setDraft({...empty});setSaved('');}}>Kontakt hinzufügen</button></header>
    <p className="onb-meta">News zeigt, ob die Person mit den Medien kommuniziert.</p>
    {loading&&<p role="status">Kontakte werden geladen …</p>}
    {!loading&&!people.length&&<p>Noch keine strukturierten Kontakte hinterlegt.</p>}
    {!!people.length&&<div className="people-table-scroll"><table className="people-table"><thead><tr>{['Name','E-Mail','Telefon','Position','Verantwortungsbereich','Medienkommunikation',''].map((label,i)=><th key={i} scope="col">{label}</th>)}</tr></thead><tbody>{people.map(person=><tr key={person.id}>
      <th scope="row">{person.name}</th><td>{person.email||'–'}</td><td>{person.phone||'–'}</td><td>{person.position||'–'}</td><td className="people-topics">{person.topics||'–'}</td>
      <td><NewsButton active={person.media_contact} disabled={busy||!!draft} onClick={()=>save({...person,media_contact:!person.media_contact})}/></td>
      <td><button type="button" className="btn" disabled={busy||!!draft} onClick={()=>{setDraft({...person});setSaved('');}}>Bearbeiten</button></td>
    </tr>)}</tbody></table></div>}
    {draft&&<form className="people-editor" onSubmit={e=>{e.preventDefault();save(draft,true);}}>
      <h3>{draft.id?'Kontakt bearbeiten':'Neuer Kontakt'}</h3><div className="people-fields">{[['name','Name','text',200],['email','E-Mail','email',320],['phone','Telefon','tel',80],['position','Position','text',200]].map(([key,label,type,max])=><label className="platform-field" key={key}><span>{label}</span><input type={type} required={key==='name'} maxLength={max} value={draft[key]} disabled={busy} onChange={e=>setDraft({...draft,[key]:e.target.value})}/></label>)}
      <label className="platform-field platform-span"><span>Verantwortungsbereich</span><textarea rows={3} maxLength={20000} value={draft.topics} disabled={busy} onChange={e=>setDraft({...draft,topics:e.target.value})}/></label></div>
      <div className="people-editor-actions"><NewsButton active={draft.media_contact} disabled={busy} onClick={()=>setDraft({...draft,media_contact:!draft.media_contact})}/><button className="btn btn--go" disabled={busy||!draft.name.trim()}>Kontakt speichern</button><button type="button" className="btn" disabled={busy} onClick={()=>setDraft(null)}>Abbrechen</button></div>
    </form>}
    {error&&<p role="alert">{error}</p>}{saved&&<p role="status">{saved}</p>}
  </section>;
}
