import React,{useEffect,useState} from 'react';
import './NewsAlerts.css';
export default function NewsAlerts({path=''}){
 const [data,setData]=useState({items:[]}),[seen,setSeen]=useState({});
 const client=path.match(/^\/client\/(\d+)(?:\/|$)/)?.[1];
 useEffect(()=>{
  let stopped=false,pending=false;
  async function check(){
   if(document.hidden||pending)return;
   pending=true;
   try{
    const response=await fetch(`/api/v1/news-alerts${client?`?client_id=${client}`:''}`,{signal:AbortSignal.timeout(10000)});
    if(!response.ok)return;
    const next=await response.json();
    if(stopped)return;
    const hidden={};
    for(const item of next.items||[]){const key=`raute-news:${next.member}:${item.id}`;try{if(localStorage.getItem(key))hidden[key]=true;}catch{}}
    setSeen(previous=>({...previous,...hidden}));setData(next);
   }catch{}finally{pending=false;}
  }
  check();const timer=setInterval(check,60000);window.addEventListener('focus',check);
  return()=>{stopped=true;clearInterval(timer);window.removeEventListener('focus',check);};
 },[client]);
 const keyFor=item=>`raute-news:${data.member}:${item.id}`;
 const items=(data.items||[]).filter(item=>!seen[keyFor(item)]);
 if(!items.length)return null;
 const item=items[0];
 function dismiss(){const key=keyFor(item);try{localStorage.setItem(key,'1');}catch{}setSeen(previous=>({...previous,[key]:true}));}
 return <aside className="news-alert-popup" aria-label={`Gebündelte Alerts für ${item.client_name}`}>
  <header><strong>{item.client_name} · Kundennews</strong><button type="button" aria-label="Hinweis schließen" onClick={dismiss}>×</button></header>
  <div role="status"><h2>{item.title}</h2><p>{item.count} Alerts zu diesem Ereignis · letzte 24 Stunden</p></div>
  <details><summary>Meldungen ansehen</summary><ul>{item.sources.map(source=><li key={source.id}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a><small>{source.source}</small></li>)}</ul></details>
  <footer><a href={item.href} onClick={dismiss}>{item.link_label||'Zum Thema'} →</a><button type="button" onClick={dismiss}>Gelesen</button></footer>
  {items.length>1&&<small>{items.length-1} weitere Hinweise</small>}
 </aside>;
}
