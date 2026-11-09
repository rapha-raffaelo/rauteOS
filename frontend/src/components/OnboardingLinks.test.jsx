import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {OnboardingLinks} from './OnboardingLinks.jsx';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('creates and copies a customer link before research finishes',async()=>{
 const copy=vi.fn().mockResolvedValue();Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:copy}});
 global.fetch=vi.fn(async(path,options)=>({ok:true,json:async()=>path.endsWith('/ensure')?{status:'queued',path:'/onboarding/example-ag',expires_at:'2026-11-01'}:path.endsWith('onboarding-workflow')?{status:'not_started'}:[]}));
 render(<OnboardingLinks clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Neuen Fragebogen erstellen'}));
 expect(await screen.findByText('Link kopiert.')).toBeTruthy();
 expect(copy).toHaveBeenCalledWith(window.location.origin+'/onboarding/example-ag');
 // The token is a secret: copied, not printed on the page.
 expect(screen.queryByLabelText('Kundenlink')).toBeNull();
 expect(fetch.mock.calls.some(([p,o])=>p.endsWith('/link/ensure')&&o.method==='POST')).toBe(true);
});

it('shows the link to copy by hand only when the clipboard refuses it',async()=>{
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn().mockRejectedValue(new Error('denied'))}});
 global.fetch=vi.fn(async path=>({ok:true,json:async()=>path.endsWith('onboarding-workflow')?{status:'ready',path:'/onboarding/example-ag',expires_at:'2026-11-12',researched_fields:3,total_fields:9,sources:2,answered:0,total_questions:22}:[]}));
 render(<OnboardingLinks clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Link kopieren'}));
 expect((await screen.findByLabelText('Kundenlink')).value).toContain('/example-ag');
});

it('offers three icon actions and recreates access after deactivation',async()=>{
 let active=true;
 global.fetch=vi.fn(async(path,options)=>{
   if(path.endsWith('/revoke'))active=false;
   return {ok:true,json:async()=>path.endsWith('onboarding-workflow')?{status:'ready',invite_id:4,path:active?'/onboarding/example-ag':null,expires_at:'2027-01-01',password:'separate-password'}:[]};
 });
 render(<OnboardingLinks clientId={1}/>);
 expect(await screen.findByRole('button',{name:'Link kopieren'})).toBeTruthy();
 expect(screen.getByRole('link',{name:'Fragebogen öffnen'}).getAttribute('href')).toContain('/onboarding/example-ag');
 expect(screen.queryByText(/Links verwalten/)).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Deaktivieren'}));
 expect(await screen.findByRole('button',{name:'Neuen Fragebogen erstellen'})).toBeTruthy();
 expect(screen.queryByRole('link',{name:'Fragebogen öffnen'})).toBeNull();
 expect(fetch.mock.calls.some(([p,o])=>p==='/client/1/onboarding-invites/4/revoke'&&o.method==='POST')).toBe(true);
});
it('copies the public domain link and password separately',async()=>{
 const copy=vi.fn().mockResolvedValue();Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:copy}});
 global.fetch=vi.fn(async()=>({ok:true,json:async()=>({status:'ready',path:'/onboarding/infuze-cbd',public_url:'https://raute-kopf.com/onboarding/infuze-cbd',password:'separate-password',expires_at:'2027-01-01'})}));
 render(<OnboardingLinks clientId={16}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Link kopieren'}));
 expect(copy).toHaveBeenLastCalledWith('https://raute-kopf.com/onboarding/infuze-cbd');
 fireEvent.click(screen.getByRole('button',{name:'Passwort kopieren'}));
 expect(copy).toHaveBeenLastCalledWith('separate-password');
});
it('shows customer completion even while background research is still queued',async()=>{
 global.fetch=vi.fn(async(path)=>({ok:true,json:async()=>path.endsWith('onboarding-workflow')?{status:'queued',completed:true,answered:2,total_questions:22}:[]}));
 render(<OnboardingLinks clientId={16}/>);
 expect(await screen.findByText('Vom Kunden abgeschlossen')).toBeTruthy();
 expect(screen.getByText('Recherche wartet auf den Start')).toBeTruthy();
});
