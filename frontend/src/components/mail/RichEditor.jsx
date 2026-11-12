import React,{forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {Icon,IconButton} from './icons.jsx';

// The text field of a mail, formatted the way Gmail formats it: the browser's
// own editing commands, so what is sent is the same HTML Gmail would send.
export const FONTS=[['Sans Serif','arial, sans-serif'],['Serif','"times new roman", serif'],['Feste Breite','monospace'],
 ['Breit','"arial black", sans-serif'],['Schmal','"arial narrow", sans-serif'],['Comic Sans MS','"comic sans ms", sans-serif'],
 ['Garamond','garamond, "times new roman", serif'],['Georgia','georgia, serif'],['Tahoma','tahoma, sans-serif'],
 ['Trebuchet MS','"trebuchet ms", sans-serif'],['Verdana','verdana, sans-serif']];
export const SIZES=[['Klein','1'],['Normal','3'],['Groß','4'],['Riesig','6']];
// Ink for the mail itself, not for RauteOS: the reader sees it on a white page.
const PALETTE=['#000000','#444444','#666666','#999999','#cccccc','#eeeeee','#f3f3f3','#ffffff',
 '#ff0000','#ff9900','#ffff00','#00ff00','#00ffff','#4a86e8','#0000ff','#9900ff',
 '#cc0000','#e69138','#f1c232','#6aa84f','#45818e','#3c78d8','#3d85c6','#674ea7',
 '#990000','#b45f06','#bf9000','#38761d','#134f5c','#1155cc','#0b5394','#351c75'];
const EMOJI='😀 😃 😄 😁 😊 🙂 😉 😍 😘 🤗 🤔 😐 😅 😂 🙃 😎 😢 😮 🙏 👍 👎 👏 🙌 💪 🤝 👋 ✌️ 👌 ❤️ 🎉 ✅ ❌ ⭐ 🔥 💡 📌 📎 📅 📈 📰 ☕ 🚀'.split(' ');

const keep=e=>e.preventDefault(); // a toolbar click must not take the cursor out of the text

export const RichEditor=forwardRef(function RichEditor({initialHtml='',label='Text',onInput,className=''},ref){
 const node=useRef(null),range=useRef(null);
 useEffect(()=>{if(node.current)node.current.innerHTML=initialHtml;},[]);// eslint-disable-line react-hooks/exhaustive-deps
 function remember(){const s=window.getSelection?.();if(s&&s.rangeCount&&node.current?.contains(s.anchorNode))range.current=s.getRangeAt(0).cloneRange();}
 function restore(){node.current?.focus();const s=window.getSelection?.();if(range.current&&s){s.removeAllRanges();s.addRange(range.current);}}
 function exec(command,value=null){restore();try{document.execCommand(command,false,value);}catch{/* not in this browser */}remember();onInput?.();}
 useImperativeHandle(ref,()=>({
  exec,remember,restore,
  html:()=>node.current?.innerHTML||'',
  setHtml:value=>{if(node.current){node.current.innerHTML=value;onInput?.();}},
  insertHtml:markup=>exec('insertHTML',markup),
  node:()=>node.current,
 }));
 function paste(e){
  const images=[...(e.clipboardData?.files||[])].filter(f=>/^image\/(png|jpeg|gif|webp)$/.test(f.type));
  if(!images.length)return;e.preventDefault();
  images.forEach(file=>{const reader=new FileReader();reader.onload=()=>exec('insertHTML',`<img src="${reader.result}" alt="" style="max-width:100%">`);reader.readAsDataURL(file);});
 }
 return <div ref={node} className={`gm-editor ${className}`} contentEditable suppressContentEditableWarning role="textbox" aria-multiline="true"
  aria-label={label} onKeyUp={remember} onMouseUp={remember} onBlur={remember} onInput={()=>{remember();onInput?.();}} onPaste={paste}/>;
});

function Menu({icon,label,children,open,setOpen,name,wide}){
 return <span className="gm-menu">
  <button type="button" className={`gm-ib gm-ib--menu${open===name?' is-on':''}`} aria-label={label} title={label} aria-expanded={open===name}
   onMouseDown={keep} onClick={()=>setOpen(open===name?'':name)}>{typeof icon==='string'?<Icon name={icon}/>:icon}<Icon name="down" size={16}/></button>
  {open===name&&<div className={`gm-pop${wide?' gm-pop--wide':''}`} role="menu" onMouseDown={keep}>{children}</div>}
 </span>;
}

// The formatting bar under the text, with everything Gmail's has.
export function FormatBar({editor}){
 const [open,setOpen]=useState(''),[font,setFont]=useState('Sans Serif');
 const run=(command,value)=>()=>{editor.current?.exec(command,value);setOpen('');};
 const button=(icon,label,command,value)=><IconButton icon={icon} label={label} onMouseDown={keep} onClick={run(command,value)}/>;
 return <div className="gm-format" role="toolbar" aria-label="Formatierung">
  {button('undo','Rückgängig','undo')}{button('redo','Wiederholen','redo')}<span className="gm-sep"/>
  <Menu name="font" label="Schriftart" open={open} setOpen={setOpen} icon={<span className="gm-font">{font}</span>}>
   {FONTS.map(([name,family])=><button key={name} type="button" role="menuitemradio" aria-checked={font===name} style={{fontFamily:family}}
    onClick={()=>{setFont(name);run('fontName',family)();}}>{name}</button>)}
  </Menu><span className="gm-sep"/>
  <Menu name="size" label="Schriftgröße" open={open} setOpen={setOpen} icon="size">
   {SIZES.map(([name,value])=><button key={name} type="button" role="menuitem" className={`gm-size-${value}`} onClick={run('fontSize',value)}>{name}</button>)}
  </Menu><span className="gm-sep"/>
  {button('bold','Fett','bold')}{button('italic','Kursiv','italic')}{button('underline','Unterstrichen','underline')}
  <Menu name="color" label="Textfarbe" open={open} setOpen={setOpen} icon="color" wide>
   <div className="gm-colors"><strong>Hintergrundfarbe</strong><div>{PALETTE.map(c=><button key={c} type="button" aria-label={`Hintergrund ${c}`} style={{background:c}} onClick={run('hiliteColor',c)}/>)}</div></div>
   <div className="gm-colors"><strong>Textfarbe</strong><div>{PALETTE.map(c=><button key={c} type="button" aria-label={`Text ${c}`} style={{background:c}} onClick={run('foreColor',c)}/>)}</div></div>
  </Menu><span className="gm-sep"/>
  <Menu name="align" label="Ausrichten" open={open} setOpen={setOpen} icon="alignLeft">
   <div className="gm-pop__row">{button('alignLeft','Linksbündig','justifyLeft')}{button('alignCenter','Zentriert','justifyCenter')}{button('alignRight','Rechtsbündig','justifyRight')}</div>
  </Menu>
  {button('numbered','Nummerierte Liste','insertOrderedList')}{button('bulleted','Aufzählung','insertUnorderedList')}
  {button('outdent','Einzug verkleinern','outdent')}{button('indent','Einzug vergrößern','indent')}
  {button('quote','Zitat','formatBlock','blockquote')}<span className="gm-sep"/>
  {button('strike','Durchgestrichen','strikeThrough')}{button('clear','Formatierung entfernen','removeFormat')}
 </div>;
}

export function LinkPopover({editor,onClose}){
 const [url,setUrl]=useState('https://'),[text,setText]=useState('');
 useEffect(()=>{setText(String(window.getSelection?.()||''));},[]);
 function apply(e){e.preventDefault();const safe=/^(https?:|mailto:|tel:)/i.test(url)?url:`https://${url}`;
  const label=text||safe;const escape=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  editor.current?.insertHtml(`<a href="${escape(safe)}">${escape(label)}</a>`);onClose();}
 return <form className="gm-pop gm-pop--link" onSubmit={apply} aria-label="Link einfügen">
  <label>Anzuzeigender Text<input value={text} onChange={e=>setText(e.target.value)}/></label>
  <label>Webadresse<input value={url} onChange={e=>setUrl(e.target.value)} autoFocus/></label>
  <div><button type="button" className="btn btn--quiet" onClick={onClose}>Abbrechen</button><button className="btn btn--go">OK</button></div>
 </form>;
}

export function EmojiPopover({editor,onClose}){
 return <div className="gm-pop gm-pop--emoji" role="menu" aria-label="Emoji einfügen" onMouseDown={keep}>
  {EMOJI.map(e=><button key={e} type="button" role="menuitem" onClick={()=>{editor.current?.exec('insertText',e);onClose();}}>{e}</button>)}
 </div>;
}
