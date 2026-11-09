import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {it,expect,vi,afterEach} from 'vitest';
import {OnboardingAccess} from './OnboardingAccess.jsx';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('requires a password and sends it only in the login body',async()=>{
 global.fetch=vi.fn(async(url,o)=>({ok:false,json:async()=>({detail:'Zugangsdaten ungültig'})}));
 render(<OnboardingAccess slug="infuze-cbd"/>);
 fireEvent.change(await screen.findByLabelText('Passwort'),{target:{value:'separate-secret'}});
 fireEvent.click(screen.getByRole('button',{name:'Fragebogen öffnen'}));
 expect(await screen.findByRole('alert')).toBeTruthy();
 const [url,options]=fetch.mock.calls[1];expect(url).toBe('/api/onboarding/login');expect(JSON.parse(options.body)).toEqual({slug:'infuze-cbd',password:'separate-secret'});
 expect(options.credentials).toBe('same-origin');
});
