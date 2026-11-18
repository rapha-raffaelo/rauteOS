import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {it,expect,vi,afterEach,beforeEach} from 'vitest';
import NewsAlerts from './NewsAlerts.jsx';
beforeEach(()=>localStorage.clear());
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('bundles sources, scopes the request and remembers dismissal per user',async()=>{
 const data={member:'raphael',items:[{id:'8:topic-116',client_name:'Qonto',title:'Qonto erhält Banklizenz',count:2,href:'/client/8/themen?context=116',sources:[{id:1,title:'Erste Meldung',source:'Medium A',url:'https://a.de'},{id:2,title:'Zweite Meldung',source:'Medium B',url:'https://b.de'}]}]};
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>data})));
 render(<NewsAlerts path="/client/8/themen"/>);
 await screen.findByText('Qonto erhält Banklizenz');
 expect(fetch.mock.calls[0][0]).toBe('/api/v1/news-alerts?client_id=8');
 expect(screen.getByText('2 Alerts zu diesem Ereignis · letzte 24 Stunden')).toBeTruthy();
 expect(screen.getAllByRole('link',{hidden:true})).toHaveLength(3);
 fireEvent.click(screen.getByText('Gelesen'));
 expect(screen.queryByText('Qonto erhält Banklizenz')).toBeNull();
 cleanup();render(<NewsAlerts path="/client/8/themen"/>);
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
 expect(screen.queryByText('Qonto erhält Banklizenz')).toBeNull();
 cleanup();data.member='lucas';render(<NewsAlerts path="/client/8/themen"/>);
 await screen.findByText('Qonto erhält Banklizenz');
});
it('does not interrupt the page when alerts are unavailable',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>{throw new Error('offline');}));
 const {container}=render(<NewsAlerts/>);
 await waitFor(()=>expect(fetch).toHaveBeenCalledOnce());
 expect(container.textContent).toBe('');
});
