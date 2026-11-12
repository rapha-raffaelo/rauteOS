import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {ThemenPage,Agenda,pitchOf} from './ThemenPage.jsx';
import {AssetsPage,KINDS} from './AssetsPage.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

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

it('filters Themen by origin and shows the Deep Dive on hover',async()=>{
 routes({'/opportunities':board,'/opportunities/developed/7':detail,'/agenda':{items:[],total:0,href:'/client/1/plan'}});
 render(<ThemenPage clientId={1}/>);
 await screen.findByText('Online-Verschreibung');
 fireEvent.click(screen.getByRole('button',{name:'★ Aus Medien · 1'}));
 expect(screen.queryByText('Preise fallen')).toBeNull();
 fireEvent.mouseEnter(screen.getByRole('button',{name:'Deep Dive'}));
 expect(await screen.findByText('Der Bundestag hat beschlossen.')).toBeTruthy();
 expect(screen.getByText('Warum für Remexian relevant?')).toBeTruthy();
 expect(screen.getByText('Versorgungssicherheit statt Lifestyle-Debatte')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Aktiviert · 1'}));
 expect(screen.getByRole('link',{name:'Zu den Assets →'}).getAttribute('href')).toBe('/client/1/assets?kind=detected&context=3');
});

it('activates a Thema with RAUTE pitch and speaker, then opens Assets',async()=>{
 const assign=vi.fn();vi.stubGlobal('location',{...window.location,assign});
 const calls=routes({'/opportunities':board,'/opportunities/developed/7':detail,'/opportunities/developed/7/activate':{...detail,status:'active'},'/agenda':{items:[],total:0}});
 render(<ThemenPage clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Thema aktivieren'}));
 await waitFor(()=>expect(assign).toHaveBeenCalledWith('/client/1/assets?kind=developed&context=7'));
 const sent=JSON.parse(calls.find(c=>c.url.endsWith('/activate')).body);
 expect(sent).toMatchObject({revision:2,storyline:'Versorgungssicherheit statt Lifestyle-Debatte',speaker_person_id:4});
});

it('draws the Agenda as a timeline with a hover note',async()=>{
 routes({'/agenda':{items:[{id:1,title:'Fachtagung',reason:'Externer Anlass',month:'2026-12',day:2,format:'',state:'angenommen',href:'/client/1/plan#monat-2026-12'}],total:1,href:'/client/1/plan'}});
 render(<Agenda clientId={1}/>);
 expect(await screen.findByRole('link',{name:'Fachtagung'})).toBeTruthy();
 expect(screen.getByText('02.12.')).toBeTruthy();
 expect(screen.getByRole('tooltip').textContent).toContain('Externer Anlass');
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
