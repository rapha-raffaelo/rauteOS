import React,{useEffect,useState} from 'react';
import {PageHeading} from './PageHeading.jsx';
import {journalistRequest as request} from '../journalists-api.js';

// Gmail inside RauteOS: the mailbox read live from Gmail, filtered by client,
// and mail written with the client's assets from the Drive folder attached.
export const FOLDERS=[['inbox','Posteingang'],['starred','Markiert'],['sent','Gesendet'],['drafts','Entwürfe']];
const when=iso=>{if(!iso)return '';const d=new Date(iso),today=new Date();
 return d.toDateString()===today.toDateString()?d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}):d.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'});};
const size=bytes=>bytes>1048576?`${(bytes/1048576).toFixed(1)} MB`:`${Math.max(1,Math.round(bytes/1024))} KB`;
const re=subject=>/^re:/i.test(subject||'')?subject:`Re: ${subject||''}`;

export function DriveAssets({client,selected,onChange}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{if(!client)return;setData(null);setError('');
  request(`mailbox/assets?client=${client}`).then(setData).catch(e=>setError(e.message));},[client]);
 if(!client)return <p className="mailbox-hint">Kunden wählen, um seine Assets aus Drive anzuhängen.</p>;
 if(error)return <p className="mailbox-hint" role="alert">{error}{/verbunden|Einstellungen/.test(error)&&<> <a href="/settings#drive">Drive verbinden</a></>}</p>;
 if(!data)return <p role="status" className="mailbox-hint">Assets werden geladen…</p>;
 return <fieldset className="mailbox-assets"><legend>Assets aus {data.folder}</legend>
  {data.files.length?data.files.map(f=><label key={f.id}><input type="checkbox" checked={selected.includes(f.id)}
   onChange={e=>onChange(e.target.checked?[...selected,f.id]:selected.filter(x=>x!==f.id))}/>
   <span>{f.name}</span><small>{f.size?size(f.size):'Google-Dokument, als PDF'}</small></label>)
   :<p className="mailbox-hint">Noch keine Assets im Ordner. Unter Assets „In Drive ablegen“.</p>}
 </fieldset>;
}

export function Composer({draft,clients,canSend,onClose,onSent}){
 const [form,setForm]=useState({to:'',cc:'',subject:'',body:'',client:'',...draft});
 const [files,setFiles]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const set=key=>e=>setForm({...form,[key]:e.target.value});
 async function send(e){e.preventDefault();setBusy(true);setError('');
  try{await request('mailbox/send',{method:'POST',body:JSON.stringify({to:form.to,cc:form.cc,subject:form.subject,body:form.body,
   thread_id:form.thread_id||'',reply_to:form.reply_to||'',drive_files:files})});onSent();}
  catch(err){setError(err.message);}finally{setBusy(false);}}
 return <form className="mailbox-compose" onSubmit={send} aria-label={form.thread_id?'Antworten':'Neue E-Mail'}>
  <header><h2>{form.thread_id?'Antworten':'Neue E-Mail'}</h2><button type="button" className="btn btn--quiet" onClick={onClose}>Verwerfen</button></header>
  {error&&<p className="twin-error" role="alert">{error}</p>}
  <label>An<input value={form.to} onChange={set('to')} required placeholder="name@beispiel.de, …"/></label>
  <label>Cc<input value={form.cc} onChange={set('cc')}/></label>
  <label>Betreff<input value={form.subject} onChange={set('subject')}/></label>
  <label>Text<textarea rows={12} value={form.body} onChange={set('body')}/></label>
  <label>Kunde für Assets<select value={form.client} onChange={e=>{setForm({...form,client:e.target.value});setFiles([]);}}>
   <option value="">Kein Kunde</option>{clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
  <DriveAssets client={form.client} selected={files} onChange={setFiles}/>
  <div className="mailbox-compose__acts">
   {!canSend&&<span className="mailbox-hint">Das Postfach darf nicht senden. Unter Einstellungen mit Senderechten verbinden.</span>}
   <button className="btn btn--go" disabled={busy||!canSend}>{busy?'Wird gesendet…':`Senden${files.length?` · ${files.length} Anhang${files.length>1?'e':''}`:''}`}</button>
  </div>
 </form>;
}

function Reader({id,client,onReply}){
 const [messages,setMessages]=useState(null),[error,setError]=useState('');
 useEffect(()=>{setMessages(null);setError('');request(`mailbox/threads/${encodeURIComponent(id)}`).then(v=>setMessages(v.messages)).catch(e=>setError(e.message));},[id]);
 if(error)return <p className="twin-error" role="alert">{error}</p>;
 if(!messages)return <p role="status">Nachricht wird geladen…</p>;
 const last=messages[messages.length-1]||{};
 return <article className="mailbox-reader">
  <header><h2>{messages[0]?.subject||'(ohne Betreff)'}</h2>
   <button type="button" className="btn btn--go" onClick={()=>onReply({to:last.sender_email,subject:re(messages[0]?.subject),thread_id:id,reply_to:last.message_id_header,client,
    body:`\n\nAm ${new Date(last.date).toLocaleString('de-DE')} schrieb ${last.sender}:\n${last.body.split('\n').map(l=>'> '+l).join('\n')}`})}>Antworten</button></header>
  {messages.map(m=><section key={m.id} className="mailbox-message">
   <div className="mailbox-message__head"><strong>{m.sender}</strong><span>{m.sender_email}</span><time>{m.date&&new Date(m.date).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'})}</time></div>
   <p className="mailbox-message__to">An: {m.to}{m.cc&&` · Cc: ${m.cc}`}</p>
   <div className="mailbox-message__body">{m.body||'(kein lesbarer Text)'}</div>
   {m.attachments.length>0&&<p className="mailbox-message__files">Anhänge: {m.attachments.join(', ')}</p>}
  </section>)}
 </article>;
}

export function MailboxPage(){
 const [status,setStatus]=useState(null),[error,setError]=useState('');
 const [folder,setFolder]=useState('inbox'),[client,setClient]=useState(''),[query,setQuery]=useState(''),[search,setSearch]=useState('');
 const [list,setList]=useState(null),[open,setOpen]=useState(''),[draft,setDraft]=useState(null),[notice,setNotice]=useState('');
 useEffect(()=>{request('mailbox').then(setStatus).catch(e=>setError(e.message));},[]);
 function load(token=''){
  const params=new URLSearchParams({folder,...(client?{client}:{}),...(search?{q:search}:{}),...(token?{page_token:token}:{})});
  if(!token)setList(null);
  request(`mailbox/threads?${params}`).then(v=>setList(old=>token&&old?{...v,threads:[...old.threads,...v.threads]}:v)).catch(e=>setError(e.message));
 }
 useEffect(()=>{if(status?.connected)load();},[status?.connected,folder,client,search]);
 if(error&&!status)return <p className="twin-error" role="alert">{error}</p>;
 if(!status)return <p role="status">Postfach wird geladen…</p>;
 if(!status.connected)return <section className="mailbox-page"><PageHeading title="Gmail" description="Kein Postfach verbunden."/>
  <p><a className="btn btn--go" href="/settings#gmail">Postfach in den Einstellungen verbinden</a></p></section>;
 const clientName=status.clients.find(c=>String(c.id)===String(client))?.name;
 return <section className="mailbox-page">
  <PageHeading title="Gmail" description={`${status.email} · gelesen direkt aus Gmail, nichts davon wird in RauteOS gespeichert`}>
   <button type="button" className="btn btn--go" onClick={()=>setDraft({client})}>Neue E-Mail</button>
  </PageHeading>
  {notice&&<p role="status">{notice}</p>}{error&&<p className="twin-error" role="alert">{error}</p>}
  <div className="mailbox-layout">
   <aside className="mailbox-side">
    <nav aria-label="Ordner">{FOLDERS.map(([key,label])=><button key={key} type="button" aria-current={folder===key?'page':undefined} onClick={()=>{setFolder(key);setOpen('');}}>{label}</button>)}</nav>
    <h2>Kunden</h2>
    <nav aria-label="Nach Kunden filtern">
     <button type="button" aria-current={!client?'page':undefined} onClick={()=>{setClient('');setOpen('');}}>Alle E-Mails</button>
     {status.clients.map(c=><button key={c.id} type="button" aria-current={String(client)===String(c.id)?'page':undefined} onClick={()=>{setClient(String(c.id));setOpen('');}}>{c.name}</button>)}
    </nav>
   </aside>
   <div className="mailbox-list">
    <form role="search" onSubmit={e=>{e.preventDefault();setSearch(query);}}><input type="search" aria-label="E-Mails durchsuchen" placeholder={`In ${clientName||'allen E-Mails'} suchen`} value={query} onChange={e=>setQuery(e.target.value)}/></form>
    {!list?<p role="status">E-Mails werden geladen…</p>:<>
     {list.note&&<p className="mailbox-hint">{list.note} <a href={`/client/${client}/twin#kontakte`}>Kontakte pflegen</a></p>}
     <ul>{list.threads.map(t=><li key={t.id}><button type="button" className={`mailbox-row${t.unread?' is-unread':''}`} aria-current={open===t.id?'true':undefined} onClick={()=>setOpen(t.id)}>
      <span className="mailbox-row__top"><strong>{t.sender}</strong><time>{when(t.date)}</time></span>
      <span className="mailbox-row__subject">{t.subject}{t.count>1&&<small> · {t.count}</small>}</span>
      <span className="mailbox-row__snippet">{t.snippet}</span></button></li>)}</ul>
     {!list.threads.length&&!list.note&&<p className="mailbox-hint">Keine E-Mails.</p>}
     {list.next_page_token&&<button type="button" className="btn btn--quiet" onClick={()=>load(list.next_page_token)}>Ältere laden</button>}
    </>}
   </div>
   <div className="mailbox-pane">
    {draft?<Composer key={JSON.stringify(draft)} draft={draft} clients={status.clients} canSend={status.may_send} onClose={()=>setDraft(null)}
      onSent={()=>{setDraft(null);setNotice('E-Mail gesendet.');load();}}/>
     :open?<Reader id={open} client={client} onReply={setDraft}/>:<p className="mailbox-hint">Eine E-Mail auswählen oder eine neue schreiben.</p>}
   </div>
  </div>
 </section>;
}
