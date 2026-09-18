import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {TwinAIImport} from './TwinAIImport.jsx';
const response=value=>({ok:true,headers:new Headers({'content-type':'application/json'}),json:async()=>value});
const fields=[{key:'A01.01',label:'Name?',section:'Unternehmen'}];
const preview={id:'preview',unanswered:2,rows:[{index:0,data:{key:'A01.01',value:'Company GmbH'},message:'From source',sources:[{id:'input',title:'Deck',text:'Company GmbH',url:''}]}]};
afterEach(()=>vi.unstubAllGlobals());
it('starts only after explicit submission and sends chosen source context',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({job:null,preview:null})).mockResolvedValueOnce(response({status:'running',note:'Quellen werden ausgewertet.'}));vi.stubGlobal('fetch',fetch);
 render(<TwinAIImport clientId={1} fields={fields} onImported={()=>{}}/>);
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(1));
 fireEvent.change(screen.getByLabelText('Quelltext ergänzen (optional)'),{target:{value:'Our supplied source'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'Öffentliche Unternehmensinformationen recherchieren'}));
 fireEvent.click(screen.getByRole('button',{name:'Antwortvorschläge erstellen'}));await screen.findByRole('status');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({text:'Our supplied source',source_title:'',section:'',web:false});
 expect(screen.getByRole('button',{name:'KI wertet die Quellen aus…'}).disabled).toBe(true);
});
it('restores review but requires selection before committing the saved preview',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({job:{status:'complete',note:'Ready'},preview})).mockResolvedValueOnce(response({created:1,skipped:0}));vi.stubGlobal('fetch',fetch);const imported=vi.fn();
 render(<TwinAIImport clientId={1} fields={fields} onImported={imported}/>);
 await screen.findByText('1 Vorschläge zur Prüfung');expect(screen.getByRole('button',{name:'0 geprüfte Antworten übernehmen'}).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'A01.01 · Name?'}));fireEvent.click(screen.getByRole('button',{name:'1 geprüfte Antworten übernehmen'}));
 await waitFor(()=>expect(imported).toHaveBeenCalledWith({created:1,skipped:0}));expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({preview_id:'preview',selected:[0]});
});
it('shows an import failure as an alert and retries only on explicit request',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({job:{status:'failed',error_code:'invalid_response',note:'Keine gültigen Antwortvorschläge.'},preview:null})).mockResolvedValueOnce(response({status:'running',note:'Quellen werden ausgewertet.'}));
 vi.stubGlobal('fetch',fetch);render(<TwinAIImport clientId={1} fields={fields} onImported={()=>{}}/>);
 expect((await screen.findByRole('alert')).textContent).toBe('Keine gültigen Antwortvorschläge.');expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.change(screen.getByLabelText('Quelltext ergänzen (optional)'),{target:{value:'Preserve my context'}});
 fireEvent.click(screen.getByRole('button',{name:'Erneut versuchen'}));await screen.findByRole('status');
 expect(screen.queryByRole('alert')).toBeNull();expect(JSON.parse(fetch.mock.calls[1][1].body).text).toBe('Preserve my context');
 expect(screen.getByRole('button',{name:'KI wertet die Quellen aus…'}).disabled).toBe(true);
});
it('blocks submission until the persisted job is restored and shows real batch progress',async()=>{
 let restore;
 const fetch=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>{restore=resolve;}));
 vi.stubGlobal('fetch',fetch);render(<TwinAIImport clientId={1} fields={fields} onImported={()=>{}}/>);
 const button=screen.getByRole('button',{name:'Importstatus wird geladen…'});
 expect(button.disabled).toBe(true);fireEvent.click(button);expect(fetch).toHaveBeenCalledTimes(1);
 restore(response({job:{status:'running',total_batches:6,completed_batches:2,note:'Fragenpaket 3 von 6 wird bearbeitet.'},preview:null}));
 const progress=await screen.findByRole('progressbar',{name:'Fortschritt des KI-Imports'});
 expect(progress.value).toBe(2);expect(progress.max).toBe(7);
 expect(screen.getByRole('button',{name:'KI wertet die Quellen aus…'}).disabled).toBe(true);
 expect(screen.getByRole('status').textContent).toContain('Fragenpaket 3 von 6');
});
