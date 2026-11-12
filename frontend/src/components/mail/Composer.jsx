import React,{useEffect,useRef,useState} from 'react';
import {journalistRequest as request} from '../../journalists-api.js';
import {Icon,IconButton} from './icons.jsx';
import {EmojiPopover,FormatBar,LinkPopover,RichEditor} from './RichEditor.jsx';

export const MAX_BYTES=20*1024*1024;
export const size=bytes=>bytes>1048576?`${(bytes/1048576).toFixed(1)} MB`:`${Math.max(1,Math.round(bytes/1024))} KB`;
const escape=s=>String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
export const SIGNATURE_CLASS='gm-signature';
export const signatureBlock=html=>html?`<div class="${SIGNATURE_CLASS}">-- <br>${html}</div>`:'';
const isEmpty=html=>!String(html||'').replace(/<div class="gm-signature">[\s\S]*$/,'').replace(/<[^>]+>|&nbsp;|\s/g,'');

// The client's files in the Drive folder "7. Assets", ticked to go along.
export function DriveAssets({client,selected,onChange}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{if(!client)return;setData(null);setError('');
  request(`mailbox/assets?client=${client}`).then(setData).catch(e=>setError(e.message));},[client]);
 if(!client)return <p className="gm-hint">Kunden wählen, um seine Assets aus Drive anzuhängen.</p>;
 if(error)return <p className="gm-hint" role="alert">{error}{/verbunden|Einstellungen/.test(error)&&<> <a href="/settings#drive">Drive verbinden</a></>}</p>;
 if(!data)return <p role="status" className="gm-hint">Assets werden geladen…</p>;
 const ids=selected.map(f=>f.id);
 return <fieldset className="gm-assets"><legend>Assets aus {data.folder}</legend>
  {data.files.length?data.files.map(f=><label key={f.id}><input type="checkbox" checked={ids.includes(f.id)}
   onChange={e=>onChange(e.target.checked?[...selected,f]:selected.filter(x=>x.id!==f.id))}/>
   <span>{f.name}</span><small>{f.size?size(f.size):'Google-Dokument, als PDF'}</small></label>)
   :<p className="gm-hint">Noch keine Assets im Ordner. Unter Assets „In Drive ablegen“.</p>}
 </fieldset>;
}

function read(file){
 return new Promise((resolve,reject)=>{const reader=new FileReader();
  reader.onload=()=>resolve(String(reader.result).split(',',2)[1]||'');reader.onerror=reject;reader.readAsDataURL(file);});
}

// "Neue Nachricht", as Gmail's window: docked at the bottom, to minimise,
// to enlarge, and closed into the Entwürfe unless thrown away.
export function Composer({draft={},clients=[],canSend,signature='',onClose,onSent,onToast}){
 const [form,setForm]=useState({to:'',cc:'',bcc:'',subject:'',client:'',...draft});
 const [show,setShow]=useState({cc:!!draft.cc,bcc:!!draft.bcc,format:true,drive:false,link:false,emoji:false});
 const [mode,setMode]=useState('');// '' | 'min' | 'max'
 const [uploads,setUploads]=useState([]),[drive,setDrive]=useState([]),[forwarded,setForwarded]=useState(draft.forwarded||[]);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const editor=useRef(null),files=useRef(null),images=useRef(null);
 const initial=useRef(`${draft.thread_id||draft.forwarded?'<div><br></div>':'<div><br></div><div><br></div>'}${signatureBlock(signature)}${draft.html||''}`);
 const set=key=>e=>setForm({...form,[key]:e.target.value});
 const toggle=key=>setShow(s=>({...s,[key]:!s[key],...(key==='link'?{emoji:false}:key==='emoji'?{link:false}:{})}));
 const total=uploads.reduce((n,f)=>n+f.size,0)+drive.reduce((n,f)=>n+(f.size||0),0)+forwarded.reduce((n,f)=>n+(f.size||0),0);
 const count=uploads.length+drive.length+forwarded.length;
 const title=form.thread_id?(form.subject||'Antworten'):(form.subject||'Neue Nachricht');

 function payload(){
  return {to:form.to,cc:form.cc,bcc:form.bcc,subject:form.subject,html:editor.current?.html()||'',thread_id:form.thread_id||'',
   reply_to:form.reply_to||'',references:form.references||'',drive_files:drive.map(f=>f.id),
   uploads:uploads.map(({name,mime,data})=>({name,mime,data})),forwarded:forwarded.map(({message_id,part_id})=>({message_id,part_id}))};
 }
 async function send(e){e?.preventDefault();if(!form.to.trim()){setError('Bitte mindestens eine:n Empfänger:in angeben.');return;}
  setBusy(true);setError('');
  try{await request('mailbox/send',{method:'POST',body:JSON.stringify(payload())});onSent?.();}
  catch(err){setError(err.message);}finally{setBusy(false);}}
 async function close(){
  const body=payload();
  if(canSend&&(body.to||body.subject||!isEmpty(body.html)||count)){
   try{await request('mailbox/draft',{method:'POST',body:JSON.stringify(body)});onToast?.('Entwurf gespeichert.');}
   catch(err){onToast?.(`Entwurf nicht gespeichert: ${err.message}`);}
  }
  onClose?.();
 }
 function discard(){onToast?.('Entwurf verworfen.');onClose?.();}
 async function attach(list){
  const added=[];
  for(const file of list){
   if(total+added.reduce((n,f)=>n+f.size,0)+file.size>MAX_BYTES){setError('Die Anhänge sind zusammen größer als 20 MB.');break;}
   added.push({name:file.name,mime:file.type||'application/octet-stream',size:file.size,data:await read(file)});
  }
  setUploads(u=>[...u,...added]);
 }
 function insertImages(list){
  [...list].filter(f=>/^image\//.test(f.type)).forEach(file=>{const reader=new FileReader();
   reader.onload=()=>editor.current?.insertHtml(`<img src="${reader.result}" alt="${escape(file.name)}" style="max-width:100%">`);reader.readAsDataURL(file);});
 }
 function toggleSignature(){
  const node=editor.current?.node();if(!node)return;
  const present=node.querySelector(`.${SIGNATURE_CLASS}`);
  if(present){present.remove();}else if(signature){node.insertAdjacentHTML('beforeend',signatureBlock(signature));}
  else{onToast?.('Noch keine Signatur. Unter Einstellungen › Signatur anlegen.');}
 }
 function keys(e){if((e.metaKey||e.ctrlKey)&&e.key==='Enter')send(e);}

 return <div className={`gm-compose${mode?` is-${mode}`:''}`} role="dialog" aria-label={form.thread_id?'Antworten':'Neue Nachricht'} onKeyDown={keys}>
  <header className="gm-compose__bar" onClick={()=>mode==='min'&&setMode('')}>
   <h2>{title}</h2>
   <span onClick={e=>e.stopPropagation()}>
    <IconButton icon="minimize" label={mode==='min'?'Wiederherstellen':'Minimieren'} size={18} onClick={()=>setMode(mode==='min'?'':'min')}/>
    <IconButton icon={mode==='max'?'shrink':'expand'} label={mode==='max'?'Verkleinern':'Vollbild'} size={18} onClick={()=>setMode(mode==='max'?'':'max')}/>
    <IconButton icon="close" label="Speichern und schließen" size={18} onClick={close}/>
   </span>
  </header>
  <form className="gm-compose__body" onSubmit={send} hidden={mode==='min'}>
   {error&&<p className="twin-error" role="alert">{error}</p>}
   <div className="gm-field"><label htmlFor="gm-to">An</label><input id="gm-to" value={form.to} onChange={set('to')} autoFocus={!form.to}/>
    <span className="gm-field__more">{!show.cc&&<button type="button" onClick={()=>toggle('cc')}>Cc</button>}{!show.bcc&&<button type="button" onClick={()=>toggle('bcc')}>Bcc</button>}</span></div>
   {show.cc&&<div className="gm-field"><label htmlFor="gm-cc">Cc</label><input id="gm-cc" value={form.cc} onChange={set('cc')}/></div>}
   {show.bcc&&<div className="gm-field"><label htmlFor="gm-bcc">Bcc</label><input id="gm-bcc" value={form.bcc} onChange={set('bcc')}/></div>}
   <div className="gm-field"><input aria-label="Betreff" placeholder="Betreff" value={form.subject} onChange={set('subject')}/></div>
   <RichEditor ref={editor} initialHtml={initial.current} label="Nachrichtentext"/>
   {count>0&&<ul className="gm-chips" aria-label="Anhänge">
    {[...uploads.map((f,i)=>[f,()=>setUploads(uploads.filter((_,j)=>j!==i))]),
      ...drive.map(f=>[f,()=>setDrive(drive.filter(x=>x.id!==f.id))]),
      ...forwarded.map((f,i)=>[f,()=>setForwarded(forwarded.filter((_,j)=>j!==i))])].map(([f,remove],i)=>
     <li key={i} className="gm-chip"><Icon name={f.id?'drive':'attach'} size={16}/><span>{f.name}</span>{f.size?<small>{size(f.size)}</small>:null}
      <button type="button" aria-label={`${f.name} entfernen`} onClick={remove}><Icon name="close" size={14}/></button></li>)}
   </ul>}
   {show.drive&&<div className="gm-drive">
    <label>Kunde<select value={form.client} onChange={e=>{setForm({...form,client:e.target.value});}}>
     <option value="">Kunden wählen</option>{clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    <DriveAssets client={form.client} selected={drive} onChange={setDrive}/>
   </div>}
   {show.format&&<FormatBar editor={editor}/>}
   <div className="gm-compose__acts">
    <button className="gm-send" disabled={busy||!canSend} title={canSend?'Senden (Strg+Enter)':'Das Postfach darf nicht senden'}>
     {busy?'Wird gesendet…':`Senden${count?` · ${count} ${count>1?'Anhänge':'Anhang'}`:''}`}</button>
    <IconButton icon="format" label="Formatierungsoptionen" active={show.format} onClick={()=>toggle('format')}/>
    <IconButton icon="attach" label="Dateien anhängen" onClick={()=>files.current?.click()}/>
    <input ref={files} type="file" multiple hidden onChange={e=>{attach([...e.target.files]);e.target.value='';}}/>
    <span className="gm-menu"><IconButton icon="link" label="Link einfügen" active={show.link} onMouseDown={e=>e.preventDefault()} onClick={()=>{editor.current?.remember();toggle('link');}}/>
     {show.link&&<LinkPopover editor={editor} onClose={()=>toggle('link')}/>}</span>
    <span className="gm-menu"><IconButton icon="emoji" label="Emoji einfügen" active={show.emoji} onMouseDown={e=>e.preventDefault()} onClick={()=>toggle('emoji')}/>
     {show.emoji&&<EmojiPopover editor={editor} onClose={()=>toggle('emoji')}/>}</span>
    <IconButton icon="drive" label="Kunden-Assets aus Drive" active={show.drive} onClick={()=>toggle('drive')}/>
    <IconButton icon="image" label="Bild einfügen" onClick={()=>images.current?.click()}/>
    <input ref={images} type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden onChange={e=>{insertImages(e.target.files);e.target.value='';}}/>
    <IconButton icon="edit" label="Signatur einfügen oder entfernen" onMouseDown={e=>e.preventDefault()} onClick={toggleSignature}/>
    <span className="gm-grow"/>
    {!canSend&&<span className="gm-hint">Senden braucht eine Verbindung mit Senderechten.</span>}
    <IconButton icon="trash" label="Entwurf verwerfen" onClick={discard}/>
   </div>
  </form>
 </div>;
}
