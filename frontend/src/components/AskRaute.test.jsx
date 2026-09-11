import React from 'react';
import {afterEach,it,expect,vi} from 'vitest';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {AskRaute} from './AskRaute.jsx';
let sources=[];
class Stream {constructor(url){this.url=url;this.listeners={};this.close=vi.fn();sources.push(this);}addEventListener(name,callback){this.listeners[name]=callback;}emit(name,data){this.listeners[name]?.({data:JSON.stringify(data)});}}
afterEach(()=>{vi.unstubAllGlobals();sessionStorage.clear();window.history.replaceState({},'','/');sources=[];});
function setup(path='/ask?scope=asset&client_id=1&asset_type=asset&asset_id=9'){
 window.history.replaceState({},'',path);vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>[{id:1,name:'Alpha'}]}));vi.stubGlobal('EventSource',Stream);render(<AskRaute/>);
}
it('sends explicit asset context only after a question and never saves text',async()=>{
 setup();await screen.findByRole('option',{name:'Alpha'});expect(sources).toHaveLength(0);
 fireEvent.change(screen.getByLabelText('Frage'),{target:{value:'Schärfen?'}});fireEvent.click(screen.getByRole('button',{name:'Fragen'}));
 expect(sources[0].url).toContain('asset_id=9');expect(sources[0].url).toContain('scope=asset');
 sources[0].emit('text','Vorschlag zum Prüfen');sources[0].emit('done','');await screen.findByText('Vorschlag zum Prüfen');
 expect(fetch).toHaveBeenCalledTimes(1);
});
it('closes the old stream and isolates conversations when context changes',async()=>{
 setup();await screen.findByRole('option',{name:'Alpha'});fireEvent.click(screen.getByRole('button',{name:'Schärfe diesen Entwurf.'}));
 fireEvent.change(screen.getByLabelText('Kontext wechseln'),{target:{value:''}});
 expect(sources[0].close).toHaveBeenCalled();sources[0].emit('text','Late old reply');
 expect(screen.queryByText('Late old reply')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Wo fehlen Leistungen?'}));expect(sources[1].url).toContain('scope=global');expect(sources[1].url).not.toContain('asset_id');
});
it('shows a failed answer and permits another question',async()=>{
 setup('/ask');await screen.findByRole('option',{name:'Alpha'});fireEvent.click(screen.getByRole('button',{name:'Wo fehlen Leistungen?'}));sources[0].emit('error','Kontext fehlt');
 await screen.findByRole('alert');await waitFor(()=>expect(screen.getByRole('button',{name:'Fragen'}).disabled).toBe(false));
});
it('migrates the matching legacy conversation without leaking it into asset context',async()=>{
 sessionStorage.setItem('captaincomms:1',JSON.stringify([{role:'assistant',text:'Earlier mandate advice'}]));
 setup();await screen.findByRole('option',{name:'Alpha'});expect(screen.queryByText('Earlier mandate advice')).toBeNull();
 fireEvent.change(screen.getByLabelText('Kontext wechseln'),{target:{value:''}});
 fireEvent.change(screen.getByLabelText('Kontext wechseln'),{target:{value:'1'}});
 await screen.findByText('Earlier mandate advice');expect(sessionStorage.getItem('captaincomms:1')).toBeNull();
});
it('dictates for review, stops on Escape and rejects late recognition after context changes',async()=>{
 let mic;class Recognition{constructor(){mic=this;this.abort=vi.fn();}start(){}}
 vi.stubGlobal('SpeechRecognition',Recognition);setup('/ask');await screen.findByRole('option',{name:'Alpha'});
 fireEvent.click(screen.getByRole('button',{name:'Frage diktieren'}));act(()=>mic.onresult({results:[[{transcript:'Meine diktierte Frage'}]]}));
 expect(screen.getByLabelText('Frage').value).toBe('Meine diktierte Frage');expect(sources).toHaveLength(0);
 fireEvent.keyDown(document,{key:'Escape'});expect(mic.abort).toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Kontext wechseln'),{target:{value:'1'}});mic.onresult({results:[[{transcript:'Late recognition'}]]});
 expect(screen.getByLabelText('Frage').value).not.toBe('Late recognition');
});
