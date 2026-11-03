import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {OnboardingLinks} from './OnboardingLinks.jsx';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('creates and copies a customer link before research finishes',async()=>{
 const copy=vi.fn().mockResolvedValue();Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:copy}});
 global.fetch=vi.fn(async(path,options)=>({ok:true,json:async()=>path.endsWith('/ensure')?{status:'queued',path:'/onboarding#secret/example-ag',expires_at:'2026-11-01'}:path.endsWith('onboarding-workflow')?{status:'not_started'}:[]}));
 render(<OnboardingLinks clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Onboarding-Link erstellen'}));
 expect(await screen.findByRole('button',{name:'Link kopiert'})).toBeTruthy();
 expect(copy).toHaveBeenCalledWith(window.location.origin+'/onboarding#secret/example-ag');
 // The token is a secret: copied, not printed on the page.
 expect(screen.queryByLabelText('Kundenlink')).toBeNull();
 expect(fetch.mock.calls.some(([p,o])=>p.endsWith('/link/ensure')&&o.method==='POST')).toBe(true);
});

it('shows the link to copy by hand only when the clipboard refuses it',async()=>{
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn().mockRejectedValue(new Error('denied'))}});
 global.fetch=vi.fn(async path=>({ok:true,json:async()=>path.endsWith('onboarding-workflow')?{status:'ready',path:'/onboarding#secret/example-ag',expires_at:'2026-11-12',researched_fields:3,total_fields:9,sources:2,answered:0,total_questions:22}:[]}));
 render(<OnboardingLinks clientId={1}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Kundenlink kopieren'}));
 expect((await screen.findByLabelText('Kundenlink')).value).toContain('/example-ag');
});
