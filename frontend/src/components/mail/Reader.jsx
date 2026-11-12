import React,{useEffect,useRef,useState} from 'react';
import {journalistRequest as request} from '../../journalists-api.js';
import {Icon,IconButton} from './icons.jsx';
import {size} from './Composer.jsx';

const escape=s=>String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const LABELS={INBOX:'Posteingang',SPAM:'Spam',TRASH:'Papierkorb',SENT:'Gesendet',DRAFT:'Entwurf'};

export function relative(iso,now=new Date()){
 if(!iso)return '';const d=new Date(iso),minutes=Math.round((now-d)/60000);
 const time=d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});
 if(d.toDateString()===now.toDateString())return `${time} (vor ${minutes<60?`${Math.max(1,minutes)} Minute${minutes===1?'':'n'}`:`${Math.round(minutes/60)} Stunde${Math.round(minutes/60)===1?'':'n'}`})`;
 return `${d.toLocaleDateString('de-DE',{day:'numeric',month:'short',year:d.getFullYear()===now.getFullYear()?undefined:'numeric'})}, ${time}`;
}
const fullDate=iso=>iso?new Date(iso).toLocaleString('de-DE',{weekday:'short',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}):'';
const addresses=raw=>String(raw||'').split(',').map(s=>s.trim()).filter(Boolean);
const emailOf=s=>(s.match(/<([^>]+)>/)?.[1]||s).trim();

// A mail's own HTML, shown as Gmail shows it, in a frame that runs no script.
// The server has already taken out what could; the sandbox is the second lock.
export function HtmlBody({html}){
 const frame=useRef(null),[height,setHeight]=useState(120);
 const doc=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'"><base target="_blank"><style>html,body{margin:0;background:#fff;color:#222;font:14px/1.5 Arial,Helvetica,sans-serif;overflow-wrap:anywhere}img{max-width:100%;height:auto}table{max-width:100%}blockquote{margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex}</style></head><body>${html}</body></html>`;
 useEffect(()=>{const node=frame.current;if(!node)return undefined;let observer;
  function fit(){try{const d=node.contentDocument;if(!d?.documentElement)return;setHeight(Math.max(60,d.documentElement.scrollHeight));
   if(!observer&&window.ResizeObserver){observer=new ResizeObserver(fit);observer.observe(d.documentElement);}}catch{/* not same origin */}}
  node.addEventListener('load',fit);return ()=>{node.removeEventListener('load',fit);observer?.disconnect();};},[html]);
 return <iframe ref={frame} className="gm-html" title="Inhalt der E-Mail" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" srcDoc={doc} style={{height}}/>;
}

export function quoteHtml(message){
 const text=escape(message.body).replace(/\n/g,'<br>');
 return `<div class="gmail_quote"><div>Am ${escape(fullDate(message.date))} schrieb ${escape(message.sender)} &lt;${escape(message.sender_email)}&gt;:</div><blockquote style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex">${text}</blockquote></div>`;
}
export function forwardHtml(message){
 const original=String(message.html||'').replace(/<style[\s\S]*?<\/style>/gi,'')||escape(message.body).replace(/\n/g,'<br>');
 return `<div class="gmail_quote">---------- Weitergeleitete Nachricht ---------<br>Von: <strong>${escape(message.sender)}</strong> &lt;${escape(message.sender_email)}&gt;<br>Datum: ${escape(fullDate(message.date))}<br>Betreff: ${escape(message.subject)}<br>An: ${escape(message.to)}${message.cc?`<br>Cc: ${escape(message.cc)}`:''}<br><br>${original}</div>`;
}
const prefixed=(prefix,subject)=>new RegExp(`^${prefix}:`,'i').test(subject||'')?subject:`${prefix}: ${subject||''}`;

function Avatar({name}){
 return <span className="gm-avatar" aria-hidden="true">{(name||'?').trim().charAt(0).toUpperCase()}</span>;
}

function Attachments({message}){
 if(!message.attachments?.length)return null;
 return <div className="gm-files"><p>{message.attachments.length} Anhang{message.attachments.length>1?'e':''}</p>
  <ul>{message.attachments.map(a=>{const url=`/api/v1/mailbox/messages/${encodeURIComponent(a.message_id)}/parts/${encodeURIComponent(a.part_id)}`;
   return <li key={a.part_id}><a href={`${url}?download=1`} className="gm-file" title={`${a.name} herunterladen`}>
    {/^image\/(png|jpeg|gif|webp)$/.test(a.mime)?<img src={url} alt=""/>:<span className="gm-file__type">{(a.name.split('.').pop()||'').slice(0,4).toUpperCase()}</span>}
    <span className="gm-file__name">{a.name}</span><small>{a.size?size(a.size):''}</small></a></li>;})}</ul></div>;
}

function MessageView({message,me,open,onToggle,onReply,onReplyAll,onForward}){
 const [details,setDetails]=useState(false);
 const toMe=addresses(message.to).map(emailOf).some(a=>a.toLowerCase()===String(me).toLowerCase());
 if(!open)return <button type="button" className="gm-msg gm-msg--folded" onClick={onToggle}>
  <Avatar name={message.sender}/><strong>{message.sender}</strong><span className="gm-msg__snippet">{message.snippet||message.body.slice(0,140)}</span><time>{relative(message.date)}</time></button>;
 return <section className="gm-msg" aria-label={`Nachricht von ${message.sender}`}>
  <div className="gm-msg__head">
   <Avatar name={message.sender}/>
   <div className="gm-msg__who">
    <button type="button" className="gm-msg__fold" onClick={onToggle}><strong>{message.sender}</strong> <span>&lt;{message.sender_email}&gt;</span></button>
    <button type="button" className="gm-msg__to" aria-expanded={details} onClick={()=>setDetails(!details)}>an {toMe&&addresses(message.to).length===1&&!message.cc?'mich':addresses(message.to).map(a=>a.replace(/<.*>/,'').trim()||a).join(', ')}</button>
    {details&&<dl className="gm-msg__details"><dt>von:</dt><dd>{message.sender} &lt;{message.sender_email}&gt;</dd><dt>an:</dt><dd>{message.to}</dd>
     {message.cc&&<><dt>cc:</dt><dd>{message.cc}</dd></>}<dt>Datum:</dt><dd>{fullDate(message.date)}</dd><dt>Betreff:</dt><dd>{message.subject}</dd></dl>}
   </div>
   <div className="gm-msg__acts"><time>{relative(message.date)}</time>
    <IconButton icon="reply" label="Antworten" onClick={()=>onReply(message)}/>
    <IconButton icon="replyAll" label="Allen antworten" onClick={()=>onReplyAll(message)}/>
    <IconButton icon="forward" label="Weiterleiten" onClick={()=>onForward(message)}/>
   </div>
  </div>
  <div className="gm-msg__body">{message.html?<HtmlBody html={message.html}/>:<div className="gm-plain">{message.body||'(kein lesbarer Text)'}</div>}</div>
  <Attachments message={message}/>
 </section>;
}

export function Reader({id,summary,me,client,mayManage,position,onBack,onAct,onStep,onCompose,onRead}){
 const [messages,setMessages]=useState(null),[error,setError]=useState(''),[open,setOpen]=useState({});
 useEffect(()=>{setMessages(null);setError('');setOpen({});
  request(`mailbox/threads/${encodeURIComponent(id)}`).then(v=>{setMessages(v.messages);
   const last=v.messages.length-1;setOpen(Object.fromEntries(v.messages.map((m,i)=>[m.id,i===last||m.unread])));
   if(mayManage&&v.messages.some(m=>m.unread))onRead?.(id);}).catch(e=>setError(e.message));},[id]);// eslint-disable-line react-hooks/exhaustive-deps
 const first=messages?.[0],labels=summary?.labels||[];
 function reply(message,all=false){
  const others=all?[...addresses(message.to),...addresses(message.cc)].filter(a=>emailOf(a).toLowerCase()!==String(me).toLowerCase()&&emailOf(a).toLowerCase()!==message.sender_email.toLowerCase()):[];
  const fromMe=message.sender_email.toLowerCase()===String(me).toLowerCase();
  onCompose({to:fromMe?message.to:message.sender_email,cc:all?others.join(', '):'',subject:prefixed('Re',first?.subject),thread_id:id,
   reply_to:message.message_id_header,references:message.references,client,html:quoteHtml(message)});
 }
 function forward(message){
  onCompose({subject:prefixed('Fwd',message.subject),client,html:forwardHtml(message),
   forwarded:(message.attachments||[]).map(a=>({message_id:a.message_id,part_id:a.part_id,name:a.name,size:a.size}))});
 }
 const act=action=>()=>onAct([id],action,{back:true});
 const inTrash=labels.includes('TRASH'),inSpam=labels.includes('SPAM'),inInbox=labels.includes('INBOX');
 return <article className="gm-reader">
  <div className="gm-toolbar" role="toolbar" aria-label="E-Mail">
   <IconButton icon="back" label="Zurück zur Liste" onClick={onBack}/>
   {mayManage&&<>
    {inInbox?<IconButton icon="archive" label="Archivieren" onClick={act('archive')}/>:<IconButton icon="toInbox" label="In den Posteingang" onClick={act(inSpam?'notspam':'inbox')}/>}
    {!inSpam&&<IconButton icon="spam" label="Als Spam melden" onClick={act('spam')}/>}
    {inTrash?<IconButton icon="toInbox" label="Wiederherstellen" onClick={act('untrash')}/>:<IconButton icon="trash" label="Löschen" onClick={act('trash')}/>}
    <span className="gm-sep"/>
    <IconButton icon="unread" label="Als ungelesen markieren" onClick={act('unread')}/>
    <IconButton icon={summary?.starred?'star':'starOff'} label={summary?.starred?'Markierung entfernen':'Markieren'} className={summary?.starred?'is-star':''}
     onClick={()=>onAct([id],summary?.starred?'unstar':'star',{})}/>
   </>}
   <span className="gm-grow"/>
   {position&&<span className="gm-count">{position.index.toLocaleString('de-DE')} von {position.total.toLocaleString('de-DE')}</span>}
   <IconButton icon="prev" label="Neuere" disabled={!position?.hasPrev} onClick={()=>onStep(-1)}/>
   <IconButton icon="next" label="Ältere" disabled={!position?.hasNext} onClick={()=>onStep(1)}/>
  </div>
  {error?<p className="twin-error" role="alert">{error}</p>:!messages?<p role="status" className="gm-hint gm-pad">Nachricht wird geladen…</p>:<>
   <header className="gm-reader__head">
    <h2>{first?.subject||'(kein Betreff)'}</h2>
    {labels.filter(l=>LABELS[l]).map(l=><span key={l} className="gm-label">{LABELS[l]}</span>)}
    <span className="gm-grow"/>
    <a className="gm-ib" href={`https://mail.google.com/mail/u/${encodeURIComponent(me||0)}/#all/${encodeURIComponent(id)}`} target="_blank" rel="noopener noreferrer"
     aria-label="In Gmail öffnen" title="In Gmail öffnen"><Icon name="external"/></a>
   </header>
   {messages.map(m=><MessageView key={m.id} message={m} me={me} open={!!open[m.id]} onToggle={()=>setOpen({...open,[m.id]:!open[m.id]})}
    onReply={reply} onReplyAll={m=>reply(m,true)} onForward={forward}/>)}
   <div className="gm-reader__foot">
    <button type="button" className="gm-pill" onClick={()=>reply(messages[messages.length-1])}><Icon name="reply"/>Antworten</button>
    {(addresses(messages[messages.length-1].to).length+addresses(messages[messages.length-1].cc).length)>1&&
     <button type="button" className="gm-pill" onClick={()=>reply(messages[messages.length-1],true)}><Icon name="replyAll"/>Allen antworten</button>}
    <button type="button" className="gm-pill" onClick={()=>forward(messages[messages.length-1])}><Icon name="forward"/>Weiterleiten</button>
   </div>
  </>}
 </article>;
}
