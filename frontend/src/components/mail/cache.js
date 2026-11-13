import {journalistRequest as request} from '../../journalists-api.js';

// What the Gmail page has already seen, so a folder, a client tab or a mail
// opened before shows at once and is brought up to date behind it. Lists live
// for this tab in sessionStorage (gone when the tab closes); whole mails only
// in memory. Nothing here leaves the browser.
const MAX_LISTS=24;
const lists=new Map(),threads=new Map(),pending=new Map();

// No mailbox data survives a page reload or a login change in sessionStorage.
// Older releases stored it without an owner; discard those entries immediately.
try { window.sessionStorage.removeItem('gm.lists.v1'); window.sessionStorage.removeItem('gm.status.v1'); } catch {}
export function cachedList(key){return lists.get(key)||null;}
export function rememberList(key,value){lists.delete(key);lists.set(key,value);while(lists.size>MAX_LISTS)lists.delete(lists.keys().next().value);}
export function forgetLists(){lists.clear();}
export function cachedStatus(){return null;}
export function rememberStatus(){lists.clear();threads.clear();pending.clear();}

// One mail, read once per change: the list's historyId says whether the copy
// held is still the mail Gmail has.
export function cachedThread(id,history){const held=threads.get(id);return held&&(!history||held.history===history)?held.messages:null;}
export function loadThread(id,history=''){
 const held=cachedThread(id,history);if(held)return Promise.resolve(held);
 const key=`${id}@${history}`;if(pending.has(key))return pending.get(key);
 const job=request(`mailbox/threads/${encodeURIComponent(id)}${history?`?h=${encodeURIComponent(history)}`:''}`)
  .then(v=>{threads.set(id,{history,messages:v.messages});if(threads.size>60)threads.delete(threads.keys().next().value);return v.messages;})
  .finally(()=>pending.delete(key));
 pending.set(key,job);return job;
}
export function prefetchThread(id,history){loadThread(id,history).catch(()=>{});}
export function forgetThreads(ids){ids.forEach(id=>threads.delete(id));}
