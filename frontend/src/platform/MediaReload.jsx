import React, {useEffect, useState} from 'react';
const iso = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
// Each term on its own: the name or any one keyword is a hit. Quoting them all
// side by side asked Google for pages that carry every keyword at once, which
// on most days is none.
function googleLink(client, pref, days) {
  const terms = [...(pref.company ? [client.name] : []), ...pref.keywords].map(term => `"${term}"`);
  const range = days.length ? [`after:${days[0]}`, `before:${iso(new Date(new Date(days[days.length - 1] + 'T12:00:00').getTime() + 86400000))}`] : [];
  return 'https://www.google.com/search?q=' + encodeURIComponent([terms.length > 1 ? `(${terms.join(' OR ')})` : terms.join(''), ...range].join(' ').trim());
}
export function MediaReload({data:d}) {
 const today=iso(new Date());
 const clients=d.clients.filter(c=>c.active && !c.is_competitor);
 const [days,setDays]=useState([today]);
 const [month,setMonth]=useState(new Date());
 const [selected,setSelected]=useState(clients.map(c=>c.id));
 const [prefs,setPrefs]=useState(Object.fromEntries(clients.map(c=>[c.id,{company:d.reload_preferences?.[c.id]?.company ?? true, keywords:(d.reload_preferences?.[c.id]?.keywords || c.keywords || []).filter(k=>(c.keywords || []).includes(k))}])));
 const [status,setStatus]=useState(d.reload_status);
 const [busy,setBusy]=useState(!!d.run_active);
 const [from,setFrom]=useState(today),[to,setTo]=useState(today);
 const [error,setError]=useState('');
 useEffect(()=>{
  if(!busy)return;
  const id=setInterval(async()=>{try{const r=await fetch('/settings/reload/status');if(r.ok){const data=await r.json();setStatus(data.status);setBusy(data.active);}}catch{}},3000);
  return ()=>clearInterval(id);
 },[busy]);
 const change=(id,patch)=>setPrefs(p=>({...p,[id]:{...p[id],...patch}}));
 const toggleDay=day=>{setError('');setDays(prev=>prev.includes(day)?prev.filter(x=>x!==day):prev.length<90?[...prev,day].sort():prev);};
 function range(){
  if(!from||!to||from>to||to>today){setError('Bitte einen gültigen Zeitraum bis heute wählen');return;}
  const result=[],cursor=new Date(from+'T12:00:00');
  while(iso(cursor)<=to && result.length<91){result.push(iso(cursor));cursor.setDate(cursor.getDate()+1);}
  if(result.length>90){setError('Bitte höchstens 90 Tage auswählen');return;}
  setDays(result);setError('');setMonth(new Date(from+'T12:00:00'));
 }
 const first=new Date(month.getFullYear(),month.getMonth(),1);
 const offset=(first.getDay()+6)%7,count=new Date(month.getFullYear(),month.getMonth()+1,0).getDate();
 return <section id="media-reload" className="media-reload">
  <p>Unternehmensmeldungen und Suchbegriffe über Google News für ausgewählte Tage nachladen</p>
  <form method="post" action="/settings/reload" onSubmit={e=>{if(!days.length||!selected.length){e.preventDefault();setError('Bitte Tage und Kunden auswählen');}}}>
   <input type="hidden" name="choices" value={JSON.stringify(selected.map(id=>({id,...prefs[id]})))}/>
   {days.map(day=><input type="hidden" key={day} name="days" value={day}/>)}
   <div className="media-reload-grid">
    <div className="media-reload-calendar" aria-label="Tage für den Nachlauf">
     <div className="media-calendar-head"><button type="button" aria-label="Vorheriger Monat" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}>←</button><strong>{month.toLocaleDateString('de-DE',{month:'long',year:'numeric'})}</strong><button type="button" aria-label="Nächster Monat" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}>→</button></div>
     <div className="media-calendar-days">{['Mo','Di','Mi','Do','Fr','Sa','So'].map(x=><span key={x}>{x}</span>)}{Array.from({length:offset},(_,i)=><span key={'blank'+i}/>)}{Array.from({length:count},(_,i)=>{const day=iso(new Date(month.getFullYear(),month.getMonth(),i+1));return <button type="button" key={day} aria-label={day} aria-pressed={days.includes(day)} disabled={day>today} onClick={()=>toggleDay(day)}>{i+1}</button>;})}</div>
     <p>{days.length} von maximal 90 Tagen ausgewählt</p>
     <button type="button" className="btn btn--quiet" onClick={()=>{setDays([today]);setMonth(new Date());}}>Heute</button><button type="button" className="btn btn--quiet" onClick={()=>setDays([])}>Auswahl leeren</button>
     <div className="media-range"><label>Von<input type="date" max={today} value={from} onChange={e=>setFrom(e.target.value)}/></label><label>Bis<input type="date" max={today} value={to} onChange={e=>setTo(e.target.value)}/></label><button type="button" onClick={range}>Zeitraum auswählen</button></div>
    </div>
    <div>
     <details className="media-client-picker"><summary>Kunden auswählen · {selected.length} von {clients.length}</summary><button type="button" className="btn btn--quiet" onClick={()=>setSelected(clients.map(c=>c.id))}>Alle auswählen</button><button type="button" className="btn btn--quiet" onClick={()=>setSelected([])}>Alle abwählen</button>{clients.map(c=><label key={c.id}><input type="checkbox" checked={selected.includes(c.id)} onChange={e=>setSelected(p=>e.target.checked?[...p,c.id]:p.filter(id=>id!==c.id))}/>{c.name}</label>)}</details>
     {clients.filter(c=>selected.includes(c.id)).map(c=><details key={c.id} className="media-client-config"><summary>{c.name} · Suche anpassen</summary><label><input type="checkbox" checked={prefs[c.id].company} onChange={e=>change(c.id,{company:e.target.checked})}/>Unternehmensname und Aliasse</label><p>Suchbegriffe aus dem Kundenprofil</p>{(c.keywords || []).map(keyword=><label key={keyword}><input type="checkbox" checked={prefs[c.id].keywords.includes(keyword)} onChange={e=>change(c.id,{keywords:e.target.checked?[...prefs[c.id].keywords,keyword]:prefs[c.id].keywords.filter(k=>k!==keyword)})}/>{keyword}</label>)}<a href={`/client/${c.id}/twin`}>Suchbegriffe im Profil bearbeiten →</a><p><a target="_blank" rel="noreferrer" href={googleLink(c, prefs[c.id], days)}>Auch direkt bei Google ansehen ↗</a></p></details>)}
    </div>
   </div>
   {error&&<p role="alert">{error}</p>}
   <button type="submit" className="btn btn--go" disabled={busy || !selected.length || !days.length}>{busy?'Lauf aktiv…':'Auswahl nachladen'}</button>
  </form>
  <p>Die Suchauswahl wird pro Kunde gespeichert. Nur Artikel mit einem Veröffentlichungsdatum an den ausgewählten Tagen werden übernommen; vorhandene Artikel werden nicht doppelt gespeichert.</p>
  {status&&<div role="status"><strong>{busy?'Nachlauf läuft':status.state==='done'?'Nachlauf abgeschlossen':status.state==='partial'?'Nachlauf mit Fehlern abgeschlossen':status.state==='failed'?'Nachlauf fehlgeschlagen':'Nachlauf unterbrochen'}</strong>{status.results?.map((r,i)=><p key={i}>{r.client} · {r.day}: {r.found} Treffer, {r.stored} neue Artikel{r.errors?.length>0&&` · ${r.errors.join('; ')}`}</p>)}</div>}
 </section>;
}
