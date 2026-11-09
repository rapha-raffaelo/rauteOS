import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {OpportunitiesPage,OpportunityWorkspace,JournalistPicker} from './OpportunitiesPage.jsx';
const response=(body,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
const data={id:null,context_kind:'developed',context_id:1,title:'Data story',revision:0,status:'draft',evidence_type:'RAUTE Hypothesis',
 situation:'A study idea',relevance:'Relevant to the business',why_now:'Planning opportunity',window_ends_at:null,proposed_window_days:null,
 storylines:['Publish a study'],storyline:'Publish a study',speaker_statement_id:null,speakers:[{id:7,value:'Anna CEO',evidence_type:'Client Statement'}],
 contact_ids:[],contacts:[{id:9,name:'A Journalist',outlet:'Paper'}],recommended_actions:['kundenmail','pitch'],risks:['Verify the client claim'],
 research:[],sources:[],proof_points:[],assets:[],events:[],legacy_href:'/client/1/advice'};
afterEach(()=>vi.unstubAllGlobals());
it('filters 520 journalists by name and outlet without losing hidden selections',()=>{
 const items=Array.from({length:520},(_,i)=>({id:i+1,name:`Journalist ${i+1}`,outlet:i===519?'Handelsblatt':'Zeitung'}));
 items[519].name='Andreas Kröner';
 function Picker(){const [selected,setSelected]=React.useState([1]);return <JournalistPicker items={items} selected={selected} onChange={setSelected}/>;}
 render(<Picker/>);
 fireEvent.change(screen.getByRole('searchbox'),{target:{value:'kroner handelsblatt'}});
 expect(screen.getByRole('status').textContent).toContain('1 ausgewählt · 1 von 520');
 fireEvent.click(screen.getByRole('checkbox',{name:'Andreas Kröner · Handelsblatt'}));
 fireEvent.change(screen.getByRole('searchbox'),{target:{value:''}});
 fireEvent.click(screen.getByRole('checkbox',{name:'Nur ausgewählte'}));
 expect(screen.getByRole('status').textContent).toContain('2 ausgewählt · 2 von 520');
 expect(screen.getByRole('checkbox',{name:'Journalist 1 · Zeitung'}).checked).toBe(true);
 expect(screen.getByRole('checkbox',{name:'Andreas Kröner · Handelsblatt'}).checked).toBe(true);
 fireEvent.change(screen.getByRole('searchbox'),{target:{value:'kein treffer'}});
 expect(screen.getByText('Keine passenden Journalisten gefunden.')).toBeTruthy();
},20000); // 520 rows in jsdom: slow on a loaded machine, and speed is not what this checks
it('omits empty briefing sections and generic timing placeholders',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockImplementation(url=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:{...data,why_now:'Zeitfenster noch zu prüfen',recommended_actions:[],risks:[]}))));
 render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 await screen.findByText('A study idea');
 expect(screen.queryByText('Warum jetzt?')).toBeNull();
 expect(screen.queryByText('Kein bestätigtes Zeitfenster.')).toBeNull();
 expect(screen.queryByText('Empfohlene Maßnahmen')).toBeNull();
 expect(screen.queryByText('Belege und offene Fragen')).toBeNull();
});
it('shows a prepared release before a workspace is saved without creating anything',async()=>{
 const fetch=vi.fn().mockImplementation(url=>Promise.resolve(response(url.includes('/press-release')?{status:'ready',title:'Existing release',body:'Saved draft body',url:'/draft/8'}:url.includes('journalist-research')?{context:{title:'Data story'},research:null}:{...data,angle_id:42,assets:[{id:8,kind:'pressemitteilung',href:'/draft/8'}]})));
 vi.stubGlobal('fetch',fetch);render(<OpportunityWorkspace clientId={1} kind="detected" identity={3}/>);
 await screen.findByText('Saved draft body');
 expect(screen.getByRole('link',{name:'Bearbeiten & prüfen'}).getAttribute('href')).toBe('/draft/8');
 expect(fetch.mock.calls.some(([url])=>url==='/api/v1/clients/1/impulses/42/press-release')).toBe(true);
 expect(fetch.mock.calls.every(([,options])=>!options?.method)).toBe(true);
});
it('opens the workspace without activation and sends explicit choices',async()=>{
 const fetch=vi.fn().mockImplementation((url,options)=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:options?.method?{...data,revision:1,status:'active'}:data)));
 vi.stubGlobal('fetch',fetch);render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 await screen.findByText('A study idea');expect(fetch.mock.calls.every(([,options])=>!options?.method)).toBe(true);
 fireEvent.change(screen.getByLabelText('Sprecher aus dem Profil'),{target:{value:'7'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'A Journalist · Paper'}));
 fireEvent.click(screen.getByRole('button',{name:'Opportunity aktivieren'}));
 await screen.findByText('Gelegenheit aktiviert. Wählen Sie den nächsten Arbeitsschritt.');
 const call=fetch.mock.calls.find(([url])=>url.endsWith('/activate'));
 expect(JSON.parse(call[1].body)).toEqual({revision:0,storyline:'Publish a study',speaker_statement_id:7,speaker_person_id:null,contact_ids:[9]});
});
it('preserves unsaved storyline on a conflict',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockImplementation((url,options)=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:options?.method?{detail:'Neu laden und vergleichen.'}:data,options?.method?409:200))));
 render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 fireEvent.change(await screen.findByLabelText('Gewählte Storyline'),{target:{value:'My unsaved angle'}});
 fireEvent.click(screen.getByRole('button',{name:'Auswahl speichern'}));await screen.findByRole('alert');
 expect(screen.getByLabelText('Gewählte Storyline').value).toBe('My unsaved angle');
});
it('does not offer activation for a closed opportunity',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockImplementation(url=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:{...data,status:'closed'}))));
 render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);await screen.findByText('A study idea');
 expect(screen.queryByRole('button',{name:'Opportunity aktivieren'})).toBeNull();expect(screen.getByLabelText('Gewählte Storyline').disabled).toBe(true);
});
it('develops a chance only after submission and distinguishes no opportunity from failure',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({client:{name:'Demo'},opportunities:[],development:null})).mockResolvedValue(response({status:'no_opportunity',note:'Not enough evidence',queries:[],sources:[],started_at:'2026-09-10T10:00:00Z'}));
 vi.stubGlobal('fetch',fetch);render(<OpportunitiesPage clientId={1} params={new URLSearchParams()}/>);
 await screen.findByText('Demo');expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.change(screen.getByLabelText('Recherchefokus'),{target:{value:'BioLNG'}});
 fireEvent.click(screen.getByRole('button',{name:'Themen-Pitch entwickeln'}));await screen.findByText('Not enough evidence');
 expect(screen.getByRole('status').textContent).toContain('Keine neue tragfähige Idee');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({focus:'BioLNG'});
});

it('separates reactive occasions and proactive pitches on one board',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response({client:{name:'Demo'},development:null,reaction:{crisis:{title:'Aktive Krise',href:'/client/1/krise'},issues:[{id:1,title:'Offenes Risiko',href:'/client/1/issues'}]},opportunities:[{context_kind:'detected',context_id:1,title:'News occasion',status:'draft'},{context_kind:'developed',context_id:2,title:'Our topic pitch',status:'draft'}]})));
 render(<OpportunitiesPage clientId={1} params={new URLSearchParams()}/>);
 await screen.findByText('News occasion');
 expect(screen.getByRole('heading',{name:'Aktivitäten'})).toBeTruthy();
 expect(within(screen.getByRole('region',{name:'Issues / Krisen'})).getByText('Offenes Risiko')).toBeTruthy();
 expect(within(screen.getByRole('region',{name:'Opportunities'})).getByText('News occasion')).toBeTruthy();
 expect(within(screen.getByRole('region',{name:'Impulse'})).getByText('Our topic pitch')).toBeTruthy();
 expect(within(screen.getByRole('region',{name:'Opportunities'})).queryByText('Our topic pitch')).toBeNull();
});
it('saves a structured media contact independently of legacy statement ids',async()=>{
 const fetch=vi.fn().mockImplementation((url,options)=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:{...data,speaker_people:[{id:4,name:'Anna Test',position:'Leitung'}],...(options?.method?{revision:1,speaker_person_id:4}:{})})));
 vi.stubGlobal('fetch',fetch);render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 await screen.findByRole('option',{name:'Anna Test · Leitung · Medienkontakt'});
 fireEvent.change(screen.getByLabelText('Sprecher aus dem Profil'),{target:{value:'person:4'}});
 fireEvent.click(screen.getByRole('button',{name:'Auswahl speichern'}));
 await screen.findByText('Auswahl gespeichert.');
 const call=fetch.mock.calls.find(([,o])=>o?.method==='PUT');
 expect(JSON.parse(call[1].body)).toMatchObject({speaker_person_id:4,speaker_statement_id:null});
});
