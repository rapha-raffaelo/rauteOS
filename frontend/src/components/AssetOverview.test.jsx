import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {AssetOverview} from './AssetOverview.jsx';
afterEach(()=>vi.unstubAllGlobals());
it('shows actual assets with customer ribbons and combinable filters',async()=>{
 const texts=[{id:1,type:'asset',client:'Alpha',client_id:1,title:'Kundenmail',format:'mail',format_name:'Mail',href:'/asset/1',generated_at:'2026-11-12',released_at:null},
 {id:2,type:'asset',client:'Beta',client_id:2,title:'Statement',format:'statement',format_name:'Statement',href:'/asset/2',generated_at:'2026-11-12',released_at:'2026-11-12'}];
 const fetch=vi.fn(async url=>({ok:true,json:async()=>({texts:url.includes('client_id=2')?[texts[1]]:texts,clients:[{id:1,name:'Alpha',count:1},{id:2,name:'Beta',count:1}],total:2})}));
 vi.stubGlobal('fetch',fetch);render(<AssetOverview/>);
 await screen.findByRole('link',{name:/Kundenmail/});
 expect(screen.queryByRole('combobox')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Freigegeben'}));
 expect(screen.queryByRole('link',{name:/Kundenmail/})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:/Beta 1/}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledWith('/api/v1/workbench/assets?client_id=2',expect.anything()));
 await screen.findByRole('link',{name:/Statement/});
 fireEvent.change(screen.getByRole('searchbox'),{target:{value:'unmatched'}});
 expect(screen.getByText('Keine Assets für diese Auswahl')).toBeTruthy();
});
