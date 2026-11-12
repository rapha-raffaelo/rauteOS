import '../news-refresh.css';
import React,{useEffect,useRef,useState} from 'react';
export function NewsRefresh({onFinished}) {
  const [active,setActive]=useState(false),[starting,setStarting]=useState(false),[message,setMessage]=useState('');
  const wasActive=useRef(false), previous=useRef(null), finished=useRef(onFinished); finished.current=onFinished;
  useEffect(()=>{
    let live=true;
    async function poll(){try{
      const r=await fetch('/api/v1/news-run'); if(!r.ok)throw Error(); const d=await r.json(); if(!live)return;
      setActive(d.active);
      if(wasActive.current&&!d.active){
        const completed=d.run&&d.run.id!==previous.current&&d.run.finished_at;
        setMessage(completed?(d.run.errors?`Lauf beendet · ${d.run.errors} Fehler – Details in Einstellungen`:`Lauf beendet · ${d.run.articles} neue Artikel`):'Lauf beendet – Status bitte in Einstellungen prüfen');
        finished.current();
      }
      wasActive.current=d.active; if(!d.active)previous.current=d.run?.id;
    }catch{if(live&&wasActive.current)setMessage('Status momentan nicht abrufbar');}}
    poll(); const timer=setInterval(poll,5000); return()=>{live=false;clearInterval(timer);};
  },[]);
  async function start(){setStarting(true);setMessage('');try{
    const r=await fetch('/api/v1/news-run',{method:'POST'}); const d=await r.json();
    if(!r.ok&&r.status!==409)throw Error(d.detail||'Lauf konnte nicht gestartet werden');
    wasActive.current=true;setActive(true);
  }catch(e){setMessage(e.message);}finally{setStarting(false);}}
  return <div className="news-refresh"><button type="button" className="news-refresh__button" disabled={active||starting} onClick={start} aria-label={active?'Nachrichtenlauf läuft':'Nachrichten aktualisieren'} title={active?'Nachrichtenlauf läuft':'Neuen Nachrichtenlauf starten'}>
    <svg className={active||starting?'news-refresh__spin':''} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M20 7v5h-5M20 12a8 8 0 1 0-2 5"/></svg>
  </button>{(active||message)&&<span role="status">{active?'Nachrichten werden geladen…':message}</span>}</div>;
}
