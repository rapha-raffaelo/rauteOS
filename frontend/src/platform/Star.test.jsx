import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {Star} from './ArchivePage.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it('stars an article into the Themen and takes it back',async()=>{
 const fetch=vi.fn()
  .mockResolvedValueOnce({ok:true,json:async()=>({kind:'developed',context:7,status:'draft'})})
  .mockResolvedValueOnce({ok:true,json:async()=>({ok:true})});
 vi.stubGlobal('fetch',fetch);
 render(<Star clientId={1} articleId={42}/>);
 fireEvent.click(screen.getByRole('button',{name:'In Themen aufnehmen'}));
 expect(await screen.findByRole('link',{name:'In Themen →'})).toBeTruthy();
 expect(fetch.mock.calls[0][0]).toBe('/api/v1/clients/1/themen');
 expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({article_id:42});
 fireEvent.click(screen.getByRole('button',{name:'Aus den Themen nehmen'}));
 expect(await screen.findByRole('button',{name:'In Themen aufnehmen'})).toBeTruthy();
 expect(fetch.mock.calls[1]).toMatchObject(['/api/v1/clients/1/themen/42',{method:'DELETE'}]);
});

it('keeps the star of an activated Thema',()=>{
 render(<Star clientId={1} articleId={42} thema={{status:'active'}}/>);
 expect(screen.getByRole('button',{name:'Aus den Themen nehmen'}).disabled).toBe(true);
});
