import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {NewsRefresh} from './NewsRefresh.jsx';
afterEach(()=>vi.unstubAllGlobals());
it('starts a run and disables duplicate clicks',async()=>{
 const fetch=vi.fn(async (_url,options)=>({ok:true,json:async()=>options?.method==='POST'?{active:true}:{active:false,run:{id:1}}}));
 vi.stubGlobal('fetch',fetch);render(<NewsRefresh onFinished={()=>{}}/>);
 await waitFor(()=>expect(fetch).toHaveBeenCalled());
 fireEvent.click(screen.getByRole('button',{name:'Nachrichten aktualisieren'}));
 await screen.findByText('Nachrichten werden geladen…');
 expect(screen.getByRole('button').disabled).toBe(true);
 expect(fetch).toHaveBeenCalledWith('/api/v1/news-run',{method:'POST'});
});
