import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { TwinPage, ImportPanel } from './TwinPage.jsx';

const options = {evidence_type:['Client Statement','Fact'],source_type:['Other','Public Database'],confidence:['Unknown','High'],
 confidentiality:['Client Confidential','Public'],external_use:['Approval Required','Allowed'],fact_status:['Needs Verification','Vollständig','Rejected'],input_owner:['RAUTE']};
const row = {id:3,key:'R02.01',value:'400 % THG-Minderung',revision:4,source_title:'Company questionnaire',source_url:'',
 evidence_type:'Client Statement',source_type:'Other',confidence:'Unknown',confidentiality:'Client Confidential',external_use:'Approval Required',
 fact_status:'Needs Verification',input_owner:'RAUTE',as_of:null,note:'',verification_note:'',verified_at:null};
const data = {client:{id:1,name:'Demo'},fields:[{key:'R02.01',label:'Rechtliche Unternehmensdaten',section:'R. Onboarding-Recherche',group:'R01 Öffentliches Unternehmensbild',requirement:'Optional',hint:'Welche Rechtsform hat das Unternehmen?'}],
 statements:[row],progress:{percent:1,required_filled:1,required_total:43,verified:0,missing:[]},options};
const response = (body, status=200) => ({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
afterEach(()=>vi.unstubAllGlobals());
const stubFetch=fetch=>vi.stubGlobal('fetch',(url,options)=>url.endsWith('/onboarding-audio')?Promise.resolve(response([])):url.endsWith('/ai-import')?Promise.resolve(response({job:null,preview:null})):fetch(url,options));

it('edits a statement by id and revision without flattening its evidence', async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValueOnce(response({...row,value:'Revised',revision:5})).mockResolvedValue(response({...data,statements:[{...row,value:'Revised',revision:5}]}));
 stubFetch(fetch); render(<TwinPage clientId={1}/>);
 await screen.findByText(row.value);
 expect(screen.queryByRole('img',{name:'Vom Kunden noch nicht bestätigt'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Bearbeiten'}));
 fireEvent.change(screen.getByLabelText('Aussage'),{target:{value:'Revised'}});
 fireEvent.click(screen.getByRole('button',{name:'Aussage speichern'}));
 await screen.findByText('Revised');
 expect(fetch.mock.calls[1][0]).toBe('/api/v1/clients/1/twin/statements/3');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({value:'Revised',revision:4,evidence_type:'Client Statement'});
});

it('keeps unsaved text visible after a conflict',async()=>{
 stubFetch(vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValue(response({detail:'Aussage wurde inzwischen geändert.'},409)));
 render(<TwinPage clientId={1}/>); fireEvent.click(await screen.findByRole('button',{name:'Bearbeiten'}));
 fireEvent.change(screen.getByLabelText('Aussage'),{target:{value:'My unsaved correction'}});
 fireEvent.click(screen.getByRole('button',{name:'Aussage speichern'}));
 await screen.findByRole('alert');
 expect(screen.getByLabelText('Aussage').value).toBe('My unsaved correction');
});

it('shows an answer with its source and one edit button, and clips a long one',async()=>{
 const long={...row,value:'Lang '.repeat(80),source_url:'https://zenchef.com/de/impressum',
  note:'Weitere Quellen: https://zenchef.com/a, https://blog.zenchef.com/b, https://frenchweb.fr/c'};
 stubFetch(vi.fn().mockResolvedValue(response({...data,statements:[long]})));
 render(<TwinPage clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Mehr anzeigen'}));
 expect(screen.getByRole('button',{name:'Weniger anzeigen'})).toBeTruthy();
 expect(screen.getByRole('link',{name:'zenchef.com'})).toBeTruthy();
 // The same site twice is one source; the others are counted, not listed.
 expect(screen.getByText('+2 Quellen')).toBeTruthy();
 expect(screen.queryByText('Weitere Aktionen')).toBeNull();
 expect(screen.queryByRole('button',{name:'Weitere Aussage'})).toBeNull();
 expect(screen.getAllByRole('button',{name:'Bearbeiten'})).toHaveLength(1);
});

it('never imports on file selection or preview; sends only checked rows',async()=>{
 const preview={id:'preview-1',mapping:{key:'ID',value:'Answer'},columns:['ID','Answer'],rows:[
  {index:0,state:'ready',sheet:'CSV',line:2,data:{key:'A02.01',value:'First'}},
  {index:1,state:'ready',sheet:'CSV',line:3,data:{key:'A02.01',value:'Second'}}]};
 const fetch=vi.fn().mockResolvedValueOnce(response(preview)).mockResolvedValueOnce(response({created:1,skipped:0}));
 stubFetch(fetch);const imported=vi.fn();render(<ImportPanel clientId={1} onImported={imported}/>);
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
it('edits in the field and keeps permission values when using the compact form',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response(data)).mockResolvedValueOnce(response(row)).mockResolvedValue(response(data));
 stubFetch(fetch);render(<TwinPage clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Bearbeiten'}));
 const form=screen.getByRole('form',{name:'Aussage bearbeiten'});
 expect(form.closest('.twin-topic--editing')).toBeTruthy();
 expect(form.querySelector('details').open).toBe(false);
 expect(screen.getByText('Kundenaussage · Vertraulich · Freigabe nötig')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Aussage'),{target:{value:'Neue Formulierung'}});
 fireEvent.click(screen.getByRole('button',{name:'Aussage speichern'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3));
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({confidentiality:'Client Confidential',external_use:'Approval Required',evidence_type:'Client Statement'});
});
it('automatically reveals a saved AI preview on returning to the profile',async()=>{
 const saved={id:'saved',rows:[{index:0,data:{key:'R02.01',value:'Saved answer'},sources:[],message:'Source'}],unanswered:0};
 const fetch=vi.fn().mockImplementation(url=>Promise.resolve(response(url.endsWith('/ai-import')?{job:{status:'complete',note:'Ready'},preview:saved}:data)));
 vi.stubGlobal('fetch',fetch);render(<TwinPage clientId={1}/>);
 await screen.findByText('Saved answer');
 expect(screen.getByRole('button',{name:'Mit KI importieren'}).getAttribute('aria-expanded')).toBe('true');
 expect(screen.getByText('1 KI-Vorschläge gespeichert')).toBeTruthy();
 expect(fetch.mock.calls.every(([,options])=>!options?.method)).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Mit KI importieren'}));
 fireEvent.click(screen.getByRole('button',{name:'Mit KI importieren'}));
 expect(screen.getByText('Saved answer')).toBeTruthy();
 expect(fetch.mock.calls.filter(([url])=>!url.endsWith('/onboarding-audio'))).toHaveLength(2);
});
it('shows the brief as numbered cards and the customer questionnaire as its own panel',async()=>{
 const researched={...row,id:7,key:'R01.01',value:'Zalando SE',source_url:'https://www.corporate.zalando.com/de/impressum',
  source_title:'Öffentliche Onboarding-Recherche',note:'Weitere Quellen: https://handelsregister.de/x, https://de.wikipedia.org/wiki/Zalando'};
 const founded={...row,id:8,key:'A01.03',value:'2008 in Berlin.'};
 const fields=[{key:'R01.01',label:'Unternehmensidentität',section:'R',group:'R01 Öffentliches Unternehmensbild',requirement:'Optional',hint:'Wie lautet der offizielle Firmenname?'},
  {key:'R02.01',label:'Rechtliche Unternehmensdaten',section:'R',group:'R01 Öffentliches Unternehmensbild',requirement:'Optional',hint:''},
  {key:'Q01.14',label:'Von welchen externen Akteuren hängt Ihr Geschäft ab?',section:'Q',group:'Q01 Strategie',requirement:'Optional',hint:'Bitte nennen Sie Partner.'},
  {key:'A01.03',label:'Wann wurde das Unternehmen gegründet?',section:'A. Client Facts',group:'A01 Unternehmen',requirement:'Empfohlen'},
  {key:'A01.04',label:'Wo befindet sich der Hauptsitz?',section:'A. Client Facts',group:'A01 Unternehmen',requirement:'Pflicht'}];
 stubFetch(vi.fn().mockResolvedValue(response({...data,fields,statements:[researched,founded]})));
 render(<TwinPage clientId={1}/>);
 const brief=(await screen.findByRole('heading',{name:'Unternehmenssteckbrief'})).closest('section');
 const asked=screen.getByRole('heading',{name:'Kundenfragebogen'}).closest('section');
 expect(within(brief).getByText('Zalando SE')).toBeTruthy();
 expect(within(brief).getByText('01')).toBeTruthy();
 expect(within(brief).getByText('bitte ergänzen')).toBeTruthy();
 expect(within(brief).getByText('1 von 2 Themen recherchiert')).toBeTruthy();
 // The guiding question is the card title's tooltip, not a paragraph.
 expect(within(brief).getByRole('heading',{name:'Unternehmensidentität'}).getAttribute('title')).toBe('Wie lautet der offizielle Firmenname?');
 // The question keeps its own number. The guiding text is the customer's,
 // on the customer page; the profile shows no "Leitfragen" at all.
 expect(within(asked).getByText('14')).toBeTruthy();
 expect(within(asked).queryByRole('img',{name:'Vom Kunden noch nicht bestätigt'})).toBeNull();
 expect(within(asked).queryByText('Bitte nennen Sie Partner.')).toBeNull();
 expect(within(asked).queryByRole('button',{name:'Leitfragen'})).toBeNull();
 // A researched company fact appears at a glance; the catalogue is not shown.
 expect(within(screen.getByLabelText('Auf einen Blick')).getByText('2008 in Berlin.')).toBeTruthy();
 expect(screen.getByRole('progressbar',{name:'Profilvollständigkeit'})).toBeTruthy();
 expect(within(brief).getByRole('link',{name:'corporate.zalando.com'}).getAttribute('href')).toBe(researched.source_url);
 expect(within(brief).getByText('+2 Quellen')).toBeTruthy();
 expect(screen.queryByText('Wo befindet sich der Hauptsitz?')).toBeNull();
 expect(screen.queryByRole('button',{name:/Katalog/})).toBeNull();
});
it('shows only the latest answer without acknowledgement icons',async()=>{
 stubFetch(vi.fn().mockResolvedValue(response({...data,statements:[{...row,value:'Old research',verified_at:'2026-01-01',id:1},{...row,value:'Current correction',id:8,customer_confirmed_at:'2026-11-07T12:00:00Z'}]})));
 render(<TwinPage clientId={1}/>);
 await screen.findByText('Current correction');
 expect(screen.queryByText('Old research')).toBeNull();
 expect(screen.queryByRole('img',{name:'Vom Kunden bestätigt'})).toBeNull();
 expect(screen.getAllByRole('button',{name:'Bearbeiten'})).toHaveLength(1);
});
