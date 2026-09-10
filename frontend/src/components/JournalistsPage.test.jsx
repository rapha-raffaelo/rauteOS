import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {JournalistsPage,ResearchPanel} from './JournalistsPage.jsx';
const contact={id:1,name:'Anna Beispiel',outlet:'Handelsblatt',email:'',updated_at:'2026-09-10T10:00:00Z'};
const profile={topics:[],specialties:[],story_types:[],companies:[],source_aliases:[],preferences:'',relationship_status:'Unbekannt',last_interaction_at:null,revision:0};
const data={contact,profile,relationship_options:['Unbekannt','Im Kontakt'],articles:[],corpus_capped:false,
  relationship:{last_interaction_at:null,tally:{anschreiben:0,antworten:0,veroeffentlicht:0},timeline:[],capped:false}};
const response=(body,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
afterEach(()=>vi.unstubAllGlobals());
it('saves profile topics with the revision without starting research',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({contacts:[contact]})).mockResolvedValueOnce(response(data))
    .mockResolvedValue(response({...data,profile:{...profile,topics:['FuelEU','BioLNG'],revision:1}}));
  vi.stubGlobal('fetch',fetch);render(<JournalistsPage params={new URLSearchParams('contact=1')}/>);
  fireEvent.change(await screen.findByLabelText('Themen'),{target:{value:'FuelEU\nBioLNG'}});
  fireEvent.click(screen.getByRole('button',{name:'Profil speichern'}));await screen.findByText('Profil gespeichert.');
  expect(fetch.mock.calls[2][0]).toBe('/api/v1/journalists/1');
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toMatchObject({revision:0,contact_updated_at:contact.updated_at,profile:{topics:['FuelEU','BioLNG']}});
  expect(fetch.mock.calls.some(([url])=>url.includes('research'))).toBe(false);
});
it('retains unsaved changes after a conflict',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response({contacts:[contact]})).mockResolvedValueOnce(response(data))
    .mockResolvedValue(response({detail:'Profil wurde inzwischen geändert.'},409)));
  render(<JournalistsPage params={new URLSearchParams('contact=1')}/>);
  fireEvent.change(await screen.findByLabelText('Notizen'),{target:{value:'My correction'}});
  fireEvent.click(screen.getByRole('button',{name:'Profil speichern'}));
  await screen.findByRole('alert');expect(screen.getByLabelText('Notizen').value).toBe('My correction');
});
it('creates only explicitly entered contact details',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({contacts:[]})).mockResolvedValue(response(data));
  vi.stubGlobal('fetch',fetch);render(<JournalistsPage params={new URLSearchParams()}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Neuer Kontakt'}));
  fireEvent.change(screen.getByLabelText('Name'),{target:{value:'Anna Beispiel'}});
  fireEvent.change(screen.getByLabelText('Medium'),{target:{value:'Handelsblatt'}});
  fireEvent.click(screen.getByRole('button',{name:'Kontakt speichern'}));await screen.findByLabelText('Themen');
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({name:'Anna Beispiel',outlet:'Handelsblatt'});
});
it('starts research only on submission and shows archive-only limitations',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({context:{title:'Transport'},research:null}))
    .mockResolvedValue(response({id:2,query:'BioLNG',status:'archive_only',finished_at:'2026-09-10T10:00:00Z',
      note:'Keine frische Quelle verfügbar; nur Archivbelege.',providers:{Perigon:{status:'failed',articles:0}},results:[]}));
  vi.stubGlobal('fetch',fetch);render(<ResearchPanel clientId={1} contextKind="developed" contextId={9} onContact={vi.fn()}/>);
  await screen.findByText('Transport');expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('Suchthema'),{target:{value:'BioLNG'}});
  fireEvent.click(screen.getByRole('button',{name:'Frisch recherchieren'}));await screen.findByText('Nur Archiv verfügbar');
  expect(screen.getByText(/Abruf fehlgeschlagen/)).toBeTruthy();
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({context_kind:'developed',context_id:9,query:'BioLNG'});
});
it('shows dated evidence and opens the matching contact',async()=>{
  const onContact=vi.fn();
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response({context:{title:'Transport'},research:{status:'complete',query:'FuelEU',
    finished_at:'2026-09-10T10:00:00Z',providers:{},note:'Sources are incomplete.',results:[{name:contact.name,outlet:contact.outlet,
      contact_id:1,fit:'Belegter Themenbezug',reason:'Two articles in six weeks.',approach:'Kurzer CEO-Kommentar',article_count:2,
      evidence:[{url:'https://example.org/story',title:'FuelEU costs',source:'Handelsblatt',author:contact.name,published_at:'2026-09-09T10:00:00Z',provider:'Perigon'}]}]}})));
  render(<ResearchPanel clientId={1} contextKind="developed" contextId={9} onContact={onContact}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Profil öffnen'}));expect(onContact).toHaveBeenCalledWith(1);
  expect(screen.getByText('FuelEU costs').getAttribute('href')).toBe('https://example.org/story');
  expect(screen.getByText(/Handelsblatt · .*2026.* · Perigon/)).toBeTruthy();
});
