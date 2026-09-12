import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {OpportunitiesPage,OpportunityWorkspace} from './OpportunitiesPage.jsx';
const response=(body,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
const data={id:null,context_kind:'developed',context_id:1,title:'Data story',revision:0,status:'draft',evidence_type:'RAUTE Hypothesis',
 situation:'A study idea',relevance:'Relevant to the business',why_now:'Planning opportunity',window_ends_at:null,proposed_window_days:null,
 storylines:['Publish a study'],storyline:'Publish a study',speaker_statement_id:null,speakers:[{id:7,value:'Anna CEO',evidence_type:'Client Statement'}],
 contact_ids:[],contacts:[{id:9,name:'A Journalist',outlet:'Paper'}],recommended_actions:['kundenmail','pitch'],risks:['Verify the client claim'],
 research:[],sources:[],proof_points:[],assets:[],events:[],legacy_href:'/client/1/advice'};
afterEach(()=>vi.unstubAllGlobals());
it('opens the workspace without activation and sends explicit choices',async()=>{
 const fetch=vi.fn().mockImplementation((url,options)=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:options?.method?{...data,revision:1,status:'active'}:data)));
 vi.stubGlobal('fetch',fetch);render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 await screen.findByText('A study idea');expect(fetch.mock.calls.every(([,options])=>!options?.method)).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Strategie & Auswahl'}));
 fireEvent.change(screen.getByLabelText('Sprecher aus dem Profil'),{target:{value:'7'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'A Journalist · Paper'}));
 fireEvent.click(screen.getByRole('button',{name:'ACTIVATE'}));
 await screen.findByText('Gelegenheit aktiviert. Wählen Sie den nächsten Arbeitsschritt.');
 const call=fetch.mock.calls.find(([url])=>url.endsWith('/activate'));
 expect(JSON.parse(call[1].body)).toEqual({revision:0,storyline:'Publish a study',speaker_statement_id:7,contact_ids:[9]});
});
it('preserves unsaved storyline on a conflict',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockImplementation((url,options)=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:options?.method?{detail:'Neu laden und vergleichen.'}:data,options?.method?409:200))));
 render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);
 fireEvent.change(await screen.findByLabelText('Gewählte Storyline'),{target:{value:'My unsaved angle'}});
 fireEvent.click(screen.getByRole('button',{name:'Strategie & Auswahl'}));
 fireEvent.click(screen.getByRole('button',{name:'Auswahl speichern'}));await screen.findByRole('alert');
 expect(screen.getByLabelText('Gewählte Storyline').value).toBe('My unsaved angle');
});
it('does not offer activation for a closed opportunity',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockImplementation(url=>Promise.resolve(response(url.includes('journalist-research')?{context:{title:'Data story'},research:null}:{...data,status:'closed'}))));
 render(<OpportunityWorkspace clientId={1} kind="developed" identity={1}/>);await screen.findByText('A study idea');
 expect(screen.queryByRole('button',{name:'ACTIVATE'})).toBeNull();expect(screen.getByLabelText('Gewählte Storyline').disabled).toBe(true);
});
it('develops a chance only after submission and distinguishes no opportunity from failure',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response({client:{name:'Demo'},opportunities:[],development:null})).mockResolvedValue(response({status:'no_opportunity',note:'Not enough evidence',queries:[],sources:[],started_at:'2026-09-10T10:00:00Z'}));
 vi.stubGlobal('fetch',fetch);render(<OpportunitiesPage clientId={1} params={new URLSearchParams()}/>);
 await screen.findByText('Demo');expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.change(screen.getByLabelText('Recherchefokus'),{target:{value:'BioLNG'}});
 fireEvent.click(screen.getByRole('button',{name:'Chance entwickeln'}));await screen.findByText('Not enough evidence');
 expect(screen.getByRole('status').textContent).toContain('Keine neue tragfähige Idee');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({focus:'BioLNG'});
});
