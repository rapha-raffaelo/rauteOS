import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {it,expect,vi,afterEach,beforeEach} from 'vitest';
import ClaudeLogin from './ClaudeLogin.jsx';
beforeEach(()=>{
 sessionStorage.clear();
 HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 HTMLDialogElement.prototype.close=function(){this.open=false;};
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
it('opens for expired login, starts server login and accepts a code',async()=>{
 const popup={opener:null,closed:false,location:{replace:vi.fn()},close:vi.fn()};
 vi.spyOn(window,'open').mockReturnValue(popup);
 const fetch=vi.fn(async(url,options)=>({ok:true,json:async()=>url.endsWith('/status')?{state:'login_required'}:url.endsWith('/code')?{id:'one',state:'connected',message:'Claude ist angemeldet'}:{id:'one',state:'waiting',url:'https://claude.ai/oauth/authorize?state=test',message:'Bitte bestätigen'}}));
 vi.stubGlobal('fetch',fetch);render(<ClaudeLogin/>);
 await waitFor(()=>expect(document.querySelector('dialog').open).toBe(true));
 fireEvent.click(screen.getByText('Mit Claude anmelden'));
 await waitFor(()=>expect(popup.location.replace).toHaveBeenCalled());
 fireEvent.change(screen.getByLabelText(/Bestätigungscode/),{target:{value:'code#state'}});
 fireEvent.click(screen.getByText('Code bestätigen'));
 await screen.findByText('Claude ist verbunden');
 expect(fetch.mock.calls.find(([u])=>u.endsWith('/code'))[1].body.get('code')).toBe('code#state');
 expect(popup.close).toHaveBeenCalled();
});
it('does not call an unknown status expired and can open manually',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({state:'unknown'})})));
 render(<ClaudeLogin/>);
 expect(document.querySelector('dialog').open).toBe(false);
 fireEvent(window,new Event('raute:claude-login'));
 expect(document.querySelector('dialog').open).toBe(true);
 fireEvent.click(screen.getByText('Später'));
 expect(document.querySelector('dialog').open).toBe(false);
});
