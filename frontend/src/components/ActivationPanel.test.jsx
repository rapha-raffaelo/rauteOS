import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {ActivationPanel} from './ActivationPanel.jsx';
const response=(body,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
const formats=[{key:'kundenmail',label:'Kundenmail'},{key:'pitch',label:'Journalistenpitch'},{key:'custom',label:'Eigene Aktion'}];
const text={id:1,type:'asset',kind:'kundenmail',title:'Vorschlag',body:'400 % THG-Minderung',digest:'a'.repeat(64),released_at:null,
 quality_stale:false,quality:{status:'complete',warnings:1,note:'Keine unabhängige Verifikation.',findings:[{quote:'400 % THG-Minderung',classification:'Client Statement',reason:'Client questionnaire',warnings:['Nicht unabhängig bestätigt'],statement_ids:[2],source_ids:[],contradiction_ids:[],no_go_rules:[]}]},
 evidence_statements:[{id:2,value:'400 % THG-Minderung',evidence_type:'Client Statement',source_title:'Questionnaire'}],evidence_sources:[]};
const data={formats,texts:[text],latest:null};
afterEach(()=>vi.unstubAllGlobals());
it('defaults to the customer email and does not write on load',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({...data,texts:[]})).mockResolvedValue(response({id:1,status:'running'}));
 vi.stubGlobal('fetch',fetch);render(<ActivationPanel clientId={1} kind="developed" identity={1}/>);
 expect((await screen.findByLabelText('Format')).value).toBe('kundenmail');expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.click(screen.getByRole('button',{name:'Entwurf erstellen'}));await screen.findByText('In Arbeit');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({kind:'kundenmail',contact_id:null,instruction:''});
});
it('shows the client-claim warning alongside its source',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response(data)));render(<ActivationPanel clientId={1} kind="developed" identity={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Aussage für Aussage prüfen'}));
 expect(screen.getByText('Client Statement')).toBeTruthy();expect(screen.getByText('Nicht unabhängig bestätigt')).toBeTruthy();
 expect(screen.getByText(/Profil: 400 % THG-Minderung/)).toBeTruthy();
});
it('marks a locally edited text as needing another check',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response(data)));render(<ActivationPanel clientId={1} kind="developed" identity={1}/>);
 fireEvent.change(await screen.findByLabelText('Text 1'),{target:{value:'A new assertion'}});
 expect(screen.getByText('Prüfung veraltet oder ausstehend')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Aussagen prüfen'}).disabled).toBe(true);
});
it('retains edits when another writer has changed the draft',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValue(response({detail:'Text wurde inzwischen geändert.'},409)));
 render(<ActivationPanel clientId={1} kind="developed" identity={1}/>);
 fireEvent.change(await screen.findByLabelText('Text 1'),{target:{value:'My correction'}});
 fireEvent.click(screen.getByRole('button',{name:'Änderungen speichern'}));await screen.findByRole('alert');
 expect(screen.getByLabelText('Text 1').value).toBe('My correction');
});
it('only offers selected journalists for a pitch and clears recipient from a customer email',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({...data,texts:[]})).mockResolvedValue(response({id:1,status:'running'}));
 vi.stubGlobal('fetch',fetch);render(<ActivationPanel clientId={1} kind="developed" identity={1} contacts={[{id:9,name:'Anna',outlet:'Paper'}]}/>);
 fireEvent.change(await screen.findByLabelText('Format'),{target:{value:'pitch'}});
 fireEvent.change(screen.getByLabelText('Journalist für diesen Text'),{target:{value:'9'}});
 fireEvent.change(screen.getByLabelText('Format'),{target:{value:'kundenmail'}});
 fireEvent.click(screen.getByRole('button',{name:'Entwurf erstellen'}));await screen.findByText('In Arbeit');
 expect(JSON.parse(fetch.mock.calls[1][1].body).contact_id).toBeNull();
});
