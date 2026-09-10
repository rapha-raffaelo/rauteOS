import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { TwinPage, ImportPanel } from './TwinPage.jsx';

const options = {evidence_type:['Client Statement','Fact'],source_type:['Other','Public Database'],confidence:['Unknown','High'],
 confidentiality:['Client Confidential','Public'],external_use:['Approval Required','Allowed'],fact_status:['Needs Verification','Vollständig','Rejected'],input_owner:['RAUTE']};
const row = {id:3,key:'A02.01',value:'400 % THG-Minderung',revision:4,source_title:'Company questionnaire',source_url:'',
 evidence_type:'Client Statement',source_type:'Other',confidence:'Unknown',confidentiality:'Client Confidential',external_use:'Approval Required',
 fact_status:'Needs Verification',input_owner:'RAUTE',as_of:null,note:'',verification_note:'',verified_at:null};
const data = {client:{id:1,name:'Demo'},fields:[{key:'A02.01',label:'Was verkauft das Unternehmen?',section:'Client Facts',group:'A02 Angebot',requirement:'Pflicht'}],
 statements:[row],progress:{percent:1,required_filled:1,required_total:127,verified:0,missing:[]},options};
const response = (body, status=200) => ({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
afterEach(()=>vi.unstubAllGlobals());

it('edits a statement by id and revision without flattening its evidence', async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValueOnce(response({...row,value:'Revised',revision:5})).mockResolvedValue(response({...data,statements:[{...row,value:'Revised',revision:5}]}));
 vi.stubGlobal('fetch',fetch); render(<TwinPage clientId={1}/>);
 await screen.findByText(row.value);
 expect(screen.getByText('Nicht unabhängig bestätigt')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Bearbeiten'}));
 fireEvent.change(screen.getByLabelText('Aussage'),{target:{value:'Revised'}});
 fireEvent.click(screen.getByRole('button',{name:'Aussage speichern'}));
 await screen.findByText('Revised');
 expect(fetch.mock.calls[1][0]).toBe('/api/v1/clients/1/twin/statements/3');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({value:'Revised',revision:4,evidence_type:'Client Statement'});
});

it('keeps unsaved text visible after a conflict',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValue(response({detail:'Aussage wurde inzwischen geändert.'},409)));
 render(<TwinPage clientId={1}/>); fireEvent.click(await screen.findByRole('button',{name:'Bearbeiten'}));
 fireEvent.change(screen.getByLabelText('Aussage'),{target:{value:'My unsaved correction'}});
 fireEvent.click(screen.getByRole('button',{name:'Aussage speichern'}));
 await screen.findByRole('alert');
 expect(screen.getByLabelText('Aussage').value).toBe('My unsaved correction');
});

it('rejects only the selected statement with its revision',async()=>{
 const fetch=vi.fn().mockResolvedValue(response(data));vi.stubGlobal('fetch',fetch);
 render(<TwinPage clientId={1}/>);fireEvent.click(await screen.findByRole('button',{name:'Verwerfen'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3));
 expect(fetch.mock.calls[1][0]).toContain('/statements/3/reject');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({revision:4,note:''});
});

it('never imports on file selection or preview; sends only checked rows',async()=>{
 const preview={id:'preview-1',mapping:{key:'ID',value:'Answer'},columns:['ID','Answer'],rows:[
  {index:0,state:'ready',sheet:'CSV',line:2,data:{key:'A02.01',value:'First'}},
  {index:1,state:'ready',sheet:'CSV',line:3,data:{key:'A02.01',value:'Second'}}]};
 const fetch=vi.fn().mockResolvedValueOnce(response(preview)).mockResolvedValueOnce(response({created:1,skipped:0}));
 vi.stubGlobal('fetch',fetch);const imported=vi.fn();render(<ImportPanel clientId={1} onImported={imported}/>);
 fireEvent.change(screen.getByLabelText('Datei'),{target:{files:[new File(['ID,Answer\nA02.01,First'],'q.csv')]}});
 expect(fetch).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Vorschau erstellen'}));await screen.findByText('First');
 expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.click(screen.getAllByRole('checkbox')[1]);
 fireEvent.click(screen.getByRole('button',{name:'Ausgewählte Aussagen importieren'}));
 await waitFor(()=>expect(imported).toHaveBeenCalled());
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({preview_id:'preview-1',selected:[0]});
});

it('requires a new preview after changing column mapping',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response({id:'p',mapping:{key:'ID',value:'Answer'},columns:['ID','Answer'],
 rows:[{index:0,state:'ready',sheet:'CSV',line:2,data:{key:'A02.01',value:'First'}}]})));
 render(<ImportPanel clientId={1} onImported={()=>{}}/>);
 fireEvent.change(screen.getByLabelText('Datei'),{target:{files:[new File(['x'],'q.csv')]}});
 fireEvent.click(screen.getByRole('button',{name:'Vorschau erstellen'}));await screen.findByText('First');
 fireEvent.change(screen.getByLabelText('Antwort'),{target:{value:'ID'}});
 expect(screen.getByRole('button',{name:'Ausgewählte Aussagen importieren'}).disabled).toBe(true);
});
