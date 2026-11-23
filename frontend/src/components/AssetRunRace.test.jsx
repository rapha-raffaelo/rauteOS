import React from 'react';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {Workspace} from './AssetsPage.jsx';
import {ActivationPanel} from './ActivationPanel.jsx';

const json=body=>({ok:true,headers:{get:()=>'application/json'},json:async()=>body});
const detail={revision:1,status:'active',title:'Ein Thema',storyline:'Ein konkreter Ansatz',contact_ids:[],contacts:[],people:[],speaker_statement_id:null};
const formats=[{key:'kundenmail',label:'Kundenmail'},{key:'pitch',label:'Pitch'}];
const text=id=>({id,type:'asset',kind:'kundenmail',title:`Entwurf ${id}`,body:`Inhalt ${id}`,digest:String(id).repeat(64),stage:'offen',released_at:null,quality:{}});
const complete=id=>({formats,texts:Array.from({length:id},(_,i)=>text(id-i)),latest:{id,status:'complete',kind:'kundenmail',started_at:new Date().toISOString()}});
let timers;
beforeEach(()=>{
 timers=[];
 const setInterval=globalThis.setInterval;
 vi.spyOn(globalThis,'setInterval').mockImplementation((fn,delay,...args)=>{if(delay===2500){timers.push(fn);return 0;}return setInterval(fn,delay,...args);});
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
function requests(){
 let initial=true,submitted=0;const pending=[];
 vi.stubGlobal('fetch',vi.fn((url,options={})=>{
  if(options.method==='POST')return Promise.resolve(json({id:++submitted,status:'running'}));
  if(!url.endsWith('/activation'))return Promise.resolve(json(detail));
  if(initial){initial=false;return Promise.resolve(json({formats,texts:[],latest:null}));}
  return new Promise(resolve=>pending.push(body=>resolve(json(body))));
 }));
 return pending;
}

it('keeps a second asset running when older polling and context-refresh responses arrive',async()=>{
 const pending=requests(),completed=vi.fn();
 const {rerender}=render(<Workspace clientId={1} kind="developed" identity={7} contextRevision={1} onCompleted={completed}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 fireEvent.click(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}));
 await waitFor(()=>expect(timers).toHaveLength(1));
 act(()=>{timers[0]();timers[0]();});
 expect(pending).toHaveLength(2);
 await act(async()=>{pending[0](complete(1));});
 await waitFor(()=>expect(completed).toHaveBeenCalledTimes(1));
 expect(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}).disabled).toBe(false);
 // An independently refreshed workspace response is still in flight when the
 // next POST is accepted. It must not cancel the new run either.
 rerender(<Workspace clientId={1} kind="developed" identity={7} contextRevision={2} onCompleted={completed}/>);
 await waitFor(()=>expect(pending).toHaveLength(3));
 await act(async()=>{pending[2]({...complete(1),latest:{...complete(1).latest,status:'running'}});});
 expect(screen.queryByRole('dialog')).toBeNull();
 expect(completed).toHaveBeenCalledTimes(1);
 rerender(<Workspace clientId={1} kind="developed" identity={7} contextRevision={3} onCompleted={completed}/>);
 await waitFor(()=>expect(pending).toHaveLength(4));
 fireEvent.click(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}));
 await waitFor(()=>expect(timers).toHaveLength(2));
 await act(async()=>{pending[1](complete(1));pending[3](complete(1));});
 expect(screen.getByRole('dialog',{name:'RAUTE schreibt Kundenmail…'})).toBeTruthy();
 expect(completed).toHaveBeenCalledTimes(1);
 act(()=>{timers[1]();});
 await act(async()=>{pending[4](complete(2));});
 await waitFor(()=>expect(completed).toHaveBeenCalledTimes(2));
 expect(screen.queryByRole('dialog')).toBeNull();
 expect(screen.getByLabelText('Text').value).toBe('Inhalt 2');
 expect(screen.getByRole('button',{name:'Entwurf 1 in den Papierkorb'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'Entwurf 2 in den Papierkorb'})).toBeTruthy();
});

it('keeps the next activation-panel run active after an old completion arrives',async()=>{
 const pending=requests(),completed=vi.fn();
 render(<ActivationPanel clientId={1} kind="developed" identity={7} onCompleted={completed}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Entwurf erstellen'}));
 await waitFor(()=>expect(timers).toHaveLength(1));
 act(()=>{timers[0]();timers[0]();});
 await act(async()=>{pending[0](complete(1));});
 await waitFor(()=>expect(completed).toHaveBeenCalledTimes(1));
 // Open the new-text form after the first result was selected.
 fireEvent.click(screen.getByText('Weiteren Text erstellen'));
 fireEvent.click(screen.getByRole('button',{name:'Entwurf erstellen'}));
 await waitFor(()=>expect(timers).toHaveLength(2));
 await act(async()=>{pending[1](complete(1));});
 expect(screen.getByRole('button',{name:'Text wird erstellt…'}).disabled).toBe(true);
 expect(screen.getByRole('status').textContent).toBe('In Arbeit');
 expect(completed).toHaveBeenCalledTimes(1);
 act(()=>{timers[1]();});
 await act(async()=>{pending[2](complete(2));});
 await waitFor(()=>expect(completed).toHaveBeenCalledTimes(2));
 expect(screen.getByLabelText('Gespeicherter Text').value).toBe('asset-2');
});
