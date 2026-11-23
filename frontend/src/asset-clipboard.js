// A single rich document plus plain text lets the destination choose the format.
// Images are embedded: copied documents must not depend on a rauteOS login.
function escapeHtml(value){
 return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function dataUrl(blob){
 return new Promise((resolve,reject)=>{
  const reader=new FileReader();
  reader.onload=()=>resolve(reader.result);
  reader.onerror=()=>reject(new Error('Logo konnte nicht gelesen werden.'));
  reader.readAsDataURL(blob);
 });
}

async function embeddedLogo(src){
 if(/^data:image\/(?:png|jpe?g|gif|webp|x-icon);base64,/i.test(src))return src;
 const url=new URL(src,window.location.href);
 if(!['https:','http:'].includes(url.protocol))throw new Error('Logo nicht verfügbar.');
 const controller=new AbortController();
 const timeout=setTimeout(()=>controller.abort(),8000);
 try{
  const response=await fetch(url.href,{credentials:'same-origin',signal:controller.signal});
  if(!response.ok)throw new Error('Logo nicht verfügbar.');
  const blob=await response.blob();
  if(!/^image\/(?:png|jpe?g|gif|webp|x-icon)$/i.test(blob.type))throw new Error('Logo nicht verfügbar.');
  return await dataUrl(blob);
 }finally{clearTimeout(timeout);}
}

async function htmlDocument({title,body,logoSrc,logoAlt,logoSize}){
 const logo=logoSrc?await embeddedLogo(logoSrc):'';
 const scale=logoSize?.width>0&&logoSize?.height>0?Math.min(180/logoSize.width,80/logoSize.height,1):null;
 const width=scale?Math.max(1,Math.round(logoSize.width*scale)):160;
 const height=scale?` height="${Math.max(1,Math.round(logoSize.height*scale))}"`:'';
 const paragraphs=String(body??'').replace(/\r\n?/g,'\n').split(/\n[\t ]*\n/)
  .map(paragraph=>`<p style="margin:0 0 14px;line-height:1.5;">${escapeHtml(paragraph).replace(/\n/g,'<br>')}</p>`).join('');
 return new Blob([`<html><head><meta charset="utf-8"></head><body><div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#22232d;">${logo?`<p style="margin:0 0 24px;"><img src="${escapeHtml(logo)}" alt="${escapeHtml(logoAlt||'Logo')}" width="${width}"${height} style="display:block;max-width:180px;max-height:80px;object-fit:contain;"></p>`:''}${title?`<h1 style="font-size:22px;line-height:1.3;margin:0 0 18px;">${escapeHtml(title)}</h1>`:''}${paragraphs}</div></body></html>`],{type:'text/html'});
}

export async function copyAsset({title,body,logoSrc='',logoAlt='',logoSize}){
 const plain=title?`${title}\n\n${body}`:body;
 if(navigator.clipboard?.write&&typeof ClipboardItem!=='undefined'){
  try{
   const html=htmlDocument({title,body,logoSrc,logoAlt,logoSize});
   // A browser can reject write() before consuming its representations.
   html.catch(()=>{});
   // Do not await image loading here: Safari requires write() during the click.
   await navigator.clipboard.write([new ClipboardItem({
    'text/html':html,
    'text/plain':new Blob([plain],{type:'text/plain'}),
   })]);
   return {rich:true,withLogo:Boolean(logoSrc)};
  }catch{/* Try plain text, but never report the logo as successfully copied. */}
 }
 if(!navigator.clipboard?.writeText)throw new Error('Kopieren nicht verfügbar.');
 await navigator.clipboard.writeText(plain);
 return {rich:false,withLogo:false};
}
