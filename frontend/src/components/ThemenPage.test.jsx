import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor,within} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {ThemenPage,Agenda,pitchOf} from './ThemenPage.jsx';
import {AssetsPage,KINDS,WritingProgress,Editor,Workspace} from './AssetsPage.jsx';
beforeEach(()=>{vi.stubGlobal('confirm',vi.fn(()=>true));HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};});
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,'','/');});

const json=body=>({ok:true,headers:{get:()=>'application/json'},json:async()=>body});
function routes(map){
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body});
  const key=Object.keys(map).find(k=>url.endsWith(k));
  return json(typeof map[key]==='function'?map[key](options):map[key]);}));
 return calls;
}
const board={client:{id:1,name:'Remexian'},reaction:{crisis:null,issues:[]},development:null,opportunities:[
 {context_kind:'developed',context_id:7,title:'Online-Verschreibung',status:'draft',origin:'medien',starred_by:'lucas',summary:'Kurz',occasion:{source:'Ärzte Zeitung',published_at:'2026-11-12T08:00:00Z'}},
 {context_kind:'detected',context_id:3,title:'Preise fallen',status:'active',origin:'anlass',summary:''},
]};
const detail={revision:2,title:'Online-Verschreibung',situation:'Der Bundestag hat beschlossen.',relevance:'Patienten in Dauertherapie.',
 storyline:'',storylines:['Versorgungssicherheit statt Lifestyle-Debatte'],speaker_statement_id:null,speaker_person_id:null,
 speaker_proposal:{person_id:4,reason:'Themen passen'},people:[{id:4,label:'Dr. A. Beispiel'}],speakers:[],contact_ids:[],contacts:[],recipients:[]};

it('filters Themen and links to a dedicated detail page without hover',async()=>{
 routes({'/opportunities':board,'/opportunities/developed/7':detail,'/agenda':{items:[],total:0,href:'/client/1/plan'}});
 render(<ThemenPage clientId={1}/>);
 await screen.findByText('Online-Verschreibung');
 fireEvent.click(screen.getByRole('button',{name:'★ Aus Medien · 1'}));
 expect(screen.queryByText('Preise fallen')).toBeNull();
 const link=screen.getByRole('link',{name:'Details ansehen'});
 fireEvent.mouseEnter(link);
 expect(screen.queryByRole('tooltip')).toBeNull();
 expect(link.getAttribute('href')).toBe('/client/1/themen?kind=developed&context=7');
 fireEvent.click(screen.getByRole('button',{name:'In Bearbeitung · 1'}));
 expect(screen.getByRole('link',{name:'Weiterarbeiten →'}).getAttribute('href')).toBe('/client/1/themen?kind=detected&context=3&step=assets');
});

it('activates from the topic card, retains choices and offers deactivation and Assets',async()=>{
 const calls=routes({'/opportunities':board,'/agenda':{items:[]},'/opportunities/developed/7':detail,
 '/opportunities/developed/7/activate':{...detail,status:'active',workflow_summary:{label:'In Entwicklung'}},
 '/opportunities/developed/7/workflow':{...detail,status:'draft',workflow_summary:{label:'Deaktiviert'}}});
 render(<ThemenPage clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Thema aktivieren'}));
 await waitFor(()=>expect(document.getElementById('thema-developed-7').classList.contains('themen-card--active')).toBe(true));
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/activate')).body)).toMatchObject({revision:2,storyline:detail.storylines[0],contact_ids:[]});
 const card=document.getElementById('thema-developed-7');
 expect(card.querySelector('a[href="/client/1/assets?kind=developed&context=7"]')).toBeTruthy();
 fireEvent.click([...card.querySelectorAll('button')].find(b=>b.textContent==='Thema deaktivieren'));
 await waitFor(()=>expect(card.classList.contains('themen-card--active')).toBe(false));
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/workflow')).body).action).toBe('deactivate');
});

it('draws the Agenda with a detail link instead of a hover note',async()=>{
 routes({'/agenda':{items:[{id:1,title:'Fachtagung',reason:'Externer Anlass',month:'2026-12',day:2,format:'',state:'angenommen',href:'/client/1/plan#monat-2026-12'}],total:1,href:'/client/1/plan'}});
 render(<Agenda clientId={1}/>);
 expect(await screen.findByRole('link',{name:'Fachtagung'})).toBeTruthy();
 expect(screen.getByText('02.12.')).toBeTruthy();
 expect(screen.queryByRole('tooltip')).toBeNull();
 expect(screen.getByRole('link',{name:'Details ansehen →'}).getAttribute('href')).toBe('/client/1/plan#monat-2026-12');
 expect(screen.getByRole('link',{name:'Ganze Agenda →'}).getAttribute('href')).toBe('/client/1/plan');
});

it('takes the chosen storyline over RAUTE proposals as the pitch',()=>{
 expect(pitchOf({storyline:'Eigene',storylines:['RAUTE']})).toBe('Eigene');
 expect(pitchOf({storyline:'',storylines:[]})).toBe('');
});

it('offers the six asset kinds, drafts one and edits it with send locked',async()=>{
 const text={id:5,type:'asset',kind:'statement',title:'Statement',body:'Entwurf',digest:'d'.repeat(64),released_at:null};
 let texts=[];
 const calls=routes({'/opportunities':{...board,opportunities:[{...board.opportunities[1]}]},
  '/opportunities/detected/3':{...detail,storyline:'Qualität vor Preis'},
  '/opportunities/detected/3/activation':o=>o.method==='POST'?{id:9,status:'running'}:{formats:[],texts,latest:null},
  '/activation/asset/5':{formats:[],texts:[{...text,body:'Geändert'}],latest:null}});
 window.history.replaceState(null,'','/client/1/assets?kind=detected&context=3');
 render(<AssetsPage clientId={1}/>);
 expect(await screen.findByText('Pitch: Qualität vor Preis')).toBeTruthy();
 const kinds=screen.getByRole('group',{name:'Asset wählen'});
 expect([...kinds.querySelectorAll('strong')].map(n=>n.textContent)).toEqual(KINDS.map(k=>k[1]));
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 fireEvent.click(screen.getByRole('button',{name:'Statement schreiben lassen'}));
 await waitFor(()=>expect(calls.some(c=>c.method==='POST'&&c.url.endsWith('/activation'))).toBe(true));
 cleanup();texts=[text];
 render(<AssetsPage clientId={1} params={new URLSearchParams('kind=detected&context=3&text=asset-5')}/>);
 fireEvent.change(await screen.findByLabelText('Text'),{target:{value:'Geändert'}});
 expect(screen.getByRole('button',{name:'Senden · bald'}).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Speichern'}));
 await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.method==='PUT').body)).toMatchObject({digest:'d'.repeat(64),body:'Geändert'});
});

it('requests an automatic recent-news proposal and links the triggering report',async()=>{
 const calls=routes({'/opportunities':{...board,opportunities:[{...board.opportunities[0],occasion:{title:'Neue Studie',url:'https://example.org/studie',source:'Fachmedium'}}]},
  '/themen/suggestions':{status:'empty',note:'Noch keine neuen Meldungen'},'/agenda':{items:[]}});
 render(<ThemenPage clientId={1}/>);
 expect(await screen.findByRole('link',{name:'Neue Studie ↗'})).toHaveProperty('href','https://example.org/studie');
 expect(await screen.findByRole('status')).toHaveProperty('textContent','Noch keine neuen Meldungen');
 expect(calls.some(c=>c.url.endsWith('/themen/suggestions')&&c.method==='POST')).toBe(true);
});

it('creates an asset without a person selector or a preparatory person update',async()=>{
 const calls=routes({'/opportunities':{...board,opportunities:[{...board.opportunities[1]}]},
  '/opportunities/detected/3':{...detail,storyline:'Ein Thema',speaker_statement_id:99,
    speakers:[{id:99,value:'Die PR betreut eine Agentur'}],people:[{id:4,label:'Anna Beispiel, Marketing'}]},
  '/opportunities/detected/3/activation':o=>o.method==='POST'?{id:9,status:'running'}:{formats:[],texts:[],latest:null}});
 window.history.replaceState(null,'','/client/1/assets?kind=detected&context=3');
 render(<AssetsPage clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 expect(screen.queryByRole('combobox',{name:'Ansprechperson (optional)'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}));
 await waitFor(()=>expect(calls.some(c=>c.method==='POST')).toBe(true));
 expect(calls.some(c=>c.method==='PUT')).toBe(false);
});

it('opens a bookmarked topic with all workflow steps and sources',async()=>{
 window.history.replaceState(null,'','/client/1/themen?kind=developed&context=7');
 routes({'/opportunities/developed/7':{...detail,sources:[{title:'Studie',url:'https://example.org/studie'}]}});
 render(<ThemenPage clientId={1}/>);
 expect(await screen.findByRole('heading',{name:'Online-Verschreibung'})).toBeTruthy();
 expect(screen.getByText('Der Bundestag hat beschlossen.')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Studie ↗'}).getAttribute('href')).toBe('https://example.org/studie');
 expect(screen.getByRole('link',{name:'← Zurück zu den Themen'}).getAttribute('href')).toBe('/client/1/themen');
 expect(screen.getByRole('navigation',{name:'Themenworkflow'}).querySelectorAll('button')).toHaveLength(8);
 expect(screen.queryByRole('tooltip')).toBeNull();
});

it('shows a centered writing dialog with indeterminate progress and a background option',()=>{
 const dismiss=vi.fn();const {unmount}=render(<WritingProgress kind="kundenmail" onDismiss={dismiss}/>);
 expect(screen.getByRole('dialog',{name:'RAUTE schreibt Kundenmail…'})).toBeTruthy();
 const bar=screen.getByRole('progressbar',{name:'Entwurf wird erstellt'});
 expect(bar.getAttribute('aria-valuenow')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Im Hintergrund weiterarbeiten'}));
 expect(dismiss).toHaveBeenCalledOnce();
 unmount();expect(screen.queryByRole('dialog')).toBeNull();
});

it('opens the Deep Dive on the card on hover, with the fitting contacts',async()=>{
 routes({'/opportunities':board,'/opportunities/developed/7':{...detail,recipients:[{name:'Anna Muster',outlet:'Ärzte Zeitung',reason:'schrieb zuletzt darüber'}]},
  '/opportunities/detected/3':detail,'/themen/suggestions':{status:'empty'},'/agenda':{items:[]}});
 render(<ThemenPage clientId={1}/>);
 const [trigger]=await screen.findAllByRole('button',{name:'Deep Dive'});
 fireEvent.mouseEnter(trigger.parentElement);
 expect(await screen.findByText('Der Bundestag hat beschlossen.')).toBeTruthy();
 expect(screen.getByText('Warum für Remexian relevant?')).toBeTruthy();
 expect(screen.getByText('Anna Muster')).toBeTruthy();
 expect(screen.getByRole('tooltip').textContent).toContain('Versorgungssicherheit statt Lifestyle-Debatte');
});

it('shows a press release as its page with the client logo, and exports with the chosen logo',async()=>{
 const {Editor}=await import('./AssetsPage.jsx');
 localStorage.clear();
 const text={id:8,type:'asset',kind:'pressemitteilung',title:'Remexian fordert Übergangsregel',body:'Text',digest:'d',released_at:null};
 render(<Editor text={text} path="p" exportBase="/api/v1/clients/1/assets/asset/8" client={{name:'Remexian',logo:'data:image/png;base64,AAAA'}} onSaved={()=>{}}/>);
 expect(screen.getByRole('img',{name:'Logo Remexian'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'Kunden-Logo'}).getAttribute('aria-pressed')).toBe('true');
 fireEvent.click(screen.getByRole('button',{name:'raute+kopf'}));
 expect(screen.getByRole('img',{name:'raute+kopf'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Exportieren'}));
 expect(screen.getByRole('link',{name:'Herunterladen'}).getAttribute('href')).toBe('/api/v1/clients/1/assets/asset/8/export.docx?logo=raute');
 expect(localStorage.getItem('asset-logo:asset-8')).toBe('raute');
});

it('gives active topics individual tabs and identifies the currently open topic',async()=>{
 const second={...board.opportunities[0],status:'active'};
 routes({'/opportunities':{...board,opportunities:[board.opportunities[1],second]},
  '/opportunities/detected/3':{...detail,status:'active',title:'Preise fallen'},
  '/opportunities/developed/7':{...detail,status:'active'},
  '/opportunities/detected/3/activation':{texts:[],latest:null},
  '/opportunities/developed/7/activation':{texts:[],latest:null}});
 render(<AssetsPage clientId={1}/>);
 const first=await screen.findByRole('tab',{name:/Preise fallen/});
 expect(first.getAttribute('aria-selected')).toBe('true');
 expect(screen.getByText('Du arbeitest an')).toBeTruthy();
 fireEvent.keyDown(first,{key:'ArrowRight'});
 const secondTab=screen.getByRole('tab',{name:/Online-Verschreibung/});
 expect(secondTab.getAttribute('aria-selected')).toBe('true');
 expect(first.getAttribute('aria-selected')).toBe('false');
 expect(document.activeElement).toBe(secondTab);
 expect(window.location.search).toBe('?kind=developed&context=7');
});


it('shows concrete topic actions without inventing a scheduled date',async()=>{
 routes({'/agenda':{items:[{id:'topic-4',kind:'topic',title:'Banklizenz einordnen',next_steps:['Umfang der Lizenz prüfen','Produktfragen für das Briefing sammeln'],month:'2026-11',day:null,format:'',state:'vorgeschlagen',href:'/client/1/themen?context=4'}],total:1}});
 render(<Agenda clientId={1}/>);
 expect(await screen.findByText('Umfang der Lizenz prüfen')).toBeTruthy();
 expect(screen.getByText('Produktfragen für das Briefing sammeln')).toBeTruthy();
 expect(screen.getByText('Aktueller Anlass')).toBeTruthy();
 expect(screen.getByText('Termin noch offen')).toBeTruthy();
});


it('changes an asset stage without editing or releasing its text',async()=>{
 const onSaved=vi.fn(),text={id:5,type:'asset',kind:'statement',title:'Statement',body:'Entwurf',digest:'d'.repeat(64),stage:'offen'};
 const calls=routes({'/activation/asset/5/stage':{texts:[{...text,stage:'review'}]}});
 render(<Editor text={text} path="clients/1/opportunities/developed/7/activation" onSaved={onSaved}/>);
 fireEvent.change(screen.getByLabelText('Stadium des Assets'),{target:{value:'review'}});
 await waitFor(()=>expect(onSaved).toHaveBeenCalledOnce());
 expect(JSON.parse(calls[0].body)).toEqual({stage:'review'});
});

it('requires confirmation before moving an asset to the recycle bin',async()=>{
 const text={id:5,type:'asset',kind:'statement',title:'Statement prüfen',body:'Entwurf',digest:'d'.repeat(64),stage:'offen'};
 const calls=routes({'/opportunities/developed/7':detail,'/opportunities/developed/7/activation':{texts:[text],latest:null},'/activation/asset/5':{texts:[],latest:null}});
 render(<Workspace clientId={1} kind="developed" identity={7}/>);
 const trash=await screen.findByRole('button',{name:'Statement prüfen in den Papierkorb'});
 confirm.mockReturnValue(false);fireEvent.click(trash);
 expect(calls.some(c=>c.method==='DELETE')).toBe(false);
 confirm.mockReturnValue(true);fireEvent.click(trash);
 await waitFor(()=>expect(calls.some(c=>c.method==='DELETE')).toBe(true));
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Statement prüfen in den Papierkorb'})).toBeNull());
});

it('creates a pitch asset without any journalist selected',async()=>{
 const calls=routes({'/opportunities':{...board,opportunities:[{...board.opportunities[1]}]},
  '/opportunities/detected/3':{...detail,contacts:[],contact_ids:[],storyline:'Ein Thema'},
  '/opportunities/detected/3/activation':o=>o.method==='POST'?{id:9,status:'running'}:{formats:[],texts:[],latest:null}});
 render(<AssetsPage clientId={1} params={new URLSearchParams('kind=detected&context=3')}/>);
 await screen.findByText('Pitch: Ein Thema');
 fireEvent.click(screen.getByRole('button',{name:/^Pitch/}));
 expect(screen.getByLabelText('Journalist:in').required).toBe(false);
 const create=screen.getByRole('button',{name:'Pitch schreiben lassen'});
 expect(create.disabled).toBe(false);
 fireEvent.click(create);
 await waitFor(()=>expect(calls.some(c=>c.method==='POST'&&c.url.endsWith('/activation'))).toBe(true));
 expect(JSON.parse(calls.find(c=>c.method==='POST'&&c.url.endsWith('/activation')).body)).toMatchObject({kind:'pitch',contact_id:null});
});

const promptContacts=[{id:10,name:'Anna',outlet:'Zeitung'},{id:11,name:'Ben',outlet:'Magazin'}];
function promptWorkspaceRoutes(){
 return routes({'/opportunities/developed/7':{...detail,contacts:promptContacts,contact_ids:[10,11]},
  '/opportunities/developed/7/activation':{texts:[],latest:null},
  '/opportunities/developed/8':{...detail,contacts:promptContacts,contact_ids:[10,11]},
  '/opportunities/developed/8/activation':{texts:[],latest:null}});
}
it('keeps additional asset instructions separate by format, recipient and topic',async()=>{
 promptWorkspaceRoutes();
 const {rerender}=render(<Workspace clientId={1} kind="developed" identity={7}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Kurz und kollegial'}});
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('');
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Ein zitierfähiger Satz'}});
 fireEvent.click(screen.getByRole('button',{name:/^Pitch/}));
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'An Annas Recherche anknüpfen'}});
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'11'}});
 expect(screen.getByLabelText('Auftrag').value).toBe('');
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Für Bens Ressort'}});
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 expect(screen.getByLabelText('Auftrag').value).toBe('An Annas Recherche anknüpfen');
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('Ein zitierfähiger Satz');
 fireEvent.click(screen.getByRole('button',{name:/^Kundenmail/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('Kurz und kollegial');
 rerender(<Workspace clientId={1} kind="developed" identity={8}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('');
});
it('seeds master and follow-up prompts only into their intended pitches',async()=>{
 promptWorkspaceRoutes();
 const {rerender}=render(<Workspace clientId={1} kind="developed" identity={7} initialInstruction="Gemeinsamer Master-Pitch"/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('');
 fireEvent.click(screen.getByRole('button',{name:/^Pitch/}));
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 expect(screen.getByLabelText('Auftrag').value).toBe('Gemeinsamer Master-Pitch');
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Individuelle Ergänzung für Anna'}});
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'11'}});
 expect(screen.getByLabelText('Auftrag').value).toBe('Gemeinsamer Master-Pitch');
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 expect(screen.getByLabelText('Auftrag').value).toBe('Individuelle Ergänzung für Anna');
 rerender(<Workspace clientId={1} kind="developed" identity={7} initialInstruction="Neue Studie für Anna" initialContact={10}/>);
 await waitFor(()=>expect(screen.getByLabelText('Auftrag').value).toBe('Neue Studie für Anna'));
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'11'}});
 expect(screen.getByLabelText('Auftrag').value).not.toBe('Neue Studie für Anna');
 fireEvent.click(screen.getByRole('button',{name:/^Interviewangebot/}));
 expect(screen.getByLabelText('Auftrag').value).toBe('');
});
it('clears an accepted asset prompt and locks the inputs while the request is pending',async()=>{
 let resolvePost;
 const calls=[];
 vi.stubGlobal('fetch',vi.fn((url,options={})=>{
  calls.push({url,...options});
  if(options.method==='POST')return new Promise(resolve=>{resolvePost=resolve;});
  return Promise.resolve(json(url.endsWith('/activation')?{texts:[],latest:null}:{...detail,contacts:promptContacts,contact_ids:[10,11]}));
 }));
 render(<Workspace clientId={1} kind="developed" identity={7} initialInstruction="Follow-up nur für Anna" initialContact={10}/>);
 const instruction=await screen.findByLabelText('Auftrag');
 fireEvent.click(screen.getByRole('button',{name:'Pitch schreiben lassen'}));
 await waitFor(()=>expect(resolvePost).toBeTypeOf('function'));
 expect(instruction.disabled).toBe(true);
 expect(screen.getByLabelText('Journalist:in').disabled).toBe(true);
 resolvePost(json({id:9,status:'running'}));
 await waitFor(()=>expect(screen.getByLabelText('Auftrag').value).toBe(''));
 expect(JSON.parse(calls.find(c=>c.method==='POST').body)).toMatchObject({kind:'pitch',contact_id:10,instruction:'Follow-up nur für Anna'});
});
it('retains an asset prompt when its creation request fails',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{
  if(options.method==='POST')return {...json({detail:'Bitte erneut versuchen.'}),ok:false,status:503};
  return json(url.endsWith('/activation')?{texts:[],latest:null}:detail);
 }));
 render(<Workspace clientId={1} kind="developed" identity={7}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Diesen Auftrag beim Fehler behalten'}});
 fireEvent.click(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}));
 await screen.findByRole('alert');
 expect(screen.getByLabelText('Auftrag').value).toBe('Diesen Auftrag beim Fehler behalten');
 expect(screen.getByLabelText('Auftrag').disabled).toBe(false);
});


it('keeps a rejected second asset visible and lets the user correct and retry',async()=>{
 const first={id:21,type:'asset',kind:'kundenmail',title:'Erste Kundenmail',body:'Bestehender Entwurf',digest:'a'.repeat(64)};
 let attempts=0;
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{
  if(options.method==='POST'){
   attempts++;
   return attempts===1?{...json({detail:'Bitte zuerst einen Sprecher im Workspace auswählen.'}),ok:false,status:422}:json({id:2,status:'running'});
  }
  return json(url.endsWith('/activation')?{texts:[first],latest:{id:1,kind:'kundenmail',status:'complete'}}:detail);
 }));
 render(<Workspace clientId={1} kind="developed" identity={7} initialText="asset-21"/>);
 await screen.findByLabelText('Text');
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 fireEvent.change(screen.getByLabelText('Auftrag'),{target:{value:'Eine kurze Einordnung'}});
 fireEvent.click(screen.getByRole('button',{name:'Statement schreiben lassen'}));
 const failure=await screen.findByRole('dialog',{name:'Asset konnte nicht gestartet werden'});
 expect(within(failure).getByRole('alert').textContent).toContain('Sprecher');
 expect(within(failure).queryByRole('progressbar')).toBeNull();
 expect(screen.getByLabelText('Text').value).toBe('Bestehender Entwurf');
 expect(screen.getByLabelText('Auftrag').value).toBe('Eine kurze Einordnung');
 fireEvent.click(within(failure).getByRole('button',{name:'Schließen'}));
 expect(screen.queryByRole('dialog')).toBeNull();
 expect(screen.getByRole('alert').textContent).toContain('Sprecher');
 fireEvent.click(within(screen.getByRole('group',{name:'Asset wählen'})).getByRole('button',{name:/^Kundenmail/}));
 fireEvent.click(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}));
 const progress=await screen.findByRole('dialog',{name:'RAUTE schreibt Kundenmail…'});
 await waitFor(()=>expect(attempts).toBe(2));
 expect(within(progress).getByRole('progressbar')).toBeTruthy();
 expect(screen.queryByRole('alert')).toBeNull();
});


it('selects at least one topic tile for each asset format and sends only those topics',async()=>{
 const topics=[{id:7,title:'Banklizenz',summary:'Folgen für KMU'},{id:12,title:'Liquiditätsplanung',summary:'Konkrete Maßnahmen'}];
 const calls=routes({'/opportunities/developed/7':{...detail,id:7},
  '/opportunities/developed/7/activation':o=>o.method==='POST'?{id:2,status:'running'}:{topics,default_topic_id:7,texts:[],latest:null}});
 render(<Workspace clientId={1} kind="developed" identity={7}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Kundenmail/}));
 expect(screen.getByRole('checkbox',{name:'Banklizenz'}).checked).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'Banklizenz'}));
 expect(screen.getByText('Wähle mindestens ein Thema aus.')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Kundenmail schreiben lassen'}).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'Liquiditätsplanung'}));
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 expect(screen.getByRole('checkbox',{name:'Banklizenz'}).checked).toBe(true);
 expect(screen.getByRole('checkbox',{name:'Liquiditätsplanung'}).checked).toBe(false);
 fireEvent.click(screen.getByRole('checkbox',{name:'Liquiditätsplanung'}));
 fireEvent.click(screen.getByRole('button',{name:/^Kundenmail/}));
 expect(screen.getByRole('checkbox',{name:'Banklizenz'}).checked).toBe(false);
 expect(screen.getByRole('checkbox',{name:'Liquiditätsplanung'}).checked).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:/^Statement/}));
 fireEvent.click(screen.getByRole('button',{name:'Statement schreiben lassen'}));
 await waitFor(()=>expect(calls.some(c=>c.method==='POST')).toBe(true));
 expect(JSON.parse(calls.find(c=>c.method==='POST').body).topic_ids).toEqual([7,12]);
 expect(screen.getByRole('checkbox',{name:'Banklizenz'}).disabled).toBe(true);
});

it('keeps pitch topic choices separate for each journalist',async()=>{
 const topics=[{id:7,title:'Thema A'},{id:12,title:'Thema B'}];
 routes({'/opportunities/developed/7':{...detail,id:7,contact_ids:[10,11],contacts:[{id:10,name:'Anna'},{id:11,name:'Ben'}]},
  '/opportunities/developed/7/activation':{topics,default_topic_id:7,texts:[],latest:null}});
 render(<Workspace clientId={1} kind="developed" identity={7}/>);
 fireEvent.click(await screen.findByRole('button',{name:/^Pitch/}));
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'Thema B'}));
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'11'}});
 expect(screen.getByRole('checkbox',{name:'Thema B'}).checked).toBe(false);
 fireEvent.change(screen.getByLabelText('Journalist:in'),{target:{value:'10'}});
 expect(screen.getByRole('checkbox',{name:'Thema B'}).checked).toBe(true);
});
