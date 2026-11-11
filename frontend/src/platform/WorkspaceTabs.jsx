import React, {useEffect, useState} from 'react';

export function WorkspaceTabs({boards, activeId, href, person}) {
  const storageKey = `rauteos.workspace-order.${person || 'default'}`;
  const [order, setOrder] = useState([]);
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
        draggable
        onDragStart={e=>{setDragged(item.id);e.dataTransfer.setData('text/plain',item.id);e.dataTransfer.effectAllowed='move';}}
        onDragOver={e=>{if(dragged){e.preventDefault();setTarget(item.id);}}}
        onDrop={e=>{e.preventDefault();if(dragged)move(dragged,index);setDragged(null);setTarget(null);}}
        onDragEnd={()=>{setDragged(null);setTarget(null);}}>
        <a href={href(item.id)} draggable={false} title="Ziehen zum Anordnen · Alt + Pfeiltaste zum Verschieben"
          onKeyDown={e=>{if(e.altKey && ['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();move(item.id,index+(e.key==='ArrowLeft'?-1:1));}}}
          aria-current={item.id===String(activeId || 'all')?'page':undefined}>
          <span>{item.name}</span><span className="tm-workspace-count">{item.open_count}</span>
        </a>

      </div>)}
    </nav>
    <span className="tm-order-status" role="status">{notice}</span>
  </>;
}
