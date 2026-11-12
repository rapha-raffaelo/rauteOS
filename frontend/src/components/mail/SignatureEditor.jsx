import React,{useEffect,useRef,useState} from 'react';
import {journalistRequest as request} from '../../journalists-api.js';
import {FormatBar,LinkPopover,RichEditor} from './RichEditor.jsx';
import {IconButton} from './icons.jsx';

// The signature under every new mail and reply, written as formatted text
// like the mail itself. Kept in RauteOS, cleaned of anything that could run.
export function SignatureEditor({initialHtml}){
 const [html,setHtml]=useState(initialHtml??null),[state,setState]=useState(''),[link,setLink]=useState(false);
 const editor=useRef(null),images=useRef(null);
 useEffect(()=>{if(initialHtml!=null)return;request('mailbox/signature').then(v=>setHtml(v.html||'')).catch(e=>{setHtml('');setState(e.message);});},[]);// eslint-disable-line react-hooks/exhaustive-deps
 async function save(){setState('saving');
  try{const v=await request('mailbox/signature',{method:'PUT',body:JSON.stringify({html:editor.current?.html()||''})});
   editor.current?.setHtml(v.html);setState('saved');}catch(e){setState(e.message);}}
 function image(list){[...list].forEach(file=>{const reader=new FileReader();
  reader.onload=()=>editor.current?.insertHtml(`<img src="${reader.result}" alt="" style="max-width:240px">`);reader.readAsDataURL(file);});}
 if(html===null)return <p role="status">Signatur wird geladen…</p>;
 return <div className="gm-signature-edit">
  <p className="gm-hint">Steht unter jeder neuen E-Mail und jeder Antwort im Gmail-Bereich. Im Schreibfenster lässt sie sich mit dem Stift entfernen oder wieder einfügen.</p>
  <FormatBar editor={editor}/>
  <RichEditor ref={editor} initialHtml={html} label="Signatur" onInput={()=>state==='saved'&&setState('')}/>
  <div>
   <button type="button" className="btn btn--go" onClick={save} disabled={state==='saving'}>{state==='saving'?'Wird gespeichert…':'Signatur speichern'}</button>
   <span className="gm-menu"><IconButton icon="link" label="Link einfügen" onMouseDown={e=>e.preventDefault()} onClick={()=>{editor.current?.remember();setLink(!link);}}/>
    {link&&<LinkPopover editor={editor} onClose={()=>setLink(false)}/>}</span>
   <IconButton icon="image" label="Bild oder Logo einfügen" onClick={()=>images.current?.click()}/>
   <input ref={images} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden onChange={e=>{image(e.target.files);e.target.value='';}}/>
   {state==='saved'&&<span role="status" className="gm-hint">Gespeichert.</span>}
   {state&&!['saving','saved'].includes(state)&&<span role="alert" className="twin-error">{state}</span>}
  </div>
 </div>;
}
