import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {it,expect,vi,afterEach,beforeEach} from 'vitest';
import OverdueTasks from './OverdueTasks.jsx';
beforeEach(()=>localStorage.clear());
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('can dismiss reminders for today without hiding another users reminder',async()=>{
 const data={member:'raphael',day:'2026-11-12',tasks:[{id:1,title:'Anrufen',due_on:'2026-11-11',days_overdue:1,href:'/aufgaben?aufgabe=1'}]};
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>data})));
 render(<OverdueTasks/>);await screen.findByText('Anrufen');
 expect(screen.getByText('Seit gestern überfällig')).toBeTruthy();
 fireEvent.click(screen.getByText('Heute ausblenden'));
 expect(screen.queryByText('Anrufen')).toBeNull();
 cleanup();render(<OverdueTasks/>);
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
 expect(screen.queryByText('Anrufen')).toBeNull();
 cleanup();data.member='lucas';render(<OverdueTasks/>);await screen.findByText('Anrufen');
});
