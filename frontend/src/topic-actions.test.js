import {it,expect,vi,afterEach} from 'vitest';
import {setTopicActive} from './topic-actions.js';
const row={context_kind:'developed',context_id:7,title:'Banklizenz für Qonto'};
const reply=data=>({ok:true,headers:{get:()=>'application/json'},json:async()=>data});
afterEach(()=>vi.unstubAllGlobals());
it('cancelling deactivation makes no request',async()=>{
 const confirm=vi.fn(()=>false),fetch=vi.fn();vi.stubGlobal('confirm',confirm);vi.stubGlobal('fetch',fetch);
 expect(await setTopicActive(8,row,false)).toBeNull();
 expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Banklizenz für Qonto'));
 expect(confirm).toHaveBeenCalledWith(expect.stringContaining('bleiben erhalten'));
 expect(fetch).not.toHaveBeenCalled();
});
it('only confirmed deactivation sends the versioned change',async()=>{
 vi.stubGlobal('confirm',vi.fn(()=>true));
 const fetch=vi.fn().mockResolvedValueOnce(reply({revision:4})).mockResolvedValueOnce(reply({status:'draft'}));vi.stubGlobal('fetch',fetch);
 expect(await setTopicActive(8,row,false)).toEqual({status:'draft'});
 expect(fetch).toHaveBeenCalledTimes(2);
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({revision:4,action:'deactivate'});
});
it('activation does not ask for deactivation confirmation',async()=>{
 const confirm=vi.fn();vi.stubGlobal('confirm',confirm);
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(reply({revision:0,title:row.title})).mockResolvedValueOnce(reply({status:'active'})));
 await setTopicActive(8,row,true);
 expect(confirm).not.toHaveBeenCalled();
});
