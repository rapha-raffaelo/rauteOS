import React, {useState} from 'react';
export function SubtaskProgress({task}) {
 const rows=task.subtasks || [];
 if(!rows.length)return null;
 return <span className="tm-subtask-progress">☑ {rows.filter(row=>row.completed).length}/{rows.length} Unteraufgaben</span>;
}
export function Subtasks({task,onChange,compact=false}) {
 const [title,setTitle]=useState('');
 const [editing,setEditing]=useState(null);
 const [edited,setEdited]=useState('');
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const rows=task.subtasks || [];
 async function save(values,id) {
  if(busy)return false;
  setBusy(true);setError('');
  try {
   const response=await fetch(`/aufgaben/${task.id}/subtasks${id?'/'+id:''}`,{method:'POST',headers:{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(values)});
   const data=await response.json();
   if(!response.ok || !Array.isArray(data.subtasks))throw Error(data.error || 'Unteraufgabe konnte nicht gespeichert werden');
   onChange(data.subtasks);return true;
  }catch(e){setError(e.message || 'Bitte erneut versuchen');return false;}finally{setBusy(false);}
 }
 async function add(){if(title.trim() && await save({title:title.trim()}))setTitle('');}
 async function rename(id){if(edited.trim() && await save({title:edited.trim()},id))setEditing(null);}
 return <section className={`tm-subtasks${compact ? " tm-subtasks--compact" : ""}`} onDragStart={compact ? e=>{e.preventDefault();e.stopPropagation();} : undefined} aria-label="Unteraufgaben" aria-busy={busy}>
  <div className="tm-subtasks-heading">{!compact && <strong>Unteraufgaben</strong>}<SubtaskProgress task={task}/></div>
  <ul>{rows.map(row=><li key={row.id}>
   <input type="checkbox" aria-label={`${row.title} erledigt`} checked={row.completed} disabled={busy} onChange={e=>save({completed:e.target.checked?'1':'0'},row.id)}/>
   {editing===row.id?<><input aria-label="Unteraufgabe umbenennen" maxLength={200} value={edited} onChange={e=>setEdited(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();rename(row.id);}}}/><button type="button" disabled={busy || !edited.trim()} onClick={()=>rename(row.id)}>OK</button><button type="button" onClick={()=>setEditing(null)}>Abbrechen</button></>:<>
    <span className={row.completed?'tm-subtask-done':''}>{row.title}</span>
    {!compact && <><button type="button" className="tm-subtask-icon" aria-label={`${row.title} bearbeiten`} disabled={busy} onClick={()=>{setEditing(row.id);setEdited(row.title);}}>✎</button>
    <button type="button" className="tm-subtask-icon" aria-label={`${row.title} löschen`} disabled={busy} onClick={()=>save({delete:'1'},row.id)}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></svg></button></>}
   </>}
  </li>)}</ul>
  {!compact && <div className="tm-subtask-add"><input aria-label="Neue Unteraufgabe" value={title} maxLength={200} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();add();}}}/><button type="button" disabled={busy || !title.trim()} onClick={add}>+ Hinzufügen</button></div>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
