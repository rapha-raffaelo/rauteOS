import React from 'react';
import {it, expect, afterEach} from 'vitest';
import {render, screen, cleanup} from '@testing-library/react';
import {ClientOverview} from './ClientOverview.jsx';
afterEach(cleanup);
it('keeps the cockpit and integrates today company news',()=>{
 render(<ClientOverview clientId={9} data={{client:{id:9,name:'Zenchef'},today_news:{total:1,items:[{id:1,title:'Heutige Unternehmensnews',url:'https://example.com/news',source:'Zeitung',published_at:'2026-11-09T09:00:00Z',summary:'Neue Meldung'}]},opportunities:[{title:'Alte Story'}],texts:[]}}/>);
 expect(screen.getByText('Heutige Unternehmensnews ↗')).toBeTruthy();
 for(const title of ['Laufende Stories','Nächste Schritte','Das Unternehmen','Aktuelle Texte','Alte Story','Leistungen · Quartal','Monitoring im Überblick','Letzte Aktivität'])expect(screen.getByText(title)).toBeTruthy();
 expect(screen.getByRole('link',{name:'Ganzes Archiv →'}).getAttribute('href')).toBe('/client/9');
});
it('shows an empty state when there are no news today',()=>{
 render(<ClientOverview clientId={9} data={{client:{name:'Zenchef'},today_news:{total:0,items:[]}}}/>);
 expect(screen.getByText('Heute wurden noch keine relevanten Kundenmeldungen erfasst.')).toBeTruthy();
});
it('tops a quiet day up with the archive\'s latest coverage, scored and dismissable',()=>{
 const earlier=[{id:7,analysis_id:70,title:'Freedom24 plant Niederlassung in Genf',url:'https://moneycab.com/x',source:'Moneycab',
  published_at:'2026-11-04T13:43:00Z',summary:'Genf im ersten Quartal 2027',important:true,category:'wettbewerb',importance:7}];
 const {container}=render(<ClientOverview clientId={9} data={{client:{id:9,name:'Freedom24'},today_news:{total:0,items:[],earlier}}}/>);
 expect(screen.getByText('Freedom24 plant Niederlassung in Genf ↗')).toBeTruthy();
 expect(screen.getByText('7/10')).toBeTruthy();
 expect(screen.getByText('Alert')).toBeTruthy();
 expect(screen.getByText(/04\.11\. · 14:43 · Moneycab/)).toBeTruthy();
 const form=container.querySelector('form.co-news-dismiss');
 expect(form.getAttribute('action')).toBe('/coverage/70/dismiss');
 expect(new FormData(form).get('redirect_to')).toBe('/client/9/overview#kundennews');
});

it('dates each opportunity card, with the year only when it is not this one', () => {
 const year = new Date().getFullYear();
 const data = {client:{name:'Remexian'},summary:null,twin:null,texts:[],activity:[],opportunities:[
  {context_kind:'developed',context_id:1,title:'Bedrocan-Insolvenz',status:'draft',created_at:`${year}-11-02T09:00:00Z`},
  {context_kind:'detected',context_id:2,title:'G-BA',status:'active',created_at:'2024-03-05T09:00:00Z'}]};
 render(<ClientOverview data={data} clientId={9}/>);
 expect(screen.getByText('2. November').getAttribute('datetime')).toBe(`${year}-11-02T09:00:00Z`);
 expect(screen.getByText('5. März 2024')).toBeTruthy();
});

it('names the company behind the brand under its title', () => {
 const data = {client:{id:9,name:'ZenchefOS'},summary:null,texts:[],activity:[],opportunities:[],
  company:{description:'',goal:'',tags:['Gastronomie'],legal_name:'Zenchef SAS'}};
 render(<ClientOverview data={data} clientId={9}/>);
 expect(screen.getByText(/Unternehmen dahinter: Zenchef SAS/)).toBeTruthy();
});
