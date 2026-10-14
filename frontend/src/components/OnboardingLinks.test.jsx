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
 expect(screen.getByLabelText('Kundenlink').value).toContain('/example-ag');
 expect(fetch.mock.calls.some(([p,o])=>p.endsWith('/link/ensure')&&o.method==='POST')).toBe(true);
});
