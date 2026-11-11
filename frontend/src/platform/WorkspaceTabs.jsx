import React, {useEffect, useState} from 'react';

export function WorkspaceTabs({boards, activeId, href, person}) {
  const storageKey = `rauteos.workspace-order.${person || 'default'}`;
  const [order, setOrder] = useState([]);
  const [editing, setEditing] = useState(false);
  const [dragged, setDragged] = useState(null);
  const [target, setTarget] = useState(null);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '[]');
      setOrder(Array.isArray(saved) ? saved.filter(x => typeof x === 'string') : []);
    } catch { setOrder([]); }
  }, [storageKey]);
  const items = [{id:'all', name:'Alle Aufgaben', open_count:boards.reduce((n,b)=>n+b.open_count,0)},
    ...boards.map(b=>({...b,id:String(b.id)}))];
  const ranked = [...items].sort((a,b) => {
    const rank = id => order.includes(id) ? order.indexOf(id) : order.length + items.findIndex(x=>x.id===id);
    return rank(a.id)-rank(b.id);
  });
  function move(id, destination) {
    const next = ranked.map(b=>b.id);
    const from = next.indexOf(id);
    if (from < 0 || destination < 0 || destination >= next.length) return;
    next.splice(from,1); next.splice(destination,0,id);
    setOrder(next);
    try { localStorage.setItem(storageKey,JSON.stringify(next)); setNotice('Reihenfolge in diesem Browser gespeichert'); }
    catch { setNotice('Die Reihenfolge konnte in diesem Browser nicht gespeichert werden'); }
  }
  return <>
    <nav aria-label="Workspaces">
      {ranked.map((item,index)=><div key={item.id} className={`tm-workspace-tab${target===item.id?' tm-workspace-tab--target':''}`}
        draggable={editing}
        onDragStart={e=>{setDragged(item.id);e.dataTransfer.setData('text/plain',item.id);e.dataTransfer.effectAllowed='move';}}
        onDragOver={e=>{if(dragged){e.preventDefault();setTarget(item.id);}}}
        onDrop={e=>{e.preventDefault();if(dragged)move(dragged,index);setDragged(null);setTarget(null);}}
        onDragEnd={()=>{setDragged(null);setTarget(null);}}>
        <a href={href(item.id)} draggable={false} onClick={e=>{if(editing)e.preventDefault();}}
          aria-current={item.id===String(activeId || 'all')?'page':undefined}>
          {editing && <span aria-hidden="true">⠿</span>}<span>{item.name}</span><span className="tm-workspace-count">{item.open_count}</span>
        </a>
        {editing && <span className="tm-workspace-move">
          <button type="button" disabled={index===0} aria-label={`${item.name} nach links`} onClick={()=>move(item.id,index-1)}>←</button>
          <button type="button" disabled={index===ranked.length-1} aria-label={`${item.name} nach rechts`} onClick={()=>move(item.id,index+1)}>→</button>
        </span>}
      </div>)}
    </nav>
    <button type="button" className="btn btn--quiet tm-workspace-arrange" aria-pressed={editing} onClick={()=>setEditing(!editing)}>{editing?'Fertig':'Reiter anordnen'}</button>
    <span className="tm-order-status" role="status">{notice}</span>
  </>;
}
