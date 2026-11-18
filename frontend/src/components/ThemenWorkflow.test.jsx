import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {ThemenWorkflow} from './ThemenWorkflow.jsx';
const original={id:1,revision:2,status:'active',title:'Die Zustellfrage',situation:'Ein aktueller Anlass.',storyline:'Zustellung zählt',storylines:['Wirtschaft','Betroffene','Daten'],selected_storylines:[],contact_ids:[],contacts:[{id:10,name:'Anna Redaktion',outlet:'Wirtschaftszeitung'},{id:11,name:'Tom Redaktion',outlet:'IT-Magazin'}],people:[],assets:[],letters:[],workflow:{approvals:{},followups:{}},events:[],workflow_summary:{label:'In Entwicklung'}};
function mount(step,extra={}){
 window.history.replaceState(null,'',`/client/1/themen?kind=developed&context=7&step=${step}`);
 let current={...original,...extra};const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{
  calls.push({url,...options});const body=options.body?JSON.parse(options.body):{};
  let data=current;
  if(url.endsWith('/activation'))data=extra.activation||{texts:[],formats:[],latest:null};
  else if(options.method==='POST'||options.method==='PUT'){
   if(url.endsWith('/workflow'))current={...current,revision:current.revision+1,workflow:{...current.workflow,...(body.action==='complete'?{completed_at:'2026-11-18',result:body.note}:{})}};
   else current={...current,...body,revision:current.revision+1};data=current;
  }
  return {ok:true,headers:{get:()=>'application/json'},json:async()=>data};
 }));
 render(<ThemenWorkflow clientId={1} kind="developed" identity={7}/>);
 return calls;
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,'','/');});
it('compares two angles and persists the actual choices before opening Assets',async()=>{
 const calls=mount('blickwinkel');
 fireEvent.click(await screen.findByRole('button',{name:/Vorschlag 1/}));fireEvent.click(screen.getByRole('button',{name:/Vorschlag 2/}));
 expect(screen.getByRole('button',{name:/Vorschlag 3/}).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Unser Pitch'),{target:{value:'Eigene Geschichte'}});
 fireEvent.click(screen.getByRole('button',{name:'Blickwinkel übernehmen & Assets entwickeln →'}));
 await screen.findByRole('heading',{name:'Assets entwickeln'});
 const body=JSON.parse(calls.find(c=>c.url.endsWith('/activate')).body);
 expect(body).toMatchObject({revision:2,storyline:'Eigene Geschichte',selected_storylines:['Wirtschaft','Betroffene']});
 expect(window.location.search).toContain('step=assets');
});
it('preserves unsaved angle choices when another workflow step is inspected',async()=>{
 mount('blickwinkel');const input=await screen.findByLabelText('Unser Pitch');
 fireEvent.change(input,{target:{value:'Noch nicht gespeichert'}});
 fireEvent.click(within(screen.getByRole('navigation')).getByRole('button',{name:/Deep Dive/}));
 fireEvent.click(within(screen.getByRole('navigation')).getByRole('button',{name:/Blickwinkel/}));
 expect(screen.getByLabelText('Unser Pitch').value).toBe('Noch nicht gespeichert');
});
it('records customer approval with the exact text version and named evidence',async()=>{
 const calls=mount('freigabe',{assets:[{id:4,kind:'statement',title:'Statement',digest:'d'.repeat(64)}]});
 fireEvent.change(await screen.findByLabelText('Freigabestand'),{target:{value:'approved'}});
 fireEvent.change(screen.getByLabelText('Freigebende Person'),{target:{value:'Anna Kunde'}});
 fireEvent.change(screen.getByLabelText('Nachweis der Zustimmung'),{target:{value:'E-Mail vom 18.11.'}});
 fireEvent.click(screen.getByRole('button',{name:'Freigabestand speichern'}));
 await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body)).toMatchObject({revision:2,action:'approval',text_id:4,digest:'d'.repeat(64),reviewer:'Anna Kunde',note:'E-Mail vom 18.11.',status:'approved'});
});
it('marks a changed approval stale without presenting it as approved',async()=>{
 mount('freigabe',{assets:[{id:4,kind:'statement',title:'Statement',digest:'d'}],workflow:{approvals:{'asset-4':{status:'approved',stale:true,reviewer:'Kunde',note:'Previous text'}}}});
 expect(await screen.findByText('Text geändert · erneut prüfen')).toBeTruthy();
 expect(screen.getByLabelText('Freigabestand').value).toBe('internal');
});
it('saves selected journalists and makes their profiles accessible',async()=>{
 const calls=mount('journalisten');
 fireEvent.click(await screen.findByRole('checkbox',{name:/Anna Redaktion/}));
 expect(screen.getByRole('link',{name:'Profil Anna Redaktion'}).getAttribute('href')).toBe('/contacts?contact=10');
 fireEvent.click(screen.getByRole('button',{name:'Auswahl speichern & Pitches vorbereiten →'}));
 await screen.findByRole('heading',{name:'Vom Master-Pitch zum individuellen Entwurf'});
 expect(JSON.parse(calls.find(c=>c.method==='PUT').body).contact_ids).toEqual([10]);
});
it('does not invent sent pitches, replies or publications',async()=>{
 mount('followup',{letters:[{id:9,state:'entwurf',subject:'Draft',released_at:null}]});
 expect(await screen.findByRole('heading',{name:'Noch kein Versand erfasst'})).toBeTruthy();
 expect(screen.queryByRole('button',{name:'Rückmeldung bestätigen'})).toBeNull();
 fireEvent.click(within(screen.getByRole('navigation')).getByRole('button',{name:/Ergebnis/}));
 const metrics=document.querySelector('.topic-metrics');expect([...metrics.querySelectorAll('strong')].map(n=>n.textContent)).toEqual(['0','0','0']);
});
it('records a dated follow-up on an actually sent letter',async()=>{
 const calls=mount('followup',{letters:[{id:9,journalist:'Anna Redaktion',outlet:'Wirtschaftszeitung',subject:'Zustellfrage',state:'raus',released_at:'2026-11-16'}]});
 fireEvent.change(await screen.findByLabelText('Wiedervorlage'),{target:{value:'2026-11-20'}});
 fireEvent.change(screen.getByLabelText('Recherche & nächster Schritt'),{target:{value:'Neue Studie als Aufhänger'}});
 fireEvent.click(screen.getByRole('button',{name:'Follow-up speichern'}));await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body)).toMatchObject({action:'followup',text_id:9,due_date:'2026-11-20',status:'planned'});
});
it('retains the final evaluation and offers reopening after completion',async()=>{
 const calls=mount('ergebnis');
 fireEvent.change(await screen.findByLabelText('Auswertung'),{target:{value:'Kein passender Zeitpunkt. Im Dezember wieder aufgreifen.'}});
 fireEvent.click(screen.getByRole('button',{name:'Auswertung speichern & Thema abschließen'}));
 await screen.findByRole('button',{name:'Thema wieder öffnen'});
 expect(screen.getByText('Kein passender Zeitpunkt. Im Dezember wieder aufgreifen.')).toBeTruthy();
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body).action).toBe('complete');
});

it('requires explicit confirmation before documenting an already sent pitch',async()=>{
 const calls=mount('pitches',{letters:[{id:9,journalist:'Anna Redaktion',outlet:'Zeitung',subject:'Pitch',message:'Gespeicherter Text',digest:'abc',released_at:null}],workflow:{pitch_approvals:{9:{digest:'abc',reviewer:'Kundin',updated_at:'2026-11-18'}}}});
 const button=await screen.findByRole('button',{name:'Bereits erfolgten Versand erfassen'});
 expect(button.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Versandnachweis'),{target:{value:'Gmail, 18.11. um 10:30'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'Ich habe genau diese Fassung an diesen Empfänger versendet.'}));
 fireEvent.click(button);await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body)).toMatchObject({action:'sent',text_id:9,digest:'abc'});
 expect(calls.some(c=>c.url.includes('/mailbox/send'))).toBe(false);
});
it('preserves unsaved asset text while switching between workflow steps',async()=>{
 mount('assets',{assets:[{id:4,title:'Statement',kind:'statement',digest:'d'}],activation:{texts:[{id:4,type:'asset',title:'Statement',body:'Gespeicherte Fassung',kind:'statement',digest:'d'}],formats:[],latest:null}});
 fireEvent.click(within(await screen.findByRole('region',{name:'Assets zu diesem Thema'})).getByRole('button'));
 fireEvent.change(screen.getByLabelText('Text'),{target:{value:'Noch nicht gespeicherte Änderung'}});
 fireEvent.click(within(screen.getByRole('navigation')).getByRole('button',{name:/Freigabe/}));
 fireEvent.click(within(screen.getByRole('navigation')).getByRole('button',{name:/Assets/}));
 await waitFor(()=>expect(screen.getByLabelText('Text').value).toBe('Noch nicht gespeicherte Änderung'));
});
it('requires a confirmed exact recipient for Gmail delivery',async()=>{
 const calls=mount('pitches',{letters:[{id:9,subject:'Pitch',message:'Approved',journalist:'Anna',email:'anna@example.org',digest:'abc'}],workflow:{pitch_approvals:{9:{digest:'abc',reviewer:'Client'}}}});
 const button=await screen.findByRole('button',{name:'Jetzt verbindlich senden'});
 expect(button.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Empfängeradresse zur Bestätigung eingeben'),{target:{value:'anna@example.org'}});
 fireEvent.click(screen.getByRole('checkbox',{name:/Ich habe Empfänger/}));
 expect(button.disabled).toBe(false);fireEvent.click(button);
 await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body)).toMatchObject({action:'send',text_id:9,digest:'abc',note:'anna@example.org'});
});
it('withholds other recipients during an exclusive phase',async()=>{
 mount('pitches',{letters:[{id:9,subject:'Pitch',journalist:'Anna',digest:'abc'}],workflow:{exclusive:{text_id:8,until:'2099-12-01'},pitch_approvals:{9:{digest:'abc'}}}});
 expect(await screen.findByText('Während der Exklusivphase zurückgehalten.')).toBeTruthy();
 expect(screen.queryByRole('button',{name:'Jetzt verbindlich senden'})).toBeNull();
});
it('hands researched evidence and the intended recipient to follow-up creation',async()=>{
 mount('followup',{contact_ids:[10],letters:[{id:9,contact_id:10,journalist:'Anna Redaktion',subject:'Pitch',state:'raus',released_at:'2026-11-16'}],workflow:{research:{9:{status:'ready',at:'2026-11-18',sources:[{title:'New study',url:'https://example.org/study',snippet:'New evidence',published_at:'2026-11-17'}],queries:[]}}}});
 fireEvent.click(await screen.findByRole('button',{name:'Diesen Bezug für den Entwurf übernehmen →'}));
 const instruction=await screen.findByLabelText('Auftrag');
 expect(instruction.value).toContain('https://example.org/study');
 expect(screen.getByLabelText('Journalist:in').value).toBe('10');
});
