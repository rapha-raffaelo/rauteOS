import React, {useEffect, useState} from 'react';
import './OverdueTasks.css';
const keyFor = (data, task) => `raute-overdue:${data.member}:${data.day}:${task.id}:${task.due_on}`;
export default function OverdueTasks() {
  const [data,setData]=useState({tasks:[]}), [hidden,setHidden]=useState({});
  useEffect(()=>{
    let stopped=false, pending=false;
    async function check() {
      if(document.hidden || pending) return;
      pending=true;
      try {
        const response=await fetch('/api/v1/tasks/overdue',{signal:AbortSignal.timeout(10000)});
        if(!response.ok) return;
        const next=await response.json();
        if(!stopped) {
          const seen={};
          for(const task of next.tasks || []) {
            try {if(localStorage.getItem(keyFor(next,task))) seen[keyFor(next,task)]=true;} catch {}
          }
          setHidden(previous=>({...previous,...seen}));setData(next);
        }
      } catch { /* Preserve the page when notifications cannot be checked. */ }
      finally {pending=false;}
    }
    check();const timer=setInterval(check,300000);
    window.addEventListener('focus',check);document.addEventListener('visibilitychange',check);
    return ()=>{stopped=true;clearInterval(timer);window.removeEventListener('focus',check);document.removeEventListener('visibilitychange',check);};
  },[]);
  const tasks=(data.tasks || []).filter(task=>!hidden[keyFor(data,task)]);
  if(!data.member || !tasks.length) return null;
  function dismiss() {
    const next={...hidden};
    for(const task of tasks) {
      const key=keyFor(data,task);next[key]=true;
      try {localStorage.setItem(key,'1');} catch {}
    }
    setHidden(next);
  }
  return <aside className="overdue-popup" aria-label="Deine überfälligen Aufgaben">
    <div role="status"><strong>{tasks.length===1?'Eine Aufgabe ist überfällig':`${tasks.length} Aufgaben sind überfällig`}</strong></div>
    <ul>{tasks.slice(0,3).map(task=><li key={task.id}><a href={task.href}>{task.title}</a><small>{task.days_overdue===1?'Seit gestern überfällig':`Seit ${task.days_overdue} Tagen überfällig`}</small></li>)}</ul>
    <div className="overdue-popup__actions"><a href={`/aufgaben?board=all&person=${encodeURIComponent(data.member)}`}>Zu den Aufgaben →</a><button type="button" onClick={dismiss}>Heute ausblenden</button></div>
  </aside>;
}
