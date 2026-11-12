import React, {useEffect, useState} from 'react';
import {PageHeading} from './PageHeading.jsx';

export function AssetOverview() {
  const [attempt,setAttempt]=useState(0);
  const [data,setData]=useState(null), [client,setClient]=useState('all');
  const [status,setStatus]=useState('all'), [format,setFormat]=useState('all'), [search,setSearch]=useState('');
  const [error,setError]=useState(''), [loading,setLoading]=useState(true);
  useEffect(()=>{
    const controller=new AbortController(); setLoading(true); setError('');
    fetch(`/api/v1/workbench/assets${client==='all'?'':`?client_id=${client}`}`,{signal:controller.signal})
      .then(r=>{if(!r.ok)throw Error('Assets konnten nicht geladen werden'); return r.json();})
      .then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[client,attempt]);
  const items=data?.texts||[];
  const formats=[...new Map(items.map(t=>[t.format,t.format_name||t.format])).entries()];
  const shown=items.filter(t=>(status==='all'||Boolean(t.released_at)===(status==='released'))&&
    (format==='all'||t.format===format)&&`${t.title} ${t.client}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const ribbon=(label,options,value,onChange)=><div className="asset-ribbon" role="group" aria-label={label}>{options.map(([id,name,count])=><button type="button" key={id} aria-label={count===undefined?name:`${name} ${count}`} aria-pressed={value===id} onClick={()=>onChange(id)}>{name}{count!==undefined&&<span> {count}</span>}</button>)}</div>;
  return <section><PageHeading eyebrow="ASSETS" title="Stories & Content" description="Alle Assets deiner Kunden an einem Ort"/>
    {ribbon('Kunden',[['all','Alle Kunden',data?.total],...(data?.clients||[]).map(c=>[String(c.id),c.name,c.count])],client,v=>{setClient(v);setFormat('all');})}
    <div className="asset-overview-controls">
      {ribbon('Status',[['all','Alle Assets'],['draft','Entwürfe'],['released','Freigegeben']],status,setStatus)}
      <label>Assets suchen<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Titel oder Kunde"/></label>
    </div>
    {formats.length>0&&ribbon('Format',[['all','Alle Formate'],...formats],format,setFormat)}
    {error?<p role="alert">{error} <button onClick={()=>setAttempt(v=>v+1)}>Erneut laden</button></p>:loading?<p role="status">Assets werden geladen…</p>:<>
      <p className="muted">{shown.length} Assets{data?.truncated?` · Die neuesten ${data.limit} Assets in dieser Kundenauswahl`:''}</p>
      <div className="story-cards asset-overview">{shown.map(t=><a className="story-card" key={`${t.type}-${t.id}`} href={t.href}>
        <div className="story-card__m"><span className="badge">{t.format_name||t.format}</span><span className={`badge badge--${t.released_at?'active':'draft'}`}>{t.released_at?'Freigegeben':'Entwurf'}</span></div>
        <h2>{t.title||'Ohne Titel'}</h2><p>{t.client}<span aria-hidden="true">→</span></p><time dateTime={t.generated_at}>{new Date(t.generated_at).toLocaleDateString('de-DE')}</time>
      </a>)}</div>{!shown.length&&<p>Keine Assets für diese Auswahl</p>}
    </>}
  </section>;
}
