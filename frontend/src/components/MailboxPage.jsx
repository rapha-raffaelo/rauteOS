import React,{useEffect,useRef,useState} from 'react';
import {journalistRequest as request} from '../journalists-api.js';
import {Icon,IconButton} from './mail/icons.jsx';
import {Composer,DriveAssets} from './mail/Composer.jsx';
import {Reader} from './mail/Reader.jsx';

export {Composer,DriveAssets};

// Gmail inside RauteOS, laid out as Gmail is: folders on the left, a tab per
// client over the list, rows that offer their actions on hover, one mail at a
// time, and the window to write in docked at the bottom.
export const FOLDERS=[['inbox','Posteingang','inbox'],['starred','Markiert','star'],['sent','Gesendet','send'],
 ['drafts','Entwürfe','draft'],['all','Alle E-Mails','allMail'],['spam','Spam','spam'],['trash','Papierkorb','trash']];
const UNDO={archive:'inbox',trash:'untrash',spam:'notspam',read:'unread',unread:'read',star:'unstar',unstar:'star',inbox:'archive',untrash:'trash',notspam:'spam'};
const DONE={archive:'archiviert',trash:'in den Papierkorb verschoben',spam:'als Spam gemeldet',read:'als gelesen markiert',unread:'als ungelesen markiert',
 inbox:'in den Posteingang verschoben',untrash:'wiederhergestellt',notspam:'in den Posteingang verschoben'};
const REMOVES={archive:'inbox',trash:'*',spam:'*',untrash:'trash',notspam:'spam',unstar:'starred'};

export const when=(iso,now=new Date())=>{if(!iso)return '';const d=new Date(iso);
 return d.toDateString()===now.toDateString()?d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})
  :d.getFullYear()===now.getFullYear()?d.toLocaleDateString('de-DE',{day:'numeric',month:'short'}):d.toLocaleDateString('de-DE');};

function leaves(folder,action){const rule=REMOVES[action];
 return rule==='*'?!['spam','trash'].includes(folder)||(action==='spam'&&folder==='trash'):rule==='inbox'?folder==='inbox':rule===folder;}

function Chips({files}){
 if(!files?.length)return null;
 const shown=files.slice(0,3);
 return <span className="gm-row__files">{shown.map((f,i)=><span key={i} className="gm-chip gm-chip--row"><span className="gm-chip__type">{(f.name.split('.').pop()||'').slice(0,4).toUpperCase()}</span><span>{f.name}</span></span>)}
  {files.length>3&&<span className="gm-chip gm-chip--more">+{files.length-3}</span>}</span>;
}

function Row({t,selected,onSelect,onOpen,onAct,mayManage}){
 return <li className={`gm-row${t.unread?' is-unread':''}${selected?' is-selected':''}`}>
  <input type="checkbox" className="gm-row__check" aria-label={`${t.subject} auswählen`} checked={selected} onChange={e=>onSelect(e.target.checked)}/>
  <IconButton icon={t.starred?'star':'starOff'} label={t.starred?'Markierung entfernen':'Markieren'} size={18} className={`gm-row__star${t.starred?' is-star':''}`}
   disabled={!mayManage} onClick={()=>onAct([t.id],t.starred?'unstar':'star')}/>
  <button type="button" className="gm-row__open" onClick={onOpen} aria-label={`${t.sender}: ${t.subject}`}>
   <span className="gm-row__from">{t.sender}{t.count>1&&<small> {t.count}</small>}</span>
   <span className="gm-row__text"><span className="gm-row__line"><span className="gm-row__subject">{t.subject}</span><span className="gm-row__snippet"> - {t.snippet}</span></span>
    <Chips files={t.attachments}/></span>
   <time className="gm-row__date">{when(t.date)}</time>
  </button>
  {mayManage&&<span className="gm-row__acts">
   {t.labels?.includes('INBOX')?<IconButton icon="archive" label="Archivieren" size={18} onClick={()=>onAct([t.id],'archive')}/>
    :<IconButton icon="toInbox" label="In den Posteingang" size={18} onClick={()=>onAct([t.id],t.labels?.includes('TRASH')?'untrash':t.labels?.includes('SPAM')?'notspam':'inbox')}/>}
   {!t.labels?.includes('TRASH')&&<IconButton icon="trash" label="Löschen" size={18} onClick={()=>onAct([t.id],'trash')}/>}
   <IconButton icon={t.unread?'read':'unread'} label={t.unread?'Als gelesen markieren':'Als ungelesen markieren'} size={18} onClick={()=>onAct([t.id],t.unread?'read':'unread')}/>
  </span>}
 </li>;
}

function Toast({toast,onUndo,onClose}){
 useEffect(()=>{if(!toast)return undefined;const timer=setTimeout(onClose,7000);return ()=>clearTimeout(timer);},[toast]);// eslint-disable-line react-hooks/exhaustive-deps
 if(!toast)return null;
 return <div className="gm-toast" role="status"><span>{toast.text}</span>{toast.undo&&<button type="button" onClick={onUndo}>Rückgängig</button>}
  <IconButton icon="close" label="Schließen" size={16} onClick={onClose}/></div>;
}

export function MailboxPage(){
 const [status,setStatus]=useState(null),[error,setError]=useState('');
 const [folder,setFolder]=useState('inbox'),[client,setClient]=useState(''),[query,setQuery]=useState(''),[search,setSearch]=useState('');
 const [list,setList]=useState(null),[pages,setPages]=useState(['']),[open,setOpen]=useState(''),[selected,setSelected]=useState([]);
 const [draft,setDraft]=useState(null),[toast,setToast]=useState(null),[unread,setUnread]=useState(null),[rev,setRev]=useState(0);
 const loading=useRef(0);
 useEffect(()=>{request('mailbox').then(setStatus).catch(e=>setError(e.message));},[]);
 function load(token=pages[pages.length-1]){
  const ticket=++loading.current;
  const params=new URLSearchParams({folder,...(client?{client}:{}),...(search?{q:search}:{}),...(token?{page_token:token}:{})});
  request(`mailbox/threads?${params}`).then(v=>{if(ticket!==loading.current)return;setList(v);if(v.unread_inbox!=null)setUnread(v.unread_inbox);})
   .catch(e=>ticket===loading.current&&setError(e.message));
 }
 useEffect(()=>{if(!status?.connected)return;setList(null);setSelected([]);setOpen('');setPages(['']);load('');},[status?.connected,folder,client,search]);// eslint-disable-line react-hooks/exhaustive-deps
 if(error&&!status)return <p className="twin-error" role="alert">{error}</p>;
 if(!status)return <p role="status">Postfach wird geladen…</p>;
 if(!status.connected)return <section className="gm"><div className="gm-empty"><h1>Gmail</h1><p>Kein Postfach verbunden.</p>
  <p><a className="btn btn--go" href="/settings#gmail">Postfach in den Einstellungen verbinden</a></p></div></section>;

 const threads=list?.threads||[];
 function patch(ids,change){setList(l=>l&&{...l,threads:l.threads.map(t=>ids.includes(t.id)?{...t,...change}:t)});}
 async function act(ids,action,{back=false,quiet=false}={}){
  try{await request('mailbox/threads/modify',{method:'POST',body:JSON.stringify({ids,action})});}
  catch(e){setToast({text:e.message});return;}
  if(leaves(folder,action)){setList(l=>l&&{...l,threads:l.threads.filter(t=>!ids.includes(t.id)),total:Math.max(0,(l.total||0)-ids.length)});if(back||ids.includes(open))setOpen('');}
  else if(action==='read'||action==='unread')patch(ids,{unread:action==='unread'});
  else if(action==='star'||action==='unstar')patch(ids,{starred:action==='star'});
  else load();
  if(action==='unread'&&back)setOpen('');
  setSelected(s=>s.filter(id=>!ids.includes(id)));
  if(!quiet&&DONE[action])setToast({text:`${ids.length>1?`${ids.length} Konversationen`:'Konversation'} ${DONE[action]}.`,undo:{ids,action:UNDO[action]}});
 }
 async function undo(){const u=toast?.undo;setToast(null);if(!u)return;
  try{await request('mailbox/threads/modify',{method:'POST',body:JSON.stringify(u)});}catch(e){setToast({text:e.message});return;}load();}
 const page=pages.length,start=threads.length?(page-1)*25+1:0,end=(page-1)*25+threads.length,total=list?.total??0;
 const index=threads.findIndex(t=>t.id===open);
 const allChecked=threads.length>0&&selected.length===threads.length;
 const clientName=status.clients.find(c=>String(c.id)===String(client))?.name;
 const compose=value=>setDraft({client,...value,key:Date.now()});

 return <section className="gm">
  <aside className="gm-side">
   <button type="button" className="gm-write" onClick={()=>compose({})}><Icon name="edit"/>Schreiben</button>
   <nav aria-label="Ordner">{FOLDERS.map(([key,label,icon])=><button key={key} type="button" aria-current={folder===key?'page':undefined}
    onClick={()=>{setFolder(key);setOpen('');}}><Icon name={icon}/><span>{label}</span>{key==='inbox'&&unread>0&&<small>{unread.toLocaleString('de-DE')}</small>}</button>)}</nav>
   <p className="gm-account">{status.email}<br/>Gelesen direkt aus Gmail, nichts davon wird in RauteOS gespeichert.</p>
  </aside>
  <div className="gm-main">
   <form role="search" className="gm-search" onSubmit={e=>{e.preventDefault();setSearch(query.trim());setOpen('');}}>
    <Icon name="search"/><input type="search" aria-label="E-Mails durchsuchen" placeholder={`In ${clientName||'E-Mails'} suchen`} value={query} onChange={e=>setQuery(e.target.value)}/>
   </form>
   {!status.may_manage&&<p className="gm-banner">Archivieren, Löschen und Gelesen-Markieren brauchen einmal eine neue Verbindung mit Verwaltungsrechten. <a href="/settings#gmail">Zu den Einstellungen</a></p>}
   <div className="gm-card">
    {open?<Reader key={`${open}-${rev}`} id={open} summary={threads[index]} me={status.email} client={client} mayManage={status.may_manage}
      position={index>=0?{index:start+index,total,hasPrev:index>0,hasNext:index<threads.length-1}:null}
      onBack={()=>setOpen('')} onAct={act} onStep={step=>setOpen(threads[index+step]?.id||'')} onCompose={compose}
      onRead={id=>act([id],'read',{quiet:true})}/>
    :<>
     <div className="gm-toolbar" role="toolbar" aria-label="Liste">
      <input type="checkbox" aria-label="Alle auswählen" checked={allChecked} ref={n=>{if(n)n.indeterminate=selected.length>0&&!allChecked;}}
       onChange={e=>setSelected(e.target.checked?threads.map(t=>t.id):[])}/>
      {selected.length&&status.may_manage?<>
       {folder==='inbox'?<IconButton icon="archive" label="Archivieren" onClick={()=>act(selected,'archive')}/>:<IconButton icon="toInbox" label="In den Posteingang" onClick={()=>act(selected,folder==='trash'?'untrash':folder==='spam'?'notspam':'inbox')}/>}
       {folder!=='spam'&&<IconButton icon="spam" label="Als Spam melden" onClick={()=>act(selected,'spam')}/>}
       {folder!=='trash'&&<IconButton icon="trash" label="Löschen" onClick={()=>act(selected,'trash')}/>}
       <span className="gm-sep"/>
       <IconButton icon="read" label="Als gelesen markieren" onClick={()=>act(selected,'read')}/>
       <IconButton icon="unread" label="Als ungelesen markieren" onClick={()=>act(selected,'unread')}/>
      </>:<IconButton icon="refresh" label="Aktualisieren" onClick={()=>{setList(null);load();}}/>}
      <span className="gm-grow"/>
      {list&&threads.length>0&&<span className="gm-count">{start.toLocaleString('de-DE')}–{end.toLocaleString('de-DE')} von {Math.max(total,end).toLocaleString('de-DE')}</span>}
      <IconButton icon="prev" label="Neuere" disabled={page<=1} onClick={()=>{const p=pages.slice(0,-1);setPages(p);setList(null);load(p[p.length-1]);}}/>
      <IconButton icon="next" label="Ältere" disabled={!list?.next_page_token} onClick={()=>{const p=[...pages,list.next_page_token];setPages(p);setList(null);load(list.next_page_token);}}/>
     </div>
     <div className="gm-tabs" role="tablist" aria-label="Nach Kunden filtern">
      <button type="button" role="tab" aria-selected={!client} onClick={()=>setClient('')}><Icon name="inbox"/>Alle</button>
      {status.clients.map(c=><button key={c.id} type="button" role="tab" aria-selected={String(client)===String(c.id)} onClick={()=>setClient(String(c.id))}><Icon name="client"/>{c.name}</button>)}
     </div>
     {!list?<p role="status" className="gm-hint gm-pad">E-Mails werden geladen…</p>:<>
      {list.note&&<p className="gm-hint gm-pad">{list.note} <a href={`/client/${client}/twin#kontakte`}>Kontakte pflegen</a></p>}
      <ul className="gm-rows">{threads.map(t=><Row key={t.id} t={t} mayManage={status.may_manage} selected={selected.includes(t.id)}
       onSelect={on=>setSelected(s=>on?[...s,t.id]:s.filter(x=>x!==t.id))} onOpen={()=>setOpen(t.id)} onAct={act}/>)}</ul>
      {!threads.length&&!list.note&&<p className="gm-hint gm-pad">{search?'Keine E-Mails gefunden.':'Hier ist nichts.'}</p>}
     </>}
    </>}
   </div>
  </div>
  {draft&&<Composer key={draft.key} draft={draft} clients={status.clients} canSend={status.may_send} signature={status.signature||''}
   onClose={()=>setDraft(null)} onToast={text=>setToast({text})}
   onSent={()=>{setDraft(null);setToast({text:'Nachricht gesendet.'});if(open)setRev(r=>r+1);else load();}}/>}
  <Toast toast={toast} onUndo={undo} onClose={()=>setToast(null)}/>
 </section>;
}
