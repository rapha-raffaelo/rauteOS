import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {Editor} from './AssetsPage.jsx';

const clientLogo='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=';
const originalClipboard=Object.getOwnPropertyDescriptor(navigator,'clipboard');
let clipboard;

beforeEach(()=>{
 localStorage.clear();
 clipboard={write:vi.fn(async items=>{for(const item of items)await Promise.all(Object.values(item.data));}),writeText:vi.fn().mockResolvedValue()};
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:clipboard});
 vi.stubGlobal('ClipboardItem',class {constructor(data){this.data=data;} static supports(){return true;}});
});
afterEach(()=>{
 cleanup();vi.unstubAllGlobals();localStorage.clear();
 if(originalClipboard)Object.defineProperty(navigator,'clipboard',originalClipboard);else delete navigator.clipboard;
});

function editor(){
 const text={id:81,type:'asset',kind:'pressemitteilung',title:'Originaltitel',body:'Originaltext',digest:'d',released_at:null};
 render(<Editor text={text} path="unused" client={{name:'Beispiel & Partner',logo:clientLogo}} onSaved={()=>{}}/>);
}
function blobText(blob){
 if(blob.text)return blob.text();
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(blob);});
}
async function copied(type){
 await waitFor(()=>expect(clipboard.write).toHaveBeenCalledTimes(1));
 return blobText(await clipboard.write.mock.calls[0][0][0].data[type]);
}

it('copies the selected client logo with the current unsaved title and paragraphs as rich and plain text',async()=>{
 editor();
 fireEvent.change(screen.getByRole('textbox',{name:'Titel'}),{target:{value:'Neue Meldung & Details'}});
 fireEvent.change(screen.getByRole('textbox',{name:'Text'}),{target:{value:'Erster Absatz.\n\nZweiter Absatz.'}});
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 const html=await copied('text/html'),plain=await copied('text/plain');
 const doc=new DOMParser().parseFromString(html,'text/html');
 expect(doc.querySelector('img')?.getAttribute('src')).toBe(clientLogo);
 expect(doc.body.textContent).toContain('Neue Meldung & Details');
 expect(doc.body.textContent).toContain('Erster Absatz.');
 expect(doc.body.textContent).toContain('Zweiter Absatz.');
 expect(plain).toBe('Neue Meldung & Details\n\nErster Absatz.\n\nZweiter Absatz.');
 expect(clipboard.writeText).not.toHaveBeenCalled();
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/Logo/));
});

it('embeds the selected raute logo instead of the client logo',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,blob:async()=>new Blob(['raute-image'],{type:'image/jpeg'})}));
 editor();
 fireEvent.click(screen.getByRole('button',{name:'raute+kopf'}));
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 const doc=new DOMParser().parseFromString(await copied('text/html'),'text/html');
 const image=doc.querySelector('img');
 expect(image?.getAttribute('src')).toMatch(/^data:image\//);
 expect(image?.getAttribute('src')).not.toBe(clientLogo);
 expect(image?.getAttribute('alt')).toContain('raute+kopf');
 expect(fetch.mock.calls[0][0]).toContain('/static/brand/raute-kopf.jpg');
});

it('starts the clipboard write during the click while the logo is still loading',async()=>{
 let resolveLogo;
 vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>{resolveLogo=resolve;})));
 editor();fireEvent.click(screen.getByRole('button',{name:'raute+kopf'}));
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 // Safari requires the write itself to begin in the user gesture; image bytes
 // may finish later through the promised ClipboardItem representation.
 expect(clipboard.write).toHaveBeenCalledTimes(1);
 resolveLogo({ok:true,blob:async()=>new Blob(['raute-image'],{type:'image/jpeg'})});
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/Logo/));
});

it('leaves the logo out when Ohne is selected',async()=>{
 editor();fireEvent.click(screen.getByRole('button',{name:'Ohne'}));
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/kopiert/));
 if(clipboard.write.mock.calls.length){
  const doc=new DOMParser().parseFromString(await copied('text/html'),'text/html');
  expect(doc.querySelector('img')).toBeNull();
  expect(await copied('text/plain')).toBe('Originaltitel\n\nOriginaltext');
 }else expect(clipboard.writeText).toHaveBeenCalledWith('Originaltitel\n\nOriginaltext');
});

it('treats title and body markup as text rather than executable clipboard HTML',async()=>{
 editor();
 fireEvent.change(screen.getByRole('textbox',{name:'Titel'}),{target:{value:'<img src=x onerror=alert(1)> & Titel'}});
 fireEvent.change(screen.getByRole('textbox',{name:'Text'}),{target:{value:'<script>alert(1)</script>\n<a href="javascript:alert(1)">Link</a>'}});
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 const doc=new DOMParser().parseFromString(await copied('text/html'),'text/html');
 expect(doc.querySelectorAll('img')).toHaveLength(1);
 expect(doc.querySelector('script,a,[onerror]')).toBeNull();
 expect(doc.body.textContent).toContain('<img src=x onerror=alert(1)> & Titel');
 expect(doc.body.textContent).toContain('<script>alert(1)</script>');
});

it('copies the text and explains the missing logo when rich clipboard is unavailable',async()=>{
 vi.stubGlobal('ClipboardItem',undefined);editor();
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 await waitFor(()=>expect(clipboard.writeText).toHaveBeenCalledWith('Originaltitel\n\nOriginaltext'));
 expect(clipboard.write).not.toHaveBeenCalled();
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/Logo/));
 expect(screen.getByRole('status').textContent).toMatch(/ohne|nicht/i);
});

it('falls back to plain text without claiming the logo was copied when rich copying fails',async()=>{
 clipboard.write.mockRejectedValue(new Error('NotAllowedError'));editor();
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 await waitFor(()=>expect(clipboard.writeText).toHaveBeenCalledWith('Originaltitel\n\nOriginaltext'));
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/Logo/));
 expect(screen.getByRole('status').textContent).toMatch(/ohne|nicht/i);
});

it('preserves copyable text and reports a logo download failure',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:404}));
 editor();fireEvent.click(screen.getByRole('button',{name:'raute+kopf'}));
 fireEvent.click(screen.getByRole('button',{name:'Kopieren'}));
 await waitFor(()=>expect(clipboard.writeText).toHaveBeenCalledWith('Originaltitel\n\nOriginaltext'));
 await waitFor(()=>expect(screen.getByRole('status').textContent).toMatch(/Logo/));
 expect(screen.getByRole('status').textContent).toMatch(/ohne|nicht/i);
});
